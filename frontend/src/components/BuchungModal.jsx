import { useMemo, useState } from 'react';
import toast from 'react-hot-toast';
import { api, apiError } from '../api/client.js';
import Dropdown from './Dropdown.jsx';
import Modal from './Modal.jsx';
import BelegeManager from './BelegeManager.jsx';
import { formatEuro, parseEuroToCent, centToInput, todayISO, KM_SATZ_CENT } from '../lib/format.js';

const BELEG_PLACEHOLDER = {
  bewirtung: 'Pflichtangaben: Ort, Tag, Teilnehmer, Anlass (ab 150 € mit Namen).',
  geschenke: 'Pflichtangaben: Empfänger (Name), Anlass.',
};

function emptyPos() {
  return { kategorie_id: '', betragInput: '', km: '', beleg_details: '' };
}

function kmToCent(km) {
  const n = Number(String(km).replace(',', '.'));
  return km !== '' && Number.isFinite(n) ? Math.round(n * KM_SATZ_CENT) : null;
}

function posBetragCent(p, kat) {
  if (kat?.key === 'fahrtkosten_kfz') return kmToCent(p.km);
  return parseEuroToCent(p.betragInput);
}

// Gemeinsames Modal für Buchungen (Beleg-Kopf + 1..n Positionen).
// preBelege: Eingangs-Belege, die beim Anlegen verknüpft werden.
export default function BuchungModal({ buchung, preBelege = [], gewerbeId, kategorien, onClose, onSaved }) {
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
  const [beschreibung, setBeschreibung] = useState(buchung?.beschreibung || '');
  const [positionen, setPositionen] = useState(() =>
    buchung?.positionen?.length
      ? buchung.positionen.map((p) => ({
          kategorie_id: String(p.kategorie_id),
          betragInput: centToInput(p.betrag_cent),
          km: '',
          beleg_details: p.beleg_details || '',
        }))
      : [emptyPos()],
  );
  const [busy, setBusy] = useState(false);

  function setPos(i, patch) {
    setPositionen((arr) => arr.map((p, idx) => (idx === i ? { ...p, ...patch } : p)));
  }
  function addPos() {
    setPositionen((arr) => [...arr, emptyPos()]);
  }
  function removePos(i) {
    setPositionen((arr) => arr.filter((_, idx) => idx !== i));
  }

  const total = positionen.reduce((s, p) => {
    const c = posBetragCent(p, katById[p.kategorie_id]);
    return s + (c && c > 0 ? c : 0);
  }, 0);

  async function save(e) {
    e.preventDefault();
    const payloadPos = [];
    for (const p of positionen) {
      const kat = katById[p.kategorie_id];
      if (!p.kategorie_id || !kat) return toast.error('Bitte für jede Position eine Kategorie wählen.');
      const betrag = posBetragCent(p, kat);
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
      title={isEdit ? 'Buchung bearbeiten' : 'Neue Buchung'}
      onClose={onClose}
      maxWidth="max-w-2xl"
    >
      <form onSubmit={save} className="space-y-4">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <label className="block">
            <span className="label">Datum (Zahlung)</span>
            <input type="date" className="input" value={datum} onChange={(e) => setDatum(e.target.value)} />
          </label>
          <label className="block">
            <span className="label">Beschreibung / Beleg (optional)</span>
            <input
              className="input"
              value={beschreibung}
              onChange={(e) => setBeschreibung(e.target.value)}
              placeholder="z. B. Amazon-Rechnung 03/2025"
            />
          </label>
        </div>

        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <span className="label mb-0">Positionen</span>
            <span className="text-sm text-ink/60 tabular-nums">Summe {formatEuro(total)}</span>
          </div>

          {positionen.map((p, i) => {
            const kat = katById[p.kategorie_id];
            const isKm = kat?.key === 'fahrtkosten_kfz';
            const isGwg = kat?.key === 'gwg';
            const isBewirtung = kat?.key === 'bewirtung';
            const needsBeleg = Boolean(kat?.belegpflicht_extra);
            const kmCent = kmToCent(p.km);
            return (
              <div key={i} className="rounded-lg border border-ink/10 p-3 space-y-3">
                <div className="flex items-start gap-2">
                  <div className="flex-1">
                    <Dropdown
                      value={p.kategorie_id}
                      onChange={(v) => setPos(i, { kategorie_id: String(v) })}
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

                {isKm ? (
                  <div className="grid grid-cols-2 gap-3">
                    <label className="block">
                      <span className="label">Kilometer</span>
                      <input
                        className="input"
                        inputMode="decimal"
                        value={p.km}
                        onChange={(e) => setPos(i, { km: e.target.value })}
                        placeholder="z. B. 120"
                      />
                      <span className="block text-xs text-ink/60 mt-1">× 0,30 €/km</span>
                    </label>
                    <div className="block">
                      <span className="label">Betrag</span>
                      <div className="input bg-ink/5 tabular-nums">
                        {kmCent !== null ? formatEuro(kmCent) : '—'}
                      </div>
                    </div>
                  </div>
                ) : (
                  <label className="block">
                    <span className="label">Betrag brutto (€)</span>
                    <input
                      className="input tabular-nums"
                      inputMode="decimal"
                      value={p.betragInput}
                      onChange={(e) => setPos(i, { betragInput: e.target.value })}
                      placeholder="0,00"
                    />
                  </label>
                )}

                {isGwg && (
                  <div className="rounded-lg bg-mint-soft/15 border-l-4 border-mint-soft p-2.5 text-xs text-ink/80">
                    GWG-Grenze ist <strong>netto</strong>: 800 € netto ≈ 952 € brutto (19 %). Darüber →
                    AfA-Erfassung.
                  </div>
                )}
                {isBewirtung && (
                  <div className="rounded-lg bg-mint-soft/15 border-l-4 border-mint-soft p-2.5 text-xs text-ink/80">
                    100 % erfassen — der Export rechnet automatisch 70 % in Zeile 63.
                  </div>
                )}
                {needsBeleg && (
                  <label className="block">
                    <span className="label">Beleg-Details (Pflicht)</span>
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
          <div className="rounded-lg bg-mint-soft/10 p-3 text-sm text-ink/70">
            Wird angehängt: {preBelege.map((b) => b.original_name).join(', ')}
          </div>
        ) : (
          <div className="rounded-lg bg-mint-soft/10 p-3 text-sm text-ink/60">
            Belege kannst du nach dem Speichern anhängen — oder vorab im Eingang hochladen.
          </div>
        )}

        <div className="flex flex-col-reverse sm:flex-row sm:justify-end gap-2 pt-2">
          <button type="button" className="btn-ghost" onClick={onClose}>
            {isEdit ? 'Schließen' : 'Abbrechen'}
          </button>
          <button type="submit" className="btn-primary" disabled={busy}>
            Speichern
          </button>
        </div>
      </form>
    </Modal>
  );
}
