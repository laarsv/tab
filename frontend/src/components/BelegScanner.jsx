import { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import toast from 'react-hot-toast';
import { api, apiError } from '../api/client.js';
import Modal from './Modal.jsx';
import Spinner from './Spinner.jsx';
import { DialogFuss, SchalterZeile } from './DialogParts.jsx';
import { IconButton, IconCamera, IconCrop, IconImage, IconMaximize, IconRotateLeft, IconRotateRight, IconTrash } from './Icons.jsx';
import { VOLLBILD, alsJpeg, drehe, dreheEcken, erkenneEcken, ladeBild, verarbeite } from '../lib/scan.js';

// Belegscanner: Seiten mit der Handy-Kamera aufnehmen (<input capture>, läuft auf iOS und Android),
// im Browser zuschneiden/entzerren/aufbereiten (lib/scan.js) und als EINE PDF in den Eingang legen
// (POST /api/belege/scan) — mit buchungId direkt an diese Buchung.
//
// Einstieg über den Hook: const scan = useBelegScanner({ gewerbeId, onGespeichert });
// <button onClick={scan.starten}>…</button> {scan.element}
// starten() öffnet sofort die Kamera (der Klick ist die nötige Nutzergeste); erst mit dem Foto
// erscheint der Dialog. Abbrechen in der Kamera ändert nichts.

let naechsteId = 1;

async function seiteAus(file) {
  const src = await ladeBild(file);
  return { id: naechsteId++, src, ecken: erkenneEcken(src), dokument: true };
}

export function useBelegScanner({ gewerbeId, buchungId, onGespeichert }) {
  const kamera = useRef(null);
  const [dateien, setDateien] = useState(null);

  function starten() {
    if (!gewerbeId) {
      toast.error('Erst ein Gewerbe anlegen oder wählen.');
      return;
    }
    kamera.current?.click();
  }

  const element = (
    <>
      <input
        ref={kamera}
        type="file"
        accept="image/*"
        capture="environment"
        className="hidden"
        onChange={(e) => {
          const f = Array.from(e.target.files || []);
          e.target.value = '';
          if (f.length) setDateien(f);
        }}
      />
      {dateien &&
        createPortal(
          <BelegScanner
            gewerbeId={gewerbeId}
            buchungId={buchungId}
            ersteDateien={dateien}
            onClose={() => setDateien(null)}
            onGespeichert={onGespeichert}
          />,
          document.body,
        )}
    </>
  );
  return { starten, element };
}

export default function BelegScanner({ gewerbeId, buchungId, ersteDateien, onClose, onGespeichert }) {
  const [seiten, setSeiten] = useState([]);
  const [aktiv, setAktiv] = useState(0);
  const [laedt, setLaedt] = useState(0); // Anzahl Bilder in Vorbereitung
  const [ansicht, setAnsicht] = useState('zuschnitt'); // zuschnitt | ergebnis
  const [name, setName] = useState('');
  const [busy, setBusy] = useState(false);
  const kamera = useRef(null);
  const galerie = useRef(null);
  const gestartet = useRef(false);

  async function hinzu(files) {
    const bilder = files.filter((f) => f.type.startsWith('image/') || /\.(jpe?g|png|heic|heif|webp)$/i.test(f.name));
    if (bilder.length < files.length) toast.error('Nur Fotos lassen sich scannen.');
    if (!bilder.length) return;
    setLaedt((n) => n + bilder.length);
    for (const f of bilder) {
      try {
        const s = await seiteAus(f);
        setSeiten((alt) => {
          setAktiv(alt.length);
          return [...alt, s];
        });
        setAnsicht('zuschnitt');
      } catch {
        toast.error(`„${f.name}“ ließ sich nicht öffnen. Bitte als JPG oder PNG aufnehmen.`);
      } finally {
        setLaedt((n) => n - 1);
      }
    }
  }

  useEffect(() => {
    if (gestartet.current) return;
    gestartet.current = true;
    hinzu(ersteDateien);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const seite = seiten[aktiv];

  function aendern(patch) {
    setSeiten((alt) => alt.map((s, i) => (i === aktiv ? { ...s, ...patch } : s)));
  }

  function drehen(richtung) {
    if (!seite) return;
    aendern({ src: drehe(seite.src, richtung), ecken: dreheEcken(seite.ecken, richtung) });
  }

  function entfernen() {
    const rest = seiten.filter((_, i) => i !== aktiv);
    setSeiten(rest);
    setAktiv(Math.max(0, Math.min(aktiv, rest.length - 1)));
  }

  function verschieben(richtung) {
    const ziel = aktiv + richtung;
    if (ziel < 0 || ziel >= seiten.length) return;
    const neu = [...seiten];
    [neu[aktiv], neu[ziel]] = [neu[ziel], neu[aktiv]];
    setSeiten(neu);
    setAktiv(ziel);
  }

  async function speichern() {
    if (!seiten.length) return;
    setBusy(true);
    try {
      const form = new FormData();
      form.append('gewerbe_id', gewerbeId);
      if (buchungId) form.append('buchung_id', buchungId);
      if (name.trim()) form.append('name', name.trim());
      for (const [i, s] of seiten.entries()) {
        // Kurz Luft holen, damit der Fortschritt sichtbar bleibt (die Rechnung blockiert sonst die Oberfläche).
        await new Promise((r) => setTimeout(r, 0));
        const blob = await alsJpeg(verarbeite(s.src, s.ecken, s.dokument));
        form.append('seiten', blob, `seite-${i + 1}.jpg`);
      }
      const { data } = await api.post('/api/belege/scan', form);
      toast.success(
        buchungId
          ? `Beleg gescannt (${data.seiten} ${data.seiten === 1 ? 'Seite' : 'Seiten'}) und angehängt.`
          : `Beleg gescannt (${data.seiten} ${data.seiten === 1 ? 'Seite' : 'Seiten'}) — liegt im Eingang.`,
      );
      onClose();
      await onGespeichert?.(data);
    } catch (err) {
      toast.error(apiError(err, 'Speichern fehlgeschlagen.'));
      setBusy(false);
    }
  }

  const leer = !seiten.length;

  return (
    <Modal
      title="Beleg scannen"
      subtitle={
        leer
          ? 'Foto wird vorbereitet…'
          : `${seiten.length} ${seiten.length === 1 ? 'Seite' : 'Seiten'} · wird eine PDF${buchungId ? ' an dieser Buchung' : ' im Eingang'}`
      }
      onClose={busy ? () => {} : onClose}
      maxWidth="max-w-3xl"
    >
      <input
        ref={kamera}
        type="file"
        accept="image/*"
        capture="environment"
        className="hidden"
        onChange={(e) => {
          const f = Array.from(e.target.files || []);
          e.target.value = '';
          hinzu(f);
        }}
      />
      <input
        ref={galerie}
        type="file"
        accept="image/*"
        multiple
        className="hidden"
        onChange={(e) => {
          const f = Array.from(e.target.files || []);
          e.target.value = '';
          hinzu(f);
        }}
      />

      {seite ? (
        <div className="space-y-3">
          <div className="flex items-center gap-1">
            <div role="tablist" aria-label="Ansicht" className="mr-auto inline-flex rounded-lg bg-ink/[0.06] p-0.5">
              {[
                ['zuschnitt', 'Zuschnitt'],
                ['ergebnis', 'Ergebnis'],
              ].map(([k, l]) => (
                <button
                  key={k}
                  type="button"
                  role="tab"
                  aria-selected={ansicht === k}
                  onClick={() => setAnsicht(k)}
                  className={`min-h-[40px] rounded-md px-3 text-sm font-bold outline-none focus-visible:ring-2 focus-visible:ring-royal/40 sm:min-h-[32px]
                    ${ansicht === k ? 'bg-paper text-ink shadow-sm' : 'text-ink/60'}`}
                >
                  {l}
                </button>
              ))}
            </div>
            <IconButton icon={IconRotateLeft} label="Nach links drehen" onClick={() => drehen(-1)} />
            <IconButton icon={IconRotateRight} label="Nach rechts drehen" onClick={() => drehen(1)} />
            <IconButton
              icon={IconCrop}
              label="Blattkanten neu erkennen"
              onClick={() => {
                const e = erkenneEcken(seite.src);
                aendern({ ecken: e });
                if (e === VOLLBILD) toast('Keine Blattkanten gefunden — Ecken bitte von Hand ziehen.');
              }}
            />
            <IconButton icon={IconMaximize} label="Ganzes Foto verwenden" onClick={() => aendern({ ecken: VOLLBILD })} />
            <IconButton icon={IconTrash} label="Seite entfernen" variant="danger" onClick={entfernen} />
          </div>

          {ansicht === 'zuschnitt' ? (
            <EckenEditor key={seite.id + ':' + seite.src.width} seite={seite} onEcken={(ecken) => aendern({ ecken })} />
          ) : (
            <Ergebnis seite={seite} />
          )}
          {ansicht === 'zuschnitt' && (
            <p className="text-[13px] text-ink/60">Ziehe die vier Ecken auf die Ecken des Belegs. Tab zieht ihn dann gerade.</p>
          )}

          <SchalterZeile
            titel="Als Dokument aufbereiten"
            hinweis="Schatten weg, Graustufen, mehr Kontrast — gut lesbar und besser für die Texterkennung."
            checked={seite.dokument}
            onChange={(v) => aendern({ dokument: v })}
          />

          {seiten.length > 1 && (
            <div className="flex items-center gap-2 overflow-x-auto pb-1" aria-label="Seiten">
              {seiten.map((s, i) => (
                <Vorschaubild key={s.id} seite={s} nr={i + 1} aktiv={i === aktiv} onClick={() => setAktiv(i)} />
              ))}
              <div className="ml-auto flex shrink-0 gap-1">
                <button type="button" className="btn-ghost btn-sm" onClick={() => verschieben(-1)} disabled={aktiv === 0}>
                  ← Früher
                </button>
                <button
                  type="button"
                  className="btn-ghost btn-sm"
                  onClick={() => verschieben(1)}
                  disabled={aktiv === seiten.length - 1}
                >
                  Später →
                </button>
              </div>
            </div>
          )}

          <label className="block">
            <span className="field-label">Bezeichnung (optional)</span>
            <input
              className="input"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="z. B. Tankquittung Aral"
              maxLength={80}
            />
          </label>
        </div>
      ) : (
        <div className="flex min-h-[200px] items-center justify-center text-ink/60">
          {laedt > 0 ? <Spinner /> : 'Keine Seite aufgenommen.'}
        </div>
      )}

      <DialogFuss
        links={
          <>
            <button type="button" className="btn-ghost gap-1.5" onClick={() => kamera.current?.click()} disabled={busy}>
              <IconCamera className="h-[18px] w-[18px]" /> Weitere Seite
            </button>
            <button type="button" className="btn-ghost gap-1.5" onClick={() => galerie.current?.click()} disabled={busy}>
              <IconImage className="h-[18px] w-[18px]" /> Aus Fotos
            </button>
          </>
        }
      >
        <button type="button" className="btn-ghost" onClick={onClose} disabled={busy}>
          Abbrechen
        </button>
        <button type="button" className="btn-primary gap-2" onClick={speichern} disabled={busy || leer || laedt > 0}>
          {busy ? <Spinner size="sm" /> : null}
          {busy ? 'Wird gespeichert…' : seiten.length > 1 ? `${seiten.length} Seiten speichern` : 'Speichern'}
        </button>
      </DialogFuss>
    </Modal>
  );
}

// Foto mit verschiebbaren Ecken. Gezeichnet wird eine verkleinerte Fassung (schnell),
// die Ecken sind relativ (0..1) und gelten für das volle Arbeitsbild.
function EckenEditor({ seite, onEcken }) {
  const bild = useRef(null);
  const flaeche = useRef(null);
  const [ziehe, setZiehe] = useState(null);
  const { src, ecken } = seite;
  const f = Math.min(1, 900 / Math.max(src.width, src.height));
  const w = Math.round(src.width * f);
  const h = Math.round(src.height * f);

  useEffect(() => {
    const c = bild.current;
    c.width = w;
    c.height = h;
    const ctx = c.getContext('2d');
    ctx.imageSmoothingQuality = 'high';
    ctx.drawImage(src, 0, 0, w, h);
  }, [src, w, h]);

  function punkt(e) {
    const r = flaeche.current.getBoundingClientRect();
    return [Math.min(1, Math.max(0, (e.clientX - r.left) / r.width)), Math.min(1, Math.max(0, (e.clientY - r.top) / r.height))];
  }

  function runter(i, e) {
    e.preventDefault();
    e.currentTarget.setPointerCapture?.(e.pointerId);
    setZiehe(i);
  }

  function bewegen(e) {
    if (ziehe === null) return;
    const neu = ecken.map((p, i) => (i === ziehe ? punkt(e) : p));
    onEcken(neu);
  }

  // Griffgröße in Bildpunkten der Zeichenfläche, damit sie auf dem Handy ~44 px groß wirkt.
  const r = Math.max(w, h) * 0.035;
  const pts = ecken.map(([x, y]) => [x * w, y * h]);

  return (
    <div className="flex justify-center rounded-xl bg-ink/[0.06] p-2">
      <div ref={flaeche} className="relative" style={{ aspectRatio: `${w} / ${h}`, maxHeight: '58vh', width: '100%', maxWidth: `calc(58vh * ${w / h})` }}>
        <canvas ref={bild} className="absolute inset-0 h-full w-full rounded-md" aria-label="Foto der Seite" />
        <svg
          viewBox={`0 0 ${w} ${h}`}
          className="absolute inset-0 h-full w-full touch-none select-none"
          onPointerMove={bewegen}
          onPointerUp={() => setZiehe(null)}
          onPointerCancel={() => setZiehe(null)}
        >
          <path
            d={`M0 0H${w}V${h}H0Z M${pts.map((p) => p.join(' ')).join(' L')} Z`}
            fill="rgba(22,26,36,0.45)"
            fillRule="evenodd"
          />
          <polygon points={pts.map((p) => p.join(',')).join(' ')} fill="none" stroke="#2947c9" strokeWidth={Math.max(2, r * 0.18)} />
          {pts.map(([x, y], i) => (
            <g key={i} onPointerDown={(e) => runter(i, e)} className="cursor-grab">
              <circle cx={x} cy={y} r={r * 1.6} fill="transparent" />
              <circle cx={x} cy={y} r={r * 0.6} fill="#ffffff" stroke="#2947c9" strokeWidth={Math.max(2, r * 0.22)} />
            </g>
          ))}
        </svg>
      </div>
    </div>
  );
}

// Fertige Seite in Vorschau-Größe (gleiche Rechnung wie beim Speichern, nur kleiner).
function Ergebnis({ seite }) {
  const ref = useRef(null);
  const [rechnet, setRechnet] = useState(true);
  useEffect(() => {
    let aktiv = true;
    setRechnet(true);
    const t = setTimeout(() => {
      if (!aktiv) return;
      const c = verarbeite(seite.src, seite.ecken, seite.dokument, 1100);
      const ziel = ref.current;
      if (!ziel) return;
      ziel.width = c.width;
      ziel.height = c.height;
      ziel.getContext('2d').drawImage(c, 0, 0);
      setRechnet(false);
    }, 30);
    return () => {
      aktiv = false;
      clearTimeout(t);
    };
  }, [seite.src, seite.ecken, seite.dokument]);
  return (
    <div className="relative flex justify-center rounded-xl bg-ink/[0.06] p-2">
      <canvas ref={ref} className="max-h-[58vh] max-w-full rounded-md bg-paper shadow-sm" aria-label="Ergebnis der Seite" />
      {rechnet && (
        <div className="absolute inset-0 flex items-center justify-center">
          <Spinner />
        </div>
      )}
    </div>
  );
}

function Vorschaubild({ seite, nr, aktiv, onClick }) {
  const ref = useRef(null);
  useEffect(() => {
    const c = ref.current;
    const f = 64 / Math.max(seite.src.width, seite.src.height);
    c.width = Math.round(seite.src.width * f);
    c.height = Math.round(seite.src.height * f);
    c.getContext('2d').drawImage(seite.src, 0, 0, c.width, c.height);
  }, [seite.src]);
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={`Seite ${nr}`}
      aria-current={aktiv ? 'true' : undefined}
      className={`relative flex h-[72px] w-[60px] shrink-0 items-center justify-center rounded-lg bg-ink/[0.06] outline-none focus-visible:ring-2 focus-visible:ring-royal/40
        ${aktiv ? 'ring-2 ring-royal' : ''}`}
    >
      <canvas ref={ref} className="max-h-[64px] max-w-[52px]" />
      <span className="absolute bottom-0.5 right-1 text-[11px] font-bold tabular-nums text-ink/70">{nr}</span>
    </button>
  );
}
