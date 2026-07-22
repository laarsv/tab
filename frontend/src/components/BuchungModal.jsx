import { useEffect, useMemo, useState } from 'react';
import toast from 'react-hot-toast';
import { api, apiError } from '../api/client.js';
import Dropdown from './Dropdown.jsx';
import Modal from './Modal.jsx';
import BelegeManager from './BelegeManager.jsx';
import { openBeleg } from '../lib/belege.js';
import { formatEuro, parseEuroToCent, centToInput, todayISO } from '../lib/format.js';

const BELEG_PLACEHOLDER = {
  bewirtung: 'Pflichtangaben: Ort, Tag, Teilnehmer, Anlass (ab 150 € mit Namen).',
  geschenke: 'Pflichtangaben: Empfänger (Name), Anlass.',
};

// Zahl mit Komma oder Punkt -> number, sonst null.
function num(v) {
  if (v === '' || v === null || v === undefined) return null;
  const n = Number(String(v).replace(',', '.'));
  return Number.isFinite(n) ? n : null;
}

// Rechner-Helfer je Kategorie: füllen das Betragsfeld, das Betragsfeld bleibt
// die Quelle der Wahrheit (Backend speichert nur den Betrag).
const CALCULATORS = {
  fahrtkosten_kfz: {
    fields: [{ key: 'km', label: 'Kilometer', placeholder: 'z. B. 120' }],
    hint: 'km × 0,30 €',
    compute: (c) => {
      const km = num(c.km);
      return km !== null && km > 0 ? Math.round(km * 30) : null;
    },
  },
  wege_wohnung_betrieb: {
    fields: [
      { key: 'tage', label: 'Arbeitstage', placeholder: 'z. B. 120' },
      { key: 'km', label: 'Entfernungs-km (einfach)', placeholder: 'z. B. 25' },
    ],
    hint: 'Tage × (km 1–20 × 0,30 € · ab km 21 × 0,38 €)',
    compute: (c) => {
      const tage = num(c.tage);
      const km = num(c.km);
      if (tage === null || km === null || tage <= 0 || km <= 0) return null;
      const proTag = Math.min(km, 20) * 30 + Math.max(km - 20, 0) * 38;
      return Math.round(tage * proTag);
    },
  },
  arbeitszimmer: {
    fields: [{ key: 'monate', label: 'Monate mit Arbeitszimmer', placeholder: '12' }],
    hint: 'Jahrespauschale: 105 €/Monat (max. 1.260 €/Jahr). Tatsächliche Kosten? Betrag direkt eintragen.',
    compute: (c) => {
      const monate = num(c.monate);
      return monate !== null && monate > 0 ? Math.round(Math.min(monate, 12) * 105_00) : null;
    },
  },
  homeoffice_pauschale: {
    fields: [{ key: 'tage', label: 'Homeoffice-Tage', placeholder: 'z. B. 180' }],
    hint: 'Tage × 6 € (max. 210 Tage = 1.260 €/Jahr)',
    compute: (c) => {
      const tage = num(c.tage);
      return tage !== null && tage > 0 ? Math.round(tage * 600) : null;
    },
  },
  kfz_privatnutzung: {
    fields: [
      { key: 'listenpreis', label: 'Bruttolistenpreis (€)', placeholder: 'z. B. 42.300' },
      {
        key: 'satz',
        label: 'Antrieb',
        type: 'select',
        default: '1',
        options: [
          { value: '1', label: 'Verbrenner — 1 %' },
          { value: '0.5', label: 'Plug-in-Hybrid — 0,5 %' },
          { value: '0.25', label: 'E-Auto — 0,25 %' },
        ],
      },
      { key: 'monate', label: 'Monate', placeholder: '12' },
    ],
    hint: 'Satz × Listenpreis (auf volle 100 € abgerundet), je Monat',
    compute: (c) => {
      const lpCent = parseEuroToCent(c.listenpreis);
      const monate = num(c.monate);
      const satz = Number(c.satz || '1');
      if (!lpCent || lpCent <= 0 || monate === null || monate <= 0) return null;
      // Bemessungsgrundlage: ggf. hälftiger/viertel Listenpreis, auf volle 100 € abgerundet;
      // davon 1 % je Monat.
      const basisCent = Math.floor((lpCent * satz) / 100_00) * 100_00;
      return Math.round((basisCent / 100) * monate);
    },
  },
  verpflegungsmehraufwand: {
    fields: [
      { key: 'voll', label: 'Volle Tage (24 h)', placeholder: '0' },
      { key: 'teil', label: 'An-/Abreisetage (> 8 h)', placeholder: '0' },
    ],
    hint: '28 €/voller Tag · 14 €/An-/Abreisetag',
    compute: (c) => {
      const voll = num(c.voll) ?? 0;
      const teil = num(c.teil) ?? 0;
      if (voll <= 0 && teil <= 0) return null;
      return Math.round(voll * 2800 + teil * 1400);
    },
  },
};

