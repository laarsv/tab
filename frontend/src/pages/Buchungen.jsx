import { useMemo, useEffect, useRef, useState } from 'react';
import { useOutletContext, useSearchParams } from 'react-router-dom';
import toast from 'react-hot-toast';
import { api, apiError } from '../api/client.js';
import BuchungModal from '../components/BuchungModal.jsx';
import Dropdown from '../components/Dropdown.jsx';
import {
  IconArrowIn,
  IconArrowOut,
  IconArrowRight,
  IconBookIn,
  IconButton,
  IconChevronDown,
  IconClock,
  IconCode,
  IconCopy,
  IconFileText,
  IconImage,
  IconMove,
  IconPencil,
  IconPlus,
  IconTrash,
  IconUpload,
} from '../components/Icons.jsx';
import { Leer, PageHeader, Row, SectionHead } from '../components/PageParts.jsx';
import { PageSpinner } from '../components/Spinner.jsx';
import { openBeleg, fileSize, belegTyp, ACCEPT } from '../lib/belege.js';
import { formatEuro, formatDateDE, todayISO } from '../lib/format.js';

const MONATE = [
  'Januar', 'Februar', 'März', 'April', 'Mai', 'Juni',
  'Juli', 'August', 'September', 'Oktober', 'November', 'Dezember',
];

// „Rechnung 2026-0003 – Lisa Dietrich" (aus dem Rechnungsmodul vorbefüllt) → Herkunft + kleine Nummer.
function herkunft(beschreibung) {
  const m = /^Rechnung\s+(\S+)\s+[–-]\s+(.+)$/.exec(beschreibung || '');
  return m ? { titel: m[2], nummer: m[1] } : { titel: beschreibung || '', nummer: null };
}

// ISO-Datum → „24.10." (das Jahr steht im Monatskopf).
function kurz(iso) {
  return `${iso.slice(8, 10)}.${iso.slice(5, 7)}.`;
}

function NoGewerbe() {
  return <Leer>Kein Gewerbe gewählt. Lege unter „Gewerbe" zuerst ein Gewerbe an.</Leer>;
}

const PUNKT = (
  <span aria-hidden="true" className="text-ink/45">
    ·
  </span>
);

// Fälligkeit des Eingangs-Belegs: leise Zustandszeile, Klick öffnet das Datumsfeld.
function FaelligZeile({ beleg, ueberfaellig, onChange }) {
  const [edit, setEdit] = useState(false);
  if (edit) {
    return (
      <input
        type="date"
        autoFocus
        aria-label="Fällig am"
        className="input !w-[148px] !py-0.5 !text-xs"
        value={beleg.faellig_am || ''}
        onChange={(e) => onChange(e.target.value)}
        onBlur={() => setEdit(false)}
      />
    );
  }
  return (
    <button
      type="button"
      onClick={() => setEdit(true)}
      title="Fällig am (optional) — wann muss die Rechnung bezahlt sein?"
      className={`inline-flex items-center gap-1 rounded hover:underline ${ueberfaellig ? 'font-bold text-red-700' : ''}`}
    >
      <IconClock className="h-3.5 w-3.5" />
      {beleg.faellig_am
        ? ueberfaellig
          ? `Überfällig seit ${kurz(beleg.faellig_am)}`
          : `fällig ${formatDateDE(beleg.faellig_am)}`
        : 'Fälligkeit setzen'}
    </button>
  );
}

function belegIcon(b) {
  const typ = belegTyp(b);
  return typ === 'bild' ? IconImage : typ === 'xml' ? IconCode : IconFileText;
}

