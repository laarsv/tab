import { useMemo, useState } from 'react';
import toast from 'react-hot-toast';
import { api, apiError } from '../api/client.js';
import { DialogFuss, PositionenEditor, SchalterZeile, positionAusApi, positionenFuerSumme, satzVon } from './DialogParts.jsx';
import { hinweisFuer, istRegel, positionsSummen, steuerhinweisOptionen } from '../lib/besteuerung.js';
import Dropdown from './Dropdown.jsx';
import Modal from './Modal.jsx';
import { Hinweis } from './PageParts.jsx';
import { formatEuro, formatDateDE, parseEuroToCent, centToInput } from '../lib/format.js';
import { naechsterTermin } from '../lib/intervall.js';

const INTERVALL_OPTIONS = [
  { value: 'monatlich', label: 'monatlich' },
  { value: 'vierteljaehrlich', label: 'vierteljährlich' },
  { value: 'jaehrlich', label: 'jährlich' },
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
export default function AboModal({ abo, prefill, gewerbeId, gewerbeObj = null, kontakte = [], mailKonfiguriert, onClose, onSaved }) {
  const isEdit = Boolean(abo?.id);
  const src = abo || prefill || {};
  const [form, setForm] = useState(() => ({
    empfaenger_name: src.empfaenger_name || '',
    empfaenger_anschrift: src.empfaenger_anschrift || '',
    empfaenger_email: src.empfaenger_email || '',
    notiz: src.notiz || '',
    steuerhinweis: src.steuerhinweis || 'ku19',
    intervall: abo?.intervall || 'monatlich',
    // Aus bestehender Rechnung: die deckt den aktuellen Zeitraum ab — das Abo
    // startet daher eine Periode nach ihrem Rechnungsdatum.
    naechste_am:
      abo?.naechste_am ||
      (prefill?.datum ? naechsterTermin(prefill.datum, 'monatlich') : ersterDesNaechstenMonats()),
    endet_am: abo?.endet_am || '',
    auto_senden: Boolean(abo?.auto_senden),
    betreff: abo?.betreff || '',
    mail_text: abo?.mail_text || '',
    positionen: (src.positionen || []).length
      ? src.positionen.map(positionAusApi)
      : [emptyPos()],
  }));
  const [busy, setBusy] = useState(false);

  // Regelbesteuerung im Jahr des nächsten Termins: Netto-Preise mit Steuersatz, Summe brutto
  const regel = istRegel(gewerbeObj, String(form.naechste_am).slice(0, 4));
  const total = useMemo(
    () => positionsSummen(positionenFuerSumme(form.positionen, regel)).brutto_cent,
    [form.positionen, regel],
  );

  async function save(e) {
    e.preventDefault();
    if (!form.empfaenger_name.trim()) return toast.error('Empfänger ist Pflicht.');
    if (form.auto_senden && !form.empfaenger_email.trim())
      return toast.error('Auto-Versand braucht eine Empfänger-E-Mail.');
    if (form.endet_am && form.endet_am < form.naechste_am)
      return toast.error('Die letzte Rechnung liegt vor der nächsten Rechnung.');
    const payloadPos = [];
    for (const p of form.positionen) {
      const preis = parseEuroToCent(p.preisInput);
      const menge = Number(String(p.menge).replace(',', '.'));
      if (!p.beschreibung.trim()) return toast.error('Jede Position braucht eine Beschreibung.');
      if (!preis || preis <= 0 || !Number.isFinite(menge) || menge <= 0)
        return toast.error('Bitte Menge und Preis prüfen.');
      payloadPos.push({ beschreibung: p.beschreibung.trim(), menge, einzelpreis_cent: preis, ust_bp: satzVon(p, regel) });
    }
    const body = {
      empfaenger_name: form.empfaenger_name.trim(),
      empfaenger_anschrift: form.empfaenger_anschrift.trim() || null,
      empfaenger_email: form.empfaenger_email.trim() || null,
      notiz: form.notiz.trim() || null,
      steuerhinweis: hinweisFuer(form.steuerhinweis, regel),
      intervall: form.intervall,
      naechste_am: form.naechste_am,
      endet_am: form.endet_am || null,
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
        {prefill && !isEdit && (
          <Hinweis className="text-xs">
            <strong>Wichtig:</strong> Das Abo erstellt zum Stichtag jeweils eine <strong>neue</strong> Rechnung — die
            bestehende Rechnung ({formatDateDE(prefill.datum)}) wird dadurch nicht versendet, sie deckt den aktuellen
            Zeitraum ab. Der Start ist deshalb eine Periode später vorbelegt.
          </Hinweis>
        )}
        {kontakte.length > 0 && (
          <div className="block">
            <span className="field-label">Aus Kontakten übernehmen</span>
            <Dropdown
              value=""
              placeholder="Kontakt wählen…"
              searchable
              options={kontakte.map((k) => ({ value: String(k.id), label: k.name }))}
              onChange={(v) => {
                const k = kontakte.find((x) => String(x.id) === String(v));
                if (k)
                  setForm((f) => ({
                    ...f,
                    empfaenger_name: k.name,
                    empfaenger_anschrift: k.anschrift || '',
                    empfaenger_email: k.email || '',
                  }));
              }}
            />
          </div>
        )}
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

        <div className="grid grid-cols-2 sm:grid-cols-3 gap-x-5 gap-y-2">
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
          <label className="col-span-2 block sm:col-span-1">
            <span className="field-label">Letzte Rechnung am (optional)</span>
            <input type="date" className="input" value={form.endet_am} min={form.naechste_am || undefined}
              onChange={(e) => setForm({ ...form, endet_am: e.target.value })} />
          </label>
        </div>
        <p className="!mt-1.5 text-[13px] text-ink/60">
          {form.endet_am
            ? `Bis einschließlich ${formatDateDE(form.endet_am)} entstehen Rechnungen, danach endet das Abo von selbst.`
            : 'Ohne Enddatum läuft das Abo, bis du es pausierst oder löschst.'}
        </p>

        <PositionenEditor
          positionen={form.positionen}
          onChange={(positionen) => setForm((f) => ({ ...f, positionen }))}
          summeCent={total}
          platzhalter="z. B. Betreuung {monat}"
          gewerbeId={gewerbeId}
          regel={regel}
        />
        <Hinweis className="text-xs">
          Platzhalter <code>{'{monat}'}</code> wird durch den Abrechnungsmonat ersetzt (z. B. „Betreuung 08/2026") —
          funktioniert in Positionen, Notiz, Betreff und Mail-Text. Das Leistungsdatum setzt Tab automatisch auf den
          Abrechnungsmonat.
        </Hinweis>

        <div className="block">
          <span className="field-label">Steuer-Hinweis</span>
          <Dropdown value={hinweisFuer(form.steuerhinweis, regel)} onChange={(v) => setForm({ ...form, steuerhinweis: String(v) })}
            options={steuerhinweisOptionen(regel)} />
        </div>

        <SchalterZeile
          titel="Automatisch per E-Mail senden"
          hinweis={`Sonst wird die Rechnung nur als Entwurf angelegt und du klickst selbst auf Senden.${!mailKonfiguriert ? ' Achtung: Für dein Login ist noch kein App-Passwort hinterlegt (Profilzeile → E-Mail-Versand) — bis dahin bleiben Rechnungen als Entwurf liegen.' : ''}`}
          checked={form.auto_senden}
          onChange={(an) => setForm({ ...form, auto_senden: an })}
        />

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

        <DialogFuss>
          <button type="button" className="btn-ghost" onClick={onClose}>
            Abbrechen
          </button>
          <button type="submit" className="btn-primary" disabled={busy}>
            Speichern
          </button>
        </DialogFuss>
      </form>
    </Modal>
  );
}