const GESCHENKE_GRENZE_CENT = 50_00;
const HOMEOFFICE_MAX_CENT = 1260_00;

function emptyPos() {
  return { kategorie_id: '', betragInput: '', calc: {}, beleg_details: '' };
}

// Gemeinsames Modal für Buchungen (Beleg-Kopf + 1..n Positionen).
// preBelege: Eingangs-Belege, die beim Anlegen verknüpft werden.
// presetKategorieId/-BetragCent/-Beschreibung: starten die neue Buchung vorausgefüllt
// (Jahres-Check, Fahrten-Liste). wizard: { pos, total, onSkip } — Eingang-Abarbeiten-Modus.
export default function BuchungModal({
  buchung,
  preBelege = [],
  gewerbeId,
  jahr,
  kategorien,
  presetKategorieId,
  presetBetragCent,
  presetBeschreibung,
  wizard,
  onClose,
  onSaved,
}) {
  const isEdit = Boolean(buchung?.id);
  const katById = useMemo(() => Object.fromEntries(kategorien.map((k) => [String(k.id), k])), [kategorien]);
  const options = useMemo(
    () =>
      kategorien
        .filter((k) => !k.ist_afa)
        .map((k) => ({
          value: String(k.id),
          label: k.euer_zeile ? `${k.name} · Zeile ${k.euer_zeile}` : k.name,
        })),
    [kategorien],
  );

  const [datum, setDatum] = useState(buchung?.datum || todayISO());
  const [beschreibung, setBeschreibung] = useState(buchung?.beschreibung || presetBeschreibung || '');
  const [positionen, setPositionen] = useState(() =>
    buchung?.positionen?.length
      ? buchung.positionen.map((p) => ({
          kategorie_id: String(p.kategorie_id),
          betragInput: centToInput(p.betrag_cent),
          calc: {},
          beleg_details: p.beleg_details || '',
        }))
      : [
          {
            ...emptyPos(),
            ...(presetKategorieId ? { kategorie_id: String(presetKategorieId) } : {}),
            ...(presetBetragCent ? { betragInput: centToInput(presetBetragCent) } : {}),
          },
        ],
  );
  const [busy, setBusy] = useState(false);
  const [vorschlag, setVorschlag] = useState(null); // { quelle, ... } | null
  const [liestBeleg, setLiestBeleg] = useState(false);

  // Beleg-Erkennung: beim Verbuchen eines Eingangs-Belegs Felder vorbefüllen
  // (E-Rechnung/PDF-Text/OCR) — nur leere Felder, immer als Vorschlag markiert.
  useEffect(() => {
    if (isEdit || preBelege.length !== 1) return;
    let aktiv = true;
    setLiestBeleg(true);
    api
      .get(`/api/belege/${preBelege[0].id}/vorschlag`)
      .then((res) => {
        if (!aktiv) return;
        const v = res.data;
        if (v.quelle === 'keine' || v.quelle === 'ocr-fehlgeschlagen') {
          if (v.kategorie_id) {
            setPositionen((arr) =>
              arr.map((p, i) => (i === 0 && !p.kategorie_id ? { ...p, kategorie_id: String(v.kategorie_id) } : p)),
            );
            setVorschlag(v);
          }
          return;
        }
        setVorschlag(v);
        if (v.datum) setDatum(v.datum);
        if (v.lieferant) setBeschreibung((b) => b || v.lieferant);
        setPositionen((arr) =>
          arr.map((p, i) =>
            i === 0
              ? {
                  ...p,
                  kategorie_id: p.kategorie_id || (v.kategorie_id ? String(v.kategorie_id) : ''),
                  betragInput: p.betragInput || (v.betrag_cent ? centToInput(v.betrag_cent) : ''),
                }
              : p,
          ),
        );
      })
      .catch(() => {})
      .finally(() => aktiv && setLiestBeleg(false));
    return () => {
      aktiv = false;
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const jahrMismatch = jahr && datum && String(datum).slice(0, 4) !== String(jahr);

  function setPos(i, patch) {
    setPositionen((arr) => arr.map((p, idx) => (idx === i ? { ...p, ...patch } : p)));
  }
  function setCalcField(i, pos, calcDef, key, value) {
    const calc = { ...pos.calc, [key]: value };
    const cent = calcDef.compute(calc);
    setPos(i, { calc, ...(cent !== null ? { betragInput: centToInput(cent) } : {}) });
  }
  function addPos() {
    setPositionen((arr) => [...arr, emptyPos()]);
  }
  function removePos(i) {
    setPositionen((arr) => arr.filter((_, idx) => idx !== i));
  }

  const total = positionen.reduce((s, p) => {
    const c = parseEuroToCent(p.betragInput);
    return s + (c && c > 0 ? c : 0);
  }, 0);

  async function save(e) {
    e.preventDefault();
    const payloadPos = [];
    for (const p of positionen) {
      const kat = katById[p.kategorie_id];
      if (!p.kategorie_id || !kat) return toast.error('Bitte für jede Position eine Kategorie wählen.');
      const betrag = parseEuroToCent(p.betragInput);
      if (!betrag || betrag <= 0) return toast.error(`Bitte gültigen Betrag für „${kat.name}" eingeben.`);
      if (kat.belegpflicht_extra && !p.beleg_details.trim())
        return toast.error(`Für „${kat.name}" sind Beleg-Details Pflicht.`);
      payloadPos.push({
        kategorie_id: Number(p.kategorie_id),
        betrag_cent: betrag,
        beleg_details: kat.belegpflicht_extra ? p.beleg_details.trim() : null,
      });
    }

    setBusy(true);
    try {
      if (isEdit) {
        await api.patch(`/api/buchungen/${buchung.id}`, {
          datum,
          beschreibung: beschreibung.trim() || null,
          positionen: payloadPos,
        });
        toast.success('Gespeichert.');
      } else {
        await api.post('/api/buchungen', {
          gewerbe_id: Number(gewerbeId),
          datum,
          beschreibung: beschreibung.trim() || null,
          positionen: payloadPos,
          beleg_ids: preBelege.map((b) => b.id),
        });
        toast.success('Buchung angelegt.');
      }
      onClose();
      await onSaved?.();
    } catch (err) {
      toast.error(apiError(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal
      title={
        wizard
          ? `Beleg ${wizard.pos} von ${wizard.total} verbuchen`
          : isEdit
            ? 'Buchung bearbeiten'
            : 'Neue Buchung'
      }
      onClose={onClose}
      maxWidth="max-w-2xl"
    >
      <form onSubmit={save} className="space-y-4">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-5 gap-y-2">
          <label className="block">
            <span className="field-label">Datum (Zahlung)</span>
            <input type="date" className="input" value={datum} onChange={(e) => setDatum(e.target.value)} />
          </label>
          <label className="block">
            <span className="field-label">Beschreibung / Beleg (optional)</span>
            <input
              className="input"
              value={beschreibung}
              onChange={(e) => setBeschreibung(e.target.value)}
              placeholder="z. B. Amazon-Rechnung 03/2025"
            />
          </label>
        </div>

        {liestBeleg && (
          <div className="rounded-lg bg-royal-soft/10 p-2.5 text-xs text-ink/60">
            Beleg wird gelesen…
          </div>
        )}
        {vorschlag && !liestBeleg && (
          <div className="rounded-lg bg-royal-soft/15 border-l-4 border-royal-soft p-2.5 text-xs text-ink/80">
            <strong>Vorschlag aus dem Beleg</strong> (
            {{ 'e-rechnung': 'E-Rechnung, exakt', 'pdf-text': 'PDF-Text', ocr: 'Texterkennung/OCR' }[
              vorschlag.quelle
            ] || 'teilweise erkannt'}
            ) — bitte prüfen, besonders Betrag und Kategorie.
          </div>
        )}
        {jahrMismatch && (
          <div className="rounded-lg bg-yellow-100 text-yellow-900 p-2.5 text-xs">
            Das Datum liegt nicht im oben gewählten Jahr <strong>{jahr}</strong> — die Buchung
            erscheint dann erst, wenn du oben auf {String(datum).slice(0, 4)} umschaltest.
          </div>
        )}

        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <span className="field-label mb-0">Positionen</span>
            <span className="text-sm text-ink/60 tabular-nums">Summe {formatEuro(total)}</span>
          </div>

          {positionen.map((p, i) => {
            const kat = katById[p.kategorie_id];
            const calcDef = CALCULATORS[kat?.key];
            const isGwg = kat?.key === 'gwg';
            const isBewirtung = kat?.key === 'bewirtung';
            const isKfz1Prozent = kat?.key === 'kfz_privatnutzung';
            const needsBeleg = Boolean(kat?.belegpflicht_extra);
            const betragCent = parseEuroToCent(p.betragInput);
            const warnGeschenke = kat?.key === 'geschenke' && betragCent > GESCHENKE_GRENZE_CENT;
            const warnHomeoffice = kat?.key === 'homeoffice_pauschale' && betragCent > HOMEOFFICE_MAX_CENT;
            return (
              <div key={i} className="rounded-lg border border-ink/10 p-3 space-y-3">
                <div className="flex items-start gap-2">
                  <div className="flex-1">
                    <Dropdown
                      value={p.kategorie_id}
                      onChange={(v) => setPos(i, { kategorie_id: String(v), calc: {} })}
                      options={options}
                      placeholder="Kategorie suchen…"
                      searchable
                    />
                  </div>
                  {positionen.length > 1 && (
                    <button
                      type="button"
                      onClick={() => removePos(i)}
                      className="p-2 rounded-md hover:bg-ink/5 text-ink/50 shrink-0"
                      aria-label="Position entfernen"
                      title="Position entfernen"
                    >
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-5 w-5">
                        <path d="M6 6l12 12M18 6L6 18" />
                      </svg>
                    </button>
                  )}
                </div>

                {calcDef && (
                  <div className="rounded-lg bg-royal-soft/10 p-2.5 space-y-2">
                    <div
                      className={
                        calcDef.fields.length > 2
                          ? 'grid grid-cols-1 sm:grid-cols-3 gap-3'
                          : calcDef.fields.length > 1
                            ? 'grid grid-cols-2 gap-3'
                            : 'grid grid-cols-1 gap-3'
                      }
                    >
                      {calcDef.fields.map((f) =>
                        f.type === 'select' ? (
                          <div key={f.key} className="block">
                            <span className="field-label">{f.label}</span>
                            <Dropdown
                              value={p.calc[f.key] ?? f.default}
                              onChange={(v) => setCalcField(i, p, calcDef, f.key, String(v))}
                              options={f.options}
                            />
                          </div>
                        ) : (
                          <label key={f.key} className="block">
                            <span className="field-label">{f.label}</span>
                            <input
                              className="input tabular-nums"
                              inputMode="decimal"
                              value={p.calc[f.key] || ''}
                              onChange={(e) => setCalcField(i, p, calcDef, f.key, e.target.value)}
                              placeholder={f.placeholder}
                            />
                          </label>
                        ),
                      )}
                    </div>
                    <span className="block text-xs text-ink/60">
                      Rechner: {calcDef.hint} — Ergebnis landet im Betragsfeld.
                    </span>
                  </div>
                )}

                <label className="block">
                  <span className="field-label">Betrag brutto (€)</span>
                  <input
                    className="input tabular-nums"
                    inputMode="decimal"
                    value={p.betragInput}
                    onChange={(e) => setPos(i, { betragInput: e.target.value, calc: {} })}
                    placeholder="0,00"
                  />
                </label>

                {isGwg && (
                  <div className="rounded-lg bg-royal-soft/15 border-l-4 border-royal-soft p-2.5 text-xs text-ink/80">
                    GWG-Grenze ist <strong>netto</strong>: 800 € netto ≈ 952 € brutto (19 %). Darüber →
                    AfA-Erfassung.
                  </div>
                )}
                {isBewirtung && (
                  <div className="rounded-lg bg-royal-soft/15 border-l-4 border-royal-soft p-2.5 text-xs text-ink/80">
                    100 % erfassen — der Export rechnet automatisch 70 % in Zeile 63.
                  </div>
                )}
                {isKfz1Prozent && (
                  <div className="rounded-lg bg-royal-soft/15 border-l-4 border-royal-soft p-2.5 text-xs text-ink/80">
                    Voraussetzung: Kfz zu <strong>&gt; 50 %</strong> betrieblich genutzt (Betriebsvermögen).
                    <strong> E-Auto (0,25 %)</strong> gilt bis 70.000 € Listenpreis (Anschaffung ab
                    07/2025: 100.000 €), darüber 0,5 %; <strong>Plug-in-Hybrid (0,5 %)</strong> nur mit
                    ausreichender E-Reichweite. Die laufenden Kfz-Kosten separat als „Kfz-Kosten
                    Betriebs-Kfz" buchen. Nicht abgedeckt: 0,03 %-Kürzung für Wege Wohnung–Betrieb
                    (Zeile 72), Kostendeckelung, Fahrtenbuch — im Zweifel Steuerberater.
                  </div>
                )}
                {warnGeschenke && (
                  <div className="rounded-lg bg-yellow-100 text-yellow-900 p-2.5 text-xs">
                    Über 50 € pro Empfänger und Jahr sind Geschenke <strong>gar nicht</strong> abziehbar
                    (Freigrenze, keine Kürzung). Nur erfassen, wenn mehrere Empfänger auf dem Beleg stehen.
                  </div>
                )}
                {warnHomeoffice && (
                  <div className="rounded-lg bg-yellow-100 text-yellow-900 p-2.5 text-xs">
                    Die Homeoffice-Pauschale ist auf 1.260 €/Jahr (210 Tage) gedeckelt — dieser Betrag
                    liegt darüber.
                  </div>
                )}
                {needsBeleg && (
                  <label className="block">
                    <span className="field-label">Beleg-Details (Pflicht)</span>
                    <textarea
                      className="input min-h-[64px]"
                      value={p.beleg_details}
                      onChange={(e) => setPos(i, { beleg_details: e.target.value })}
                      placeholder={BELEG_PLACEHOLDER[kat?.key] || 'Pflichtangaben am Beleg dokumentieren.'}
                    />
                  </label>
                )}
              </div>
            );
          })}

          <button type="button" className="btn-ghost btn-sm" onClick={addPos}>
            + Position hinzufügen
          </button>
        </div>

        {isEdit ? (
          <div className="pt-2 border-t border-ink/10">
            <BelegeManager buchungId={buchung.id} gewerbeId={gewerbeId} onChange={onSaved} />
          </div>
        ) : preBelege.length > 0 ? (
          <div className="rounded-lg bg-royal-soft/10 p-3 text-sm text-ink/70">
            Wird angehängt:{' '}
            {preBelege.map((b, i) => (
              <span key={b.id}>
                {i > 0 && ', '}
                <button
                  type="button"
                  className="text-royal font-medium hover:underline"
                  onClick={() => openBeleg(b.id)}
                  title="Beleg ansehen"
                >
                  {b.original_name}
                </button>
              </span>
            ))}
          </div>
        ) : (
          <div className="rounded-lg bg-royal-soft/10 p-3 text-sm text-ink/60">
            Belege kannst du nach dem Speichern anhängen — oder vorab im Eingang hochladen.
          </div>
        )}

        <div className="flex flex-col-reverse sm:flex-row sm:justify-end gap-2 pt-2">
          <button type="button" className="btn-ghost" onClick={onClose}>
            {isEdit ? 'Schließen' : 'Abbrechen'}
          </button>
          {wizard && (
            <button type="button" className="btn-outline" onClick={wizard.onSkip}>
              Überspringen
            </button>
          )}
          <button type="submit" className="btn-primary" disabled={busy}>
            Speichern
          </button>
        </div>
      </form>
    </Modal>
  );
}