export default function Buchungen() {
  const { gewerbeId, jahr, gewerbe, reloadBadges, uploadBelege, uploading, eingangTick } = useOutletContext();
  const aktives = (gewerbe || []).find((g) => String(g.id) === String(gewerbeId));
  const andereGewerbe = (gewerbe || []).filter((g) => String(g.id) !== String(gewerbeId) && g.aktiv);
  const [kategorien, setKategorien] = useState([]);
  const [items, setItems] = useState([]);
  const [belege, setBelege] = useState([]); // offener Beleg-Eingang
  const [kennzahlen, setKennzahlen] = useState(null);
  const [loading, setLoading] = useState(true);
  const [modal, setModal] = useState(null); // { buchung? } | null
  const [verbuchen, setVerbuchen] = useState(null); // einzelner Eingangs-Beleg
  const [wizard, setWizard] = useState(null); // { queue: beleg[], i } — Abarbeiten-Modus
  const [query, setQuery] = useState('');
  const [filterKat, setFilterKat] = useState('');
  const [filterMonat, setFilterMonat] = useState('');
  const [importing, setImporting] = useState(false);
  const [wizardAngefordert, setWizardAngefordert] = useState(false);
  const geladen = useRef(false); // Spinner nur beim ersten Laden — spätere Reloads lassen offene Fenster stehen
  const importRef = useRef(null);
  const uploadRef = useRef(null);

  async function load() {
    if (!gewerbeId) {
      setLoading(false);
      return;
    }
    if (!geladen.current) setLoading(true);
    try {
      const [kat, buch, kenn, bel] = await Promise.all([
        api.get('/api/kategorien', { params: { jahr } }),
        api.get('/api/buchungen', { params: { gewerbe_id: gewerbeId, jahr } }),
        api.get('/api/kennzahlen', { params: { gewerbe_id: gewerbeId, jahr } }),
        api.get('/api/belege', { params: { gewerbe_id: gewerbeId, status: 'offen' } }),
      ]);
      setKategorien(kat.data);
      setItems(buch.data);
      setKennzahlen(kenn.data);
      setBelege(bel.data);
      geladen.current = true;
      reloadBadges?.();
    } catch (e) {
      toast.error(apiError(e));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    geladen.current = false;
    load();
  }, [gewerbeId, jahr]); // eslint-disable-line react-hooks/exhaustive-deps

  // Der Eingang wuchs von außen (Hochladen über die Seitenleiste).
  useEffect(() => {
    if (eingangTick) load();
  }, [eingangTick]); // eslint-disable-line react-hooks/exhaustive-deps

  // Aufrufe von außen per URL: ?geteilt=ok|fehler (PWA-Share, Service Worker),
  // ?neu=… („Neue Buchung" in der Seitenleiste), ?abarbeiten=… („Jetzt abarbeiten").
  const [searchParams, setSearchParams] = useSearchParams();
  useEffect(() => {
    let geaendert = false;
    const g = searchParams.get('geteilt');
    if (g) {
      if (g === 'ok') toast.success('Beleg(e) vom Handy in den Eingang übernommen.');
      else toast.error('Teilen fehlgeschlagen — Beleg bitte manuell hochladen.');
      searchParams.delete('geteilt');
      geaendert = true;
    }
    if (searchParams.get('neu')) {
      setModal({});
      searchParams.delete('neu');
      geaendert = true;
    }
    if (searchParams.get('abarbeiten')) {
      setWizardAngefordert(true);
      searchParams.delete('abarbeiten');
      geaendert = true;
    }
    if (geaendert) setSearchParams(searchParams, { replace: true });
  }, [searchParams]); // eslint-disable-line react-hooks/exhaustive-deps

  // „Jetzt abarbeiten" aus der Seitenleiste: Wizard starten, sobald die Belege geladen sind.
  useEffect(() => {
    if (!wizardAngefordert || loading) return;
    setWizardAngefordert(false);
    if (belege.length > 0) setWizard({ queue: belege, i: 0 });
    else toast('Der Beleg-Eingang ist leer.');
  }, [wizardAngefordert, loading, belege]);

  async function remove(id) {
    if (!window.confirm('Diese Buchung wirklich löschen? Angehängte Belege wandern zurück in den Eingang.'))
      return;
    try {
      await api.delete(`/api/buchungen/${id}`);
      toast.success('Gelöscht.');
      await load();
    } catch (e) {
      toast.error(apiError(e));
    }
  }

  function duplicate(b) {
    // Kopie ohne id/datum: Modal startet als „Neue Buchung" mit heutigem Datum.
    setModal({
      buchung: {
        beschreibung: b.beschreibung,
        positionen: b.positionen.map((p) => ({
          kategorie_id: p.kategorie_id,
          betrag_cent: p.betrag_cent,
          beleg_details: p.beleg_details,
        })),
      },
    });
  }

  // ── Beleg-Eingang (integriert) ─────────────────────────────────────────────
  // Hochladen steckt im Layout (Seitenleiste + diese Seite teilen es); danach lädt eingangTick neu.
  async function onUploadChosen(e) {
    const files = Array.from(e.target.files || []);
    if (files.length) await uploadBelege(files);
    if (uploadRef.current) uploadRef.current.value = '';
  }

  async function removeBeleg(b) {
    if (!window.confirm(`Beleg „${b.original_name}" endgültig löschen?`)) return;
    try {
      await api.delete(`/api/belege/${b.id}`);
      await load();
    } catch (e) {
      toast.error(apiError(e));
    }
  }

  async function setFaellig(b, datum) {
    try {
      await api.patch(`/api/belege/${b.id}`, { faellig_am: datum || null });
      await load();
    } catch (e) {
      toast.error(apiError(e));
    }
  }

  async function verschiebeBeleg(b, zielGewerbeId) {
    try {
      await api.patch(`/api/belege/${b.id}`, { gewerbe_id: Number(zielGewerbeId) });
      const ziel = andereGewerbe.find((g) => String(g.id) === String(zielGewerbeId));
      toast.success(`Beleg nach „${ziel?.name || 'anderes Gewerbe'}" verschoben.`);
      await load();
    } catch (e) {
      toast.error(apiError(e));
    }
  }

  function startWizard() {
    setWizard({ queue: belege, i: 0 });
  }
  function advanceWizard(queue, i) {
    if (i + 1 < queue.length) {
      setWizard({ queue, i: i + 1 });
    } else {
      setWizard(null);
      toast.success('Alle Belege abgearbeitet. 🎉');
    }
  }

  async function importCsv(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    setImporting(true);
    try {
      const form = new FormData();
      form.append('file', file);
      form.append('gewerbe_id', gewerbeId);
      const res = await api.post('/api/buchungen/import', form);
      toast.success(`${res.data.angelegt} Buchungen importiert.`);
      await load();
    } catch (err) {
      toast.error(apiError(err, 'Import fehlgeschlagen.'), { duration: 10000 });
    } finally {
      setImporting(false);
      if (importRef.current) importRef.current.value = '';
    }
  }

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return items.filter((b) => {
      if (filterMonat && b.datum.slice(5, 7) !== filterMonat) return false;
      if (filterKat && !b.positionen.some((p) => String(p.kategorie_id) === filterKat)) return false;
      if (!q) return true;
      const haystack = [
        b.beschreibung,
        formatDateDE(b.datum),
        ...b.positionen.flatMap((p) => [p.kategorie_name, p.beleg_details, formatEuro(p.betrag_cent)]),
      ]
        .filter(Boolean)
        .join(' ')
        .toLowerCase();
      return haystack.includes(q);
    });
  }, [items, query, filterKat, filterMonat]);

  // Nach Monat gruppieren (die Liste kommt neueste zuerst).
  const gruppen = useMemo(() => {
    const m = new Map();
    for (const b of filtered) {
      const k = b.datum.slice(0, 7);
      if (!m.has(k)) m.set(k, []);
      m.get(k).push(b);
    }
    return [...m.entries()];
  }, [filtered]);

  const hasFilter = query.trim() || filterKat || filterMonat;

  const katOptions = useMemo(
    () => [
      { value: '', label: 'Alle Kategorien' },
      ...kategorien.filter((k) => !k.ist_afa).map((k) => ({ value: String(k.id), label: k.name })),
    ],
    [kategorien],
  );
  const monatOptions = useMemo(
    () => [
      { value: '', label: 'Alle Monate' },
      ...MONATE.map((m, i) => ({ value: String(i + 1).padStart(2, '0'), label: m })),
    ],
    [],
  );

  if (!gewerbeId) return <NoGewerbe />;
  if (loading) return <PageSpinner />;

  const heute = todayISO();
  const besteuerung = aktives?.besteuerung === 'regelbesteuerung' ? 'Regelbesteuerung' : 'Kleinunternehmer';

  return (
    <div>
      <PageHeader
        title="Buchungen"
        accent={jahr}
        sub={`${aktives?.name || 'Gewerbe'} · ${besteuerung} · ${items.length} ${items.length === 1 ? 'Buchung' : 'Buchungen'}`}
      >
        <IconButton
          icon={IconUpload}
          label="CSV-Import"
          title="CSV-Import — Semikolon-CSV: Datum;Betrag;Kategorie;Beschreibung;Beleg-Details; Datum TT.MM.JJJJ, Betrag 12,34, Kategorie als Name oder Key."
          onClick={() => importRef.current?.click()}
          disabled={importing}
          className="hidden sm:inline-flex"
        />
        <input ref={importRef} type="file" accept=".csv,text/csv" className="hidden" onChange={importCsv} />
        <button className="btn-primary lg:hidden" onClick={() => setModal({})}>
          <IconPlus className="mr-1 h-4 w-4" /> Buchung
        </button>
      </PageHeader>

      {kennzahlen && (
        <div className="mt-4">
          <KuGuard k={kennzahlen} />
        </div>
      )}

      {kennzahlen && (
        <div className="mt-6 grid grid-cols-3 border-y border-ink/[0.08]">
          <Kennzahl label="Einnahmen" cent={kennzahlen.einnahmen_cent} royal />
          <Kennzahl label="Ausgaben" cent={kennzahlen.ausgaben_cent} />
          <Kennzahl
            label="Saldo"
            cent={kennzahlen.einnahmen_cent - kennzahlen.ausgaben_cent}
            hint="vor AfA und Abzugsquoten"
          />
        </div>
      )}

      {/* Beleg-Eingang: sammeln, später verbuchen — integriert statt eigener Seite */}
      <SectionHead label="Beleg-Eingang" count={belege.length}>
        {belege.length > 0 && (
          <button
            type="button"
            onClick={startWizard}
            className="inline-flex items-center gap-1.5 rounded-lg px-2 py-2 text-sm font-bold text-royal outline-none hover:bg-royal/10 focus-visible:ring-2 focus-visible:ring-royal/40 sm:py-1"
          >
            <IconArrowRight className="h-4 w-4" /> Jetzt abarbeiten
          </button>
        )}
        <IconButton
          icon={IconUpload}
          label="Belege hochladen"
          onClick={() => uploadRef.current?.click()}
          disabled={uploading}
        />
        <input ref={uploadRef} type="file" accept={ACCEPT} multiple className="hidden" onChange={onUploadChosen} />
      </SectionHead>
      {belege.length === 0 ? (
        <p className="border-b border-ink/[0.08] py-3 text-sm text-ink/60">
          Leer. Belege (PDF/JPG/PNG, E-Rechnungs-XML) hochladen und später in Ruhe verbuchen.
        </p>
      ) : (
        belege.map((b) => {
          const ueberfaellig = b.faellig_am && b.faellig_am < heute;
          return (
            <Row
              key={b.id}
              kind={ueberfaellig ? 'neg' : 'file'}
              icon={belegIcon(b)}
              title={b.original_name}
              onTitleClick={() => openBeleg(b.id)}
              titleHint={`${b.original_name} — ansehen`}
              sub={
                <>
                  <span>
                    Hochgeladen {kurz(b.created_at.slice(0, 10))} · {fileSize(b.size_bytes)}
                  </span>
                  {PUNKT}
                  <FaelligZeile beleg={b} ueberfaellig={ueberfaellig} onChange={(d) => setFaellig(b, d)} />
                </>
              }
              actions={
                <>
                  <IconButton icon={IconBookIn} variant="primary" label="Verbuchen" onClick={() => setVerbuchen(b)} />
                  {andereGewerbe.length > 0 && (
                    <Dropdown
                      variant="icon"
                      icon={IconMove}
                      label="In ein anderes Gewerbe verschieben"
                      value=""
                      options={andereGewerbe.map((g) => ({ value: String(g.id), label: `→ ${g.name}` }))}
                      onChange={(v) => verschiebeBeleg(b, v)}
                    />
                  )}
                  <IconButton icon={IconTrash} variant="danger" label="Beleg löschen" onClick={() => removeBeleg(b)} />
                </>
              }
            />
          );
        })
      )}

      {items.length > 0 && <KategorieSummen items={items} jahr={jahr} />}

      {items.length > 0 && (
        <div className="mt-8 flex flex-col gap-2 sm:flex-row">
          <input
            className="input sm:max-w-xs"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Suchen (Beschreibung, Kategorie, Betrag)…"
          />
          <Dropdown value={filterKat} onChange={(v) => setFilterKat(String(v))} options={katOptions} variant="ghost" />
          <Dropdown value={filterMonat} onChange={(v) => setFilterMonat(String(v))} options={monatOptions} variant="ghost" />
          {hasFilter && (
            <button
              className="btn-ghost btn-sm self-start sm:self-center"
              onClick={() => {
                setQuery('');
                setFilterKat('');
                setFilterMonat('');
              }}
            >
              Zurücksetzen ({filtered.length}/{items.length})
            </button>
          )}
        </div>
      )}

      {items.length === 0 ? (
        <Leer>Keine Buchungen für {jahr}. Tipp: Altdaten aus der Excel-Liste per CSV-Import übernehmen.</Leer>
      ) : filtered.length === 0 ? (
        <Leer>Keine Treffer für die aktuelle Suche/Filter.</Leer>
      ) : (
        gruppen.map(([monat, liste]) => (
          <section key={monat} aria-label={`${MONATE[Number(monat.slice(5, 7)) - 1]} ${monat.slice(0, 4)}`}>
            <SectionHead label={`${MONATE[Number(monat.slice(5, 7)) - 1]} ${monat.slice(0, 4)}`} count={liste.length} />
            {liste.map((b) => {
              const { titel, nummer } = herkunft(b.beschreibung);
              const einzel = b.positionen.length === 1;
              const typen = new Set(b.positionen.map((p) => p.kategorie_typ));
              const typ = typen.size === 1 ? [...typen][0] : null; // gemischt → Summe ohne Vorzeichen
              // Ohne Beschreibung ist die Kategorie die einzige Herkunft → nicht doppelt zeigen.
              const hauptzeile = titel || (einzel ? b.positionen[0].kategorie_name : `${b.positionen.length} Positionen`);
              return (
                <Row
                  key={b.id}
                  kind={typ === 'einnahme' ? 'in' : 'out'}
                  icon={typ === 'einnahme' ? IconArrowIn : IconArrowOut}
                  title={hauptzeile}
                  onTitleClick={() => setModal({ buchung: b })}
                  titleHint="Bearbeiten"
                  sub={
                    <>
                      <span className="tabular-nums">{kurz(b.datum)}</span>
                      {einzel && titel && (
                        <>
                          {PUNKT}
                          <span>{b.positionen[0].kategorie_name}</span>
                        </>
                      )}
                      {!einzel && (
                        <>
                          {PUNKT}
                          <span>
                            {b.positionen
                              .map(
                                (p) =>
                                  `${p.kategorie_name} ${p.kategorie_typ === 'einnahme' ? '+' : '−'}${formatEuro(p.betrag_cent)}`,
                              )
                              .join(' · ')}
                          </span>
                        </>
                      )}
                      {nummer && (
                        <>
                          {PUNKT}
                          <span className="tabular-nums">Rechnung {nummer}</span>
                        </>
                      )}
                      {b.beleg_count > 0 && <Paperclip count={b.beleg_count} />}
                    </>
                  }
                  amount={`${typ ? (typ === 'einnahme' ? '+' : '−') : ''}${formatEuro(b.summe_cent)}`}
                  amountIn={typ === 'einnahme'}
                  actions={
                    <>
                      <IconButton icon={IconPencil} label="Bearbeiten" onClick={() => setModal({ buchung: b })} />
                      <IconButton icon={IconCopy} label="Duplizieren" onClick={() => duplicate(b)} />
                      <IconButton icon={IconTrash} variant="danger" label="Löschen" onClick={() => remove(b.id)} />
                    </>
                  }
                />
              );
            })}
          </section>
        ))
      )}

      {modal && (
        <BuchungModal
          buchung={modal.buchung}
          gewerbeId={gewerbeId}
          jahr={jahr}
          kategorien={kategorien}
          onClose={() => setModal(null)}
          onSaved={load}
        />
      )}

      {verbuchen && (
        <BuchungModal
          preBelege={[verbuchen]}
          gewerbeId={gewerbeId}
          jahr={jahr}
          kategorien={kategorien}
          onClose={() => setVerbuchen(null)}
          onSaved={load}
        />
      )}

      {wizard && (
        <BuchungModal
          key={wizard.queue[wizard.i].id}
          preBelege={[wizard.queue[wizard.i]]}
          gewerbeId={gewerbeId}
          jahr={jahr}
          kategorien={kategorien}
          wizard={{
            pos: wizard.i + 1,
            total: wizard.queue.length,
            onSkip: () => advanceWizard(wizard.queue, wizard.i),
          }}
          onClose={() => setWizard(null)}
          onSaved={async () => {
            // onClose läuft im Modal vor onSaved (setzt wizard=null) — hier mit den
            // eingefangenen Werten weiterschalten, damit der Wizard nicht abbricht.
            await load();
            advanceWizard(wizard.queue, wizard.i);
          }}
        />
      )}
    </div>
  );
}

