import { useEffect, useState } from 'react';
import toast from 'react-hot-toast';
import { api, apiError } from '../api/client.js';
import Modal from './Modal.jsx';
import Dropdown from './Dropdown.jsx';
import { DialogFuss, Gruppe, SchalterZeile } from './DialogParts.jsx';
import { Hinweis } from './PageParts.jsx';
import { centToInput, formatEuro, parseEuroToCent, todayISO } from '../lib/format.js';

// Digitaler Eigenbeleg (v42, backend/app/services/eigenbeleg.py): wenn ein Originalbeleg fehlt oder es nie einen
// gab. Die Felder sind die Pflichtangaben (GoBD Rz. 61/77). Der Schalter „Angaben bestätigen“ ist die elektronische
// Freigabe; danach erzeugt der Server das PDF, das sich nicht mehr ändern lässt.
// buchungId: direkt an diese Buchung hängen, sonst landet er im Eingang. vorlage: { datum, betragCent, empfaenger,
// gegenstand, kategorieKey } zum Vorbefüllen. onCreated(beleg) nach dem Speichern.
export default function EigenbelegModal({ gewerbeId, buchungId = null, vorlage = {}, onClose, onCreated }) {
  const [optionen, setOptionen] = useState({ gruende: [], zahlungsarten: [] });
  const [f, setF] = useState({
    datum: vorlage.datum || todayISO(),
    betragInput: vorlage.betragCent ? centToInput(vorlage.betragCent) : '',
    empfaenger: vorlage.empfaenger || '',
    gegenstand: vorlage.gegenstand || '',
    anlass: '',
    zahlungsart: 'bar',
    grund: '',
    grundText: '',
  });
  const [bestaetigt, setBestaetigt] = useState(false);
  const [hinweise, setHinweise] = useState([]);
  const [busy, setBusy] = useState(false);
  const set = (patch) => setF((alt) => ({ ...alt, ...patch }));
  const betragCent = parseEuroToCent(f.betragInput);

  useEffect(() => {
    api.get('/api/eigenbelege/optionen').then((r) => setOptionen(r.data)).catch(() => {});
  }, []);

  // Weiche Hinweise (Regelbesteuerung, hoher Betrag, Bewirtung, Häufung) — kommen vom Server, blockieren nie.
  useEffect(() => {
    const t = setTimeout(() => {
      api
        .post('/api/eigenbelege/pruefen', {
          gewerbe_id: gewerbeId,
          buchung_id: buchungId,
          datum: f.datum || null,
          betrag_cent: betragCent || null,
          kategorie_key: vorlage.kategorieKey || null,
        })
        .then((r) => setHinweise(r.data.hinweise))
        .catch(() => setHinweise([]));
    }, 300);
    return () => clearTimeout(t);
  }, [gewerbeId, buchungId, f.datum, betragCent, vorlage.kategorieKey]);

  async function speichern(e) {
    e?.preventDefault();
    if (!f.empfaenger.trim() || !f.gegenstand.trim() || !f.anlass.trim())
      return toast.error('Bitte Zahlungsempfänger, Gegenstand und Anlass angeben.');
    if (!(betragCent > 0)) return toast.error('Bitte einen Betrag angeben.');
    if (!f.grund) return toast.error('Bitte angeben, warum kein Originalbeleg vorliegt.');
    if (!bestaetigt) return toast.error('Bitte die Erklärung bestätigen.');
    setBusy(true);
    try {
      const r = await api.post('/api/eigenbelege', {
        gewerbe_id: gewerbeId,
        buchung_id: buchungId,
        datum: f.datum,
        betrag_cent: betragCent,
        empfaenger: f.empfaenger,
        gegenstand: f.gegenstand,
        anlass: f.anlass,
        zahlungsart: f.zahlungsart || null,
        grund: f.grund,
        grund_text: f.grundText || null,
        bestaetigt: true,
      });
      toast.success(`Eigenbeleg ${r.data.eigenbeleg.nummer} erstellt.`);
      onCreated?.(r.data);
      onClose();
    } catch (err) {
      toast.error(apiError(err, 'Eigenbeleg konnte nicht erstellt werden.'));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal
      title="Eigenbeleg erstellen"
      subtitle="Für Ausgaben ohne Originalbeleg: verlorene Quittung, Parkautomat, Trinkgeld. Der Eigenbeleg ist die Ausnahme und ersetzt keine Rechnung."
      onClose={onClose}
      maxWidth="max-w-xl"
    >
      {/* Kein Formular-Element: das Fenster liegt oft im Formular des Buchungsfensters, verschachtelte
          Formulare schicken im Browser das äußere ab. Gespeichert wird per Klick, Enter in einem Feld schickt nichts ab. */}
      <div
        className="space-y-5"
        onKeyDown={(e) => e.key === 'Enter' && e.target.tagName === 'INPUT' && e.preventDefault()}
      >
        <Gruppe titel="Ausgabe">
          <div className="grid grid-cols-1 gap-x-5 gap-y-2 sm:grid-cols-2">
            <label className="block">
              <span className="field-label">Datum der Ausgabe</span>
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
              <span className="field-label">Betrag (brutto, €)</span>
              <input
                className="input tabular-nums"
                inputMode="decimal"
                placeholder="0,00"
                value={f.betragInput}
                onChange={(e) => set({ betragInput: e.target.value })}
                required
              />
            </label>
            <label className="block sm:col-span-2">
              <span className="field-label">Zahlungsempfänger (Name, Ort)</span>
              <input
                className="input"
                maxLength={200}
                placeholder="z. B. Parkhaus am Bahnhof, Heidelberg"
                value={f.empfaenger}
                onChange={(e) => set({ empfaenger: e.target.value })}
                required
              />
            </label>
            <label className="block sm:col-span-2">
              <span className="field-label">Was wurde bezahlt</span>
              <input
                className="input"
                maxLength={500}
                placeholder="z. B. Parkticket, 2 Stunden"
                value={f.gegenstand}
                onChange={(e) => set({ gegenstand: e.target.value })}
                required
              />
            </label>
            <label className="block sm:col-span-2">
              <span className="field-label">Betrieblicher Anlass</span>
              <input
                className="input"
                maxLength={500}
                placeholder="z. B. Kundentermin bei Firma X"
                value={f.anlass}
                onChange={(e) => set({ anlass: e.target.value })}
                required
              />
            </label>
            <div>
              <span className="field-label">Zahlungsart</span>
              <Dropdown value={f.zahlungsart} onChange={(v) => set({ zahlungsart: v })} options={optionen.zahlungsarten} />
            </div>
          </div>
        </Gruppe>

        <Gruppe titel="Warum kein Originalbeleg">
          <Dropdown
            value={f.grund}
            onChange={(v) => set({ grund: v })}
            options={optionen.gruende}
            placeholder="Grund wählen"
          />
          {f.grund && (
            <label className="block">
              <span className="field-label">{f.grund === 'sonstiges' ? 'Erklärung (Pflicht)' : 'Erklärung (optional)'}</span>
              <input
                className="input"
                maxLength={500}
                value={f.grundText}
                onChange={(e) => set({ grundText: e.target.value })}
                required={f.grund === 'sonstiges'}
              />
            </label>
          )}
        </Gruppe>

        {hinweise.map((h) => (
          <Hinweis key={h.text} ton={h.ton === 'warn' ? 'warn' : 'info'}>
            {h.text}
          </Hinweis>
        ))}

        <SchalterZeile
          titel="Angaben bestätigen"
          hinweis={`Ich bestätige, dass die Ausgabe${betragCent > 0 ? ` über ${formatEuro(betragCent)}` : ''} betrieblich angefallen ist und kein Originalbeleg vorliegt. Das ist die elektronische Freigabe; danach lässt sich der Eigenbeleg nicht mehr ändern, nur löschen und neu erstellen.`}
          checked={bestaetigt}
          onChange={setBestaetigt}
        />

        <DialogFuss>
          <button type="button" className="btn-ghost" onClick={onClose}>
            Abbrechen
          </button>
          <button type="button" className="btn-primary" onClick={speichern} disabled={busy || !bestaetigt}>
            Eigenbeleg erstellen
          </button>
        </DialogFuss>
      </div>
    </Modal>
  );
}
