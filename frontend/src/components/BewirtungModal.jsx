import { useEffect, useState } from 'react';
import toast from 'react-hot-toast';
import { api, apiError } from '../api/client.js';
import Modal from './Modal.jsx';
import { DialogFuss, Gruppe, SchalterZeile } from './DialogParts.jsx';
import { Hinweis } from './PageParts.jsx';
import { openBeleg } from '../lib/belege.js';
import { centToInput, parseEuroToCent, todayISO } from '../lib/format.js';

// Digitaler Bewirtungsbeleg (backend/app/services/eigenbeleg.py, EUER_KATEGORIEN.md §10): Anlass und Teilnehmer zur
// Restaurantrechnung, ohne Papier-Vordruck. Elektronische Freigabe per Schalter; der Server baut ein PDF mit Verweis
// auf die Rechnung (Beleg-Nr., Dateiname, SHA-256 — BMF 19.11.2025, Rn. 19–22). Ersetzt die Rechnung NICHT.
// buchungId: direkt an die Buchung (Rechnungen = die dort hängenden Belege). rechnungen: [{id, original_name}] —
// ohne buchungId die Belege, auf die verwiesen wird. vorlage: { datum, betragCent }.
export default function BewirtungModal({ gewerbeId, buchungId = null, rechnungen = [], vorlage = {}, onClose, onCreated }) {
  const [f, setF] = useState({
    datum: vorlage.datum || todayISO(),
    ort: '',
    anlass: '',
    teilnehmer: '',
    betragInput: vorlage.betragCent ? centToInput(vorlage.betragCent) : '',
    trinkgeldInput: '',
  });
  const [bestaetigt, setBestaetigt] = useState(false);
  const [hinweise, setHinweise] = useState([]);
  const [busy, setBusy] = useState(false);
  const set = (patch) => setF((alt) => ({ ...alt, ...patch }));
  const betragCent = parseEuroToCent(f.betragInput) || null;
  const trinkgeldCent = parseEuroToCent(f.trinkgeldInput) || null;
  const rechnungIds = buchungId ? [] : rechnungen.map((r) => r.id);
  const idsKey = rechnungIds.join(',');

  useEffect(() => {
    const t = setTimeout(() => {
      api
        .post('/api/eigenbelege/bewirtung/pruefen', {
          gewerbe_id: gewerbeId,
          buchung_id: buchungId,
          rechnung_beleg_ids: rechnungIds,
          datum: f.datum || null,
          betrag_cent: betragCent,
          trinkgeld_cent: trinkgeldCent,
        })
        .then((r) => setHinweise(r.data.hinweise))
        .catch(() => setHinweise([]));
    }, 300);
    return () => clearTimeout(t);
  }, [gewerbeId, buchungId, idsKey, f.datum, betragCent, trinkgeldCent]); // eslint-disable-line react-hooks/exhaustive-deps

  async function speichern(e) {
    e?.preventDefault();
    if (!f.anlass.trim() || !f.teilnehmer.trim()) return toast.error('Bitte Anlass und Teilnehmer angeben.');
    if (!bestaetigt) return toast.error('Bitte die Angaben bestätigen.');
    setBusy(true);
    try {
      const r = await api.post('/api/eigenbelege/bewirtung', {
        gewerbe_id: gewerbeId,
        buchung_id: buchungId,
        rechnung_beleg_ids: rechnungIds,
        datum: f.datum,
        ort: f.ort || null,
        anlass: f.anlass,
        teilnehmer: f.teilnehmer,
        betrag_cent: betragCent,
        trinkgeld_cent: trinkgeldCent,
        bestaetigt: true,
      });
      toast.success(`Bewirtungsbeleg ${r.data.eigenbeleg.nummer} erstellt.`);
      onCreated?.(r.data);
      onClose();
    } catch (err) {
      toast.error(apiError(err, 'Bewirtungsbeleg konnte nicht erstellt werden.'));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal
      title="Bewirtungsbeleg"
      subtitle="Anlass und Teilnehmer zur Restaurantrechnung, ohne Vordruck und ohne Papier. Die Rechnung selbst bleibt Pflicht."
      onClose={onClose}
      maxWidth="max-w-xl"
    >
      {/* Kein Formular-Element: das Fenster liegt oft im Formular des Buchungsfensters, verschachtelte
          Formulare schicken im Browser das äußere ab. Gespeichert wird per Klick, Enter in einem Feld schickt nichts ab. */}
      <div
        className="space-y-5"
        onKeyDown={(e) => e.key === 'Enter' && e.target.tagName === 'INPUT' && e.preventDefault()}
      >
        <Gruppe titel="Zugehörige Rechnung">
          {rechnungen.length ? (
            <ul className="text-sm">
              {rechnungen.map((r) => (
                <li key={r.id}>
                  <button
                    type="button"
                    className="text-left font-bold text-royal hover:underline"
                    onClick={() => openBeleg(r.id)}
                  >
                    {r.original_name}
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-ink/60">Keine Rechnung angehängt.</p>
          )}
        </Gruppe>

        <Gruppe titel="Bewirtung">
          <div className="grid grid-cols-1 gap-x-5 gap-y-2 sm:grid-cols-2">
            <label className="block">
              <span className="field-label">Tag der Bewirtung</span>
              <input
                type="date"
                className="input"
                value={f.datum}
                max={todayISO()}
                onChange={(e) => set({ datum: e.target.value })}
                required
              />
            </label>
            <label className="block">
              <span className="field-label">Ort / Gaststätte</span>
              <input
                className="input"
                maxLength={200}
                placeholder="z. B. Gasthaus Adler, Heidelberg"
                value={f.ort}
                onChange={(e) => set({ ort: e.target.value })}
              />
            </label>
            <label className="block sm:col-span-2">
              <span className="field-label">Anlass</span>
              <input
                className="input"
                maxLength={500}
                placeholder="z. B. Projektbesprechung Website mit Firma X"
                value={f.anlass}
                onChange={(e) => set({ anlass: e.target.value })}
                required
              />
            </label>
            <label className="block sm:col-span-2">
              <span className="field-label">Teilnehmer (eine Person je Zeile, dich selbst mit)</span>
              <textarea
                className="input min-h-[96px]"
                maxLength={2000}
                placeholder={'Max Muster\nErika Beispiel (Firma X)'}
                value={f.teilnehmer}
                onChange={(e) => set({ teilnehmer: e.target.value })}
                required
              />
            </label>
            <label className="block">
              <span className="field-label">Gesamtbetrag (€)</span>
              <input
                className="input tabular-nums"
                inputMode="decimal"
                placeholder="laut Rechnung"
                value={f.betragInput}
                onChange={(e) => set({ betragInput: e.target.value })}
              />
            </label>
            <label className="block">
              <span className="field-label">Davon Trinkgeld (€, optional)</span>
              <input
                className="input tabular-nums"
                inputMode="decimal"
                placeholder="0,00"
                value={f.trinkgeldInput}
                onChange={(e) => set({ trinkgeldInput: e.target.value })}
              />
            </label>
          </div>
        </Gruppe>

        {hinweise.map((h) => (
          <Hinweis key={h.text} ton={h.ton === 'warn' ? 'warn' : 'info'}>
            {h.text}
          </Hinweis>
        ))}

        <SchalterZeile
          titel="Angaben bestätigen"
          hinweis="Ich bestätige, dass die Bewirtung geschäftlich veranlasst war und Anlass und Teilnehmer stimmen. Das ersetzt die Unterschrift; danach lässt sich der Beleg nicht mehr ändern, nur löschen und neu erstellen."
          checked={bestaetigt}
          onChange={setBestaetigt}
        />

        <DialogFuss>
          <button type="button" className="btn-ghost" onClick={onClose}>
            Abbrechen
          </button>
          <button type="button" className="btn-primary" onClick={speichern} disabled={busy || !bestaetigt}>
            Bewirtungsbeleg erstellen
          </button>
        </DialogFuss>
      </div>
    </Modal>
  );
}