function Paperclip({ count }) {
  return (
    <span className="inline-flex items-center gap-1 align-middle text-xs text-ink/60" title={`${count} Beleg(e)`}>
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-3.5 w-3.5">
        <path d="M21.44 11.05l-9.19 9.19a6 6 0 01-8.49-8.49l9.19-9.19a4 4 0 015.66 5.66l-9.2 9.19a2 2 0 01-2.83-2.83l8.49-8.48" />
      </svg>
      <span className="tabular-nums">{count}</span>
    </span>
  );
}

function Kennzahl({ label, cent, hint, royal = false }) {
  return (
    <div className="border-l border-ink/[0.08] py-3 pl-3 first:border-l-0 first:pl-0 sm:pl-6 sm:first:pl-0">
      <div className="text-[11px] font-bold uppercase tracking-[0.1em] text-ink/60 sm:text-xs">{label}</div>
      <div
        className={`text-lg font-black leading-tight tabular-nums tracking-tight sm:text-[26px] ${royal ? 'text-royal' : ''}`}
      >
        {formatEuro(cent)}
      </div>
      {hint && <div className="mt-0.5 hidden text-[11px] leading-snug text-ink/60 sm:block">{hint}</div>}
    </div>
  );
}

// „Wohin ging das Geld" — Summen je Kategorie (das Pivot der Excel-Liste).
function KategorieSummen({ items, jahr }) {
  const [open, setOpen] = useState(false);
  const summen = useMemo(() => {
    const map = new Map();
    for (const b of items) {
      for (const p of b.positionen) {
        const cur = map.get(p.kategorie_name) || { name: p.kategorie_name, typ: p.kategorie_typ, cent: 0, anzahl: 0 };
        cur.cent += p.betrag_cent;
        cur.anzahl += 1;
        map.set(p.kategorie_name, cur);
      }
    }
    const list = [...map.values()].sort((a, b) => b.cent - a.cent);
    return {
      einnahmen: list.filter((s) => s.typ === 'einnahme'),
      ausgaben: list.filter((s) => s.typ === 'ausgabe'),
    };
  }, [items]);

  const maxCent = Math.max(1, ...summen.einnahmen.map((s) => s.cent), ...summen.ausgaben.map((s) => s.cent));

  return (
    <div className="mt-8">
      <button
        type="button"
        aria-expanded={open}
        className="flex w-full items-center gap-2.5 text-left"
        onClick={() => setOpen((o) => !o)}
      >
        <span className="eyebrow">Summen je Kategorie {jahr}</span>
        <IconChevronDown className={`h-4 w-4 text-ink/60 transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>
      {open && (
        <div className="mt-2 grid grid-cols-1 gap-x-8 gap-y-1 md:grid-cols-2">
          {[
            ['Einnahmen', summen.einnahmen],
            ['Ausgaben', summen.ausgaben],
          ].map(([label, list]) => (
            <div key={label}>
              <div className="text-xs font-bold text-ink/50 uppercase tracking-wider py-1">{label}</div>
              {list.length === 0 ? (
                <div className="text-sm text-ink/40 py-1">—</div>
              ) : (
                list.map((s) => (
                  <div key={s.name} className="py-1.5">
                    <div className="flex items-baseline justify-between gap-3 text-sm">
                      <span className="truncate">
                        {s.name} <span className="text-ink/40 text-xs">× {s.anzahl}</span>
                      </span>
                      <span className="tabular-nums whitespace-nowrap font-medium">{formatEuro(s.cent)}</span>
                    </div>
                    <div className="h-1 rounded-full bg-ink/5 mt-1">
                      <div
                        className={`h-1 rounded-full ${s.typ === 'einnahme' ? 'bg-royal' : 'bg-royal-soft'}`}
                        style={{ width: `${Math.max(2, (s.cent / maxCent) * 100)}%` }}
                      />
                    </div>
                  </div>
                ))
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function KuGuard({ k }) {
  if (k.ku_warn_laufend) {
    return (
      <div className="p-4 rounded flex items-start gap-3 bg-red-50 border-l-4 border-red-500 text-red-900">
        <div>
          <div className="font-bold">Kleinunternehmer-Grenze gerissen</div>
          <div className="text-sm mt-0.5">
            Die KU-relevanten Einnahmen {formatEuro(k.ku_umsatz_cent)} (ohne steuerfreie Courtage und
            Anlagenverkäufe, §19 Abs. 2 UStG) überschreiten die laufende Grenze von{' '}
            {formatEuro(k.ku_grenze_laufend_cent)}. Der KU-Status entfällt — bitte Steuerberater
            kontaktieren. Tab deckt die Regelbesteuerung nicht ab.
          </div>
        </div>
      </div>
    );
  }
  if (k.ku_warn_vorjahr) {
    return (
      <div className="p-4 rounded flex items-start gap-3 bg-yellow-100 text-yellow-900">
        <div>
          <div className="font-bold">Vorjahresgrenze überschritten</div>
          <div className="text-sm mt-0.5">
            Die KU-relevanten Einnahmen {formatEuro(k.ku_umsatz_cent)} (ohne steuerfreie Courtage und
            Anlagenverkäufe) liegen über {formatEuro(k.ku_grenze_vorjahr_cent)}. Für das Folgejahr ggf.
            kein KU mehr — im Blick behalten, im Zweifel Steuerberater fragen.
          </div>
        </div>
      </div>
    );
  }
  return null;
}
