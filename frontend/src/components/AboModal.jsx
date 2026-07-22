import { useMemo, useState } from 'react';
import toast from 'react-hot-toast';
import { api, apiError } from '../api/client.js';
import Dropdown from './Dropdown.jsx';
import Modal from './Modal.jsx';
import { formatEuro, parseEuroToCent, centToInput } from '../lib/format.js';

const INTERVALL_OPTIONS = [
  { value: 'monatlich', label: 'monatlich' },
  { value: 'vierteljaehrlich', label: 'vierteljährlich' },
  { value: 'jaehrlich', label: 'jährlich' },
];

const STEUERHINWEIS_OPTIONS = [
  { value: 'ku19', label: 'Kleinunternehmer § 19 UStG (Standard)' },
  { value: 'vers4nr11', label: 'Steuerfrei § 4 Nr. 11 UStG (Versicherungsprovision)' },
];

function ersterDesNaechstenMonats() {
  const d = new Date();
  const y = d.getMonth() === 11 ? d.getFullYear() + 1 : d.getFullYear();
  const m = (d.getMonth() + 1) % 12;
  return `${y}-${String(m + 1).padStart(2, '0')}-01`;
}

function emptyPos() {
  return { beschreibung: '', menge: '1', preisInput: '' };
}

// Wiederkehrende Rechnung (Abo) anlegen/bearbeiten. prefill: aus einer bestehenden
// Rechnung („Wiederholen…"); abo: bestehendes Abo bearbeiten.
export default function AboModal({ abo, prefill, gewerbeId, mailKonfiguriert, onClose, onSaved }) {
  const isEdit = Boolean(abo?.id);
  const src = abo || prefill || {};
  const [form, setForm] = useState(() => ({
    empfaenger_name: src.empfaenger_name || '',
    empfaenger_anschrift: src.empfaenger_anschrift || '',
    empfaenger_email: src.empfaenger_email || '',
    notiz: src.notiz || '',
    steuerhinweis: src.steuerhinweis || 'ku19',
    intervall: abo?.intervall || 'monatlich',
    naechste_am: abo?.naechste_am || ersterDesNaechstenMonats(),
    auto_senden: Boolean(abo?.auto_senden),
    betreff: abo?.betreff || '',
    mail_text: abo?.mail_text || '',
    positionen: (src.positionen || []).length
      ? src.positionen.map((p) => ({
          beschreibung: p.beschreibung,
          menge: String(p.menge).replace('.', ','),
          preisInput: centToInput(p.einzelpreis_cent),
        }))
      : [emptyPos()],
  }));
  const [busy, setBusy] = useState(false);

  function setPos(i, patch) {
    setForm((f) => ({
      ...f,
      positionen: f.positionen.map((p, idx) => (idx === i ? { ...p, ...patch } : p)),
    }));
  }

  const total = useMemo(
    () =>
      form.positionen.reduce((s, p) => {
        const preis = parseEuroToCent(p.preisInput);
        const menge = Number(String(p.menge).replace(',', '.'));
        return s + (preis > 0 && menge > 0 ? Math.round(menge * preis) : 0);
      }, 0),
    [form.positionen],
  );

  async function save(e) {
    e.preventDefault();
    if (!form.empfaenger_name.trim()) return toast.error('Empfänger ist Pflicht.');
    if (form.auto_senden && !form.empfaenger_email.trim())
      return toast.error('Auto-Versand braucht eine Empfänger-E-Mail.');
    const payloadPos = [];
    for (const p of form.positionen) {
      const preis = parseEuroToCent(p.preisInput);
      const menge = Number(String(p.menge).replace(',', '.'));
      if (!p.beschreibung.trim()) return toast.error('Jede Position braucht eine Beschreibung.');
      if (!preis || preis <= 0 || !Number.isFinite(menge) || menge <= 0)
        return toast.error('Bitte Menge und Preis prüfen.');
      payloadPos.push({ beschreibung: p.beschreibung.trim(), menge, einzelpreis_cent: preis });
    }
    const body = {
      empfaenger_name: form.empfaenger_name.trim(),
      empfaenger_anschrift: form.empfaenger_anschrift.trim() || null,
      empfaenger_email: form.empfaenger_email.trim() || null,
      notiz: form.notiz.trim() || null,
      steuerhinweis: form.steuerhinweis,
      intervall: form.intervall,
      naechste_am: form.naechste_am,
      auto_senden: form.auto_senden,
      betreff: form.betreff.trim() || null,
      mail_text: form.mail_text.trim() || null,
      positionen: payloadPos,
    };
    setBusy(true);
    try {
      if (isEdit) {
        await api.patch(`/api/rechnungsabos/${abo.id}`, body);
        toast.success('Abo gespeichert.');
      } else {
        await api.post('/api/rechnungsabos', { gewerbe_id: Number(gewerbeId), ...body });
        toast.success('Abo angelegt — erste Rechnung kommt am gewählten Stichtag.');
      }
      onClose();
      await onSaved();
    } catch (err) {
      toast.error(apiError(err), { duration: 8000 });
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal
      title={isEdit ? 'Abo bearbeiten' : 'Wiederkehrende Rechnung (Abo)'}
      onClose={onClose}
      maxWidth="max-w-2xl"
    >
      <form onSubmit={save} className="space-y-4">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-5 gap-y-2">
          <label className="block">
            <span className="field-label">Empfänger (Name/Firma)</span>
            <input className="input" value={form.empfaenger_name} autoFocus
              onChange={(e) => setForm({ ...form, empfaenger_name: e.target.value })} />
          </label>
          <label className="block">
            <span className="field-label">E-Mail</span>
            <input className="input" value={form.empfaenger_email}
              onChange={(e) => setForm({ ...form, empfaenger_email: e.target.value })} placeholder="kunde@firma.de" />
          </label>
        </div>
        <label className="block">
          <span className="field-label">Anschrift Empfänger</span>
          <textarea className="input min-h-[56px]" value={form.empfaenger_anschrift}
            onChange={(e) => setForm({ ...form, empfaenger_anschrift: e.target.value })} />
        </label>

        <div className="grid grid-cols-2 gap-x-5 gap-y-2">
          <div className="block">
            <span className="field-label">Intervall</span>
            <Dropdown value={form.intervall} onChange={(v) => setForm({ ...form, intervall: String(v) })}
              options={INTERVALL_OPTIONS} />
          </div>
          <label className="block">
            <span className="field-label">Nächste Rechnung am</span>
            <input type="date" className="input" value={form.naechste_am}
              onChange={(e) => setForm({ ...form, naechste_am: e.target.value })} />
          </label>
        </div>

        <div className="space-y-2">
          <span className="field-label mb-0">Positionen</span>
          {form.positionen.map((p, i) => (
            <div key={i} className="rounded-lg border border-ink/10 p-3 space-y-2">
              <div className="flex items-start gap-2">
                <input className="input flex-1" value={p.beschreibung}
                  placeholder="z. B. Betreuung {monat}"
                  onChange={(e) => setPos(i, { beschreibung: e.target.value })} />
                {form.positionen.length > 1 && (
                  <button type="button" className="p-2 rounded-md hover:bg-ink/5 text-ink/50 shrink-0"
                    onClick={() => setForm((f) => ({ ...f, positionen: f.positionen.filter((_, idx) => idx !== i) }))}
                    aria-label="Position entfernen">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-5 w-5">
                      <path d="M6 6l12 12M18 6L6 18" />
                    </svg>
                  </button>
                )}
              </div>
              <div className="grid grid-cols-2 gap-3">
                <label className="block">
                  <span className="field-label">Menge</span>
                  <input className="input tabular-nums" inputMode="decimal" value={p.menge}
                    onChange={(e) => setPos(i, { menge: e.target.value })} />
                </label>
                <label className="block">
                  <span className="field-label">Einzelpreis (€)</span>
                  <input className="input tabular-nums" inputMode="decimal" value={p.preisInput} placeholder="0,00"
                    onChange={(e) => setPos(i, { preisInput: e.target.value })} />
                </label>
              </div>
            </div>
          ))}
          <div className="flex items-center justify-between">
            <button type="button" className="btn-ghost btn-sm"
              onClick={() => setForm((f) => ({ ...f, positionen: [...f.positionen, emptyPos()] }))}>
              + Position
            </button>
            <span className="text-sm text-ink/60 tabular-nums">Summe {formatEuro(total)}</span>
          </div>
          <div className="rounded-lg bg-royal-soft/10 p-2.5 text-xs text-ink/70">
            Platzhalter <code>{'{monat}'}</code> wird durch den Abrechnungsmonat ersetzt
            (z. B. „Betreuung 08/2026") — funktioniert in Positionen, Notiz, Betreff und Mail-Text.
            Das Leistungsdatum setzt Tab automatisch auf den Abrechnungsmonat.
          </div>
        </div>

        <div className="block">
          <span className="field-label">Steuer-Hinweis</span>
          <Dropdown value={form.steuerhinweis} onChange={(v) => setForm({ ...form, steuerhinweis: String(v) })}
            options={STEUERHINWEIS_OPTIONS} />
        </div>

        <label className="flex items-start gap-2 text-sm">
          <input type="checkbox" className="mt-0.5 rounded border-ink/30 text-royal focus:ring-royal"
            checked={form.auto_senden}
            onChange={(e) => setForm({ ...form, auto_senden: e.target.checked })} />
          <span>
            <span className="font-bold">Automatisch per E-Mail senden</span>
            <span className="block text-xs text-ink/60">
              Sonst wird die Rechnung nur als Entwurf angelegt und du klickst selbst auf Senden.
              {!mailKonfiguriert && ' Achtung: Für dein Login ist noch kein App-Passwort hinterlegt (Profil-Menü → E-Mail-Versand) — bis dahin bleiben Rechnungen als Entwurf liegen.'}
            </span>
          </span>
        </label>

        {form.auto_senden && (
          <div className="grid grid-cols-1 gap-y-2">
            <label className="block">
              <span className="field-label">Betreff (optional)</span>
              <input className="input" value={form.betreff}
                onChange={(e) => setForm({ ...form, betreff: e.target.value })}
                placeholder="leer = „Rechnung {Nummer}“" />
            </label>
            <label className="block">
              <span className="field-label">Mail-Text (optional)</span>
              <textarea className="input min-h-[80px]" value={form.mail_text}
                onChange={(e) => setForm({ ...form, mail_text: e.target.value })}
                placeholder="leer = Standard-Anschreiben mit Nummer und Betrag" />
            </label>
          </div>
        )}

        <div className="flex flex-col-reverse sm:flex-row sm:justify-end gap-2 pt-2">
          <button type="button" className="btn-ghost" onClick={onClose}>Abbrechen</button>
          <button type="submit" className="btn-primary" disabled={busy}>Speichern</button>
        </div>
      </form>
    </Modal>
  );
}
