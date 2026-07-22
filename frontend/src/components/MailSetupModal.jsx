import { useEffect, useState } from 'react';
import toast from 'react-hot-toast';
import { api, apiError } from '../api/client.js';
import Dropdown from './Dropdown.jsx';
import Modal from './Modal.jsx';

const PROVIDER_OPTIONS = [
  { value: 'google', label: 'Google / Gmail (App-Passwort)' },
  { value: 'custom', label: 'Eigener Mail-Server (z. B. All-Inkl, IONOS …)' },
];

// Mail-Konto einrichten: Versand (SMTP) + Beleg-Import (IMAP) — je Login,
// Provider Google oder eigener Mail-Server. Passwort verschlüsselt in der DB.
export default function MailSetupModal({ onClose }) {
  const [status, setStatus] = useState(null);
  const [gewerbe, setGewerbe] = useState([]);
  const [busy, setBusy] = useState('');
  const [form, setForm] = useState({
    provider: 'google', passwort: '', smtp_host: '', smtp_port: '', imap_host: '',
    imap_port: '', mail_benutzer: '', absender_email: '', import_adresse: '',
  });

  async function load() {
    try {
      const [res, g] = await Promise.all([
        api.get('/api/einstellungen/mail'),
        api.get('/api/gewerbe'),
      ]);
      setStatus(res.data);
      setGewerbe(g.data);
      setForm((f) => ({
        ...f,
        provider: res.data.provider || 'google',
        smtp_host: res.data.smtp_host || '',
        smtp_port: res.data.smtp_port || '',
        imap_host: res.data.imap_host || '',
        imap_port: res.data.imap_port || '',
        mail_benutzer: res.data.mail_benutzer || '',
        absender_email: res.data.absender_email || '',
        import_adresse: res.data.import_adresse || '',
      }));
    } catch (e) {
      toast.error(apiError(e));
    }
  }

  useEffect(() => {
    load();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const custom = form.provider === 'custom';

  async function save(e) {
    e.preventDefault();
    if (!form.passwort.trim()) return toast.error('Bitte Passwort eingeben.');
    setBusy('save');
    try {
      await api.put('/api/einstellungen/mail', {
        provider: form.provider,
        app_passwort: form.passwort.trim(),
        smtp_host: form.smtp_host.trim() || null,
        smtp_port: form.smtp_port ? Number(form.smtp_port) : null,
        imap_host: form.imap_host.trim() || null,
        imap_port: form.imap_port ? Number(form.imap_port) : null,
        mail_benutzer: form.mail_benutzer.trim() || null,
        absender_email: form.absender_email.trim() || null,
        import_adresse: form.import_adresse.trim() || null,
      });
      toast.success('Gespeichert — Login beim Mail-Server hat geklappt.');
      setForm((f) => ({ ...f, passwort: '' }));
      await load();
    } catch (err) {
      toast.error(apiError(err), { duration: 10000 });
    } finally {
      setBusy('');
    }
  }

  async function test() {
    setBusy('test');
    try {
      await api.post('/api/einstellungen/mail/test');
      toast.success('Test-Mail gesendet — check das Absender-Postfach.');
    } catch (err) {
      toast.error(apiError(err), { duration: 10000 });
    } finally {
      setBusy('');
    }
  }

  async function remove() {
    if (!window.confirm('Mail-Konto aus Tab entfernen?')) return;
    setBusy('remove');
    try {
      await api.delete('/api/einstellungen/mail');
      toast.success('Entfernt.');
      await load();
    } catch (err) {
      toast.error(apiError(err));
    } finally {
      setBusy('');
    }
  }

  async function saveImport(aktiv, gewerbeId) {
    setBusy('import');
    try {
      const res = await api.put('/api/einstellungen/mail/import', {
        aktiv,
        gewerbe_id: gewerbeId ? Number(gewerbeId) : null,
      });
      setStatus(res.data);
      toast.success(aktiv ? 'Mail-Import aktiv — Abruf alle 10 Minuten.' : 'Mail-Import aus.');
    } catch (err) {
      toast.error(apiError(err), { duration: 8000 });
    } finally {
      setBusy('');
    }
  }

  return (
    <Modal title="E-Mail-Versand & Beleg-Import" onClose={onClose} maxWidth="max-w-2xl">
      <div className="space-y-4">
        {status?.konfiguriert && (
          <div className="rounded-lg bg-royal-soft/15 p-3 text-sm text-ink/80 flex items-center justify-between gap-2">
            <span>
              ✓ Konto aktiv — Rechnungen gehen von <strong>{status.absender}</strong> raus.
            </span>
            <div className="flex gap-2 shrink-0">
              <button className="btn-outline btn-sm" onClick={test} disabled={busy !== ''}>
                {busy === 'test' ? 'Sendet…' : 'Test-Mail'}
              </button>
              <button className="btn-ghost btn-sm text-red-700" onClick={remove} disabled={busy !== ''}>
                Entfernen
              </button>
            </div>
          </div>
        )}

        <form onSubmit={save} className="space-y-3">
          <div className="block">
            <span className="field-label">Mail-Anbieter</span>
            <Dropdown
              value={form.provider}
              onChange={(v) => setForm({ ...form, provider: String(v) })}
              options={PROVIDER_OPTIONS}
            />
          </div>

          {custom ? (
            <>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-5 gap-y-2">
                <label className="block">
                  <span className="field-label">Absender-Adresse (steht auf Rechnungen)</span>
                  <input className="input" value={form.absender_email} placeholder="rechnung@deine-domain.de"
                    onChange={(e) => setForm({ ...form, absender_email: e.target.value })} />
                </label>
                <label className="block">
                  <span className="field-label">Benutzername (meist die Mail-Adresse)</span>
                  <input className="input" value={form.mail_benutzer} placeholder="rechnung@deine-domain.de"
                    onChange={(e) => setForm({ ...form, mail_benutzer: e.target.value })} />
                </label>
                <label className="block">
                  <span className="field-label">SMTP-Server (Versand)</span>
                  <input className="input" value={form.smtp_host} placeholder="z. B. w0123456.kasserver.com"
                    onChange={(e) => setForm({ ...form, smtp_host: e.target.value })} />
                </label>
                <label className="block">
                  <span className="field-label">SMTP-Port</span>
                  <input className="input tabular-nums" value={form.smtp_port} placeholder="587"
                    onChange={(e) => setForm({ ...form, smtp_port: e.target.value })} />
                </label>
                <label className="block">
                  <span className="field-label">IMAP-Server (Beleg-Import, optional)</span>
                  <input className="input" value={form.imap_host} placeholder="leer = wie SMTP-Server"
                    onChange={(e) => setForm({ ...form, imap_host: e.target.value })} />
                </label>
                <label className="block">
                  <span className="field-label">IMAP-Port</span>
                  <input className="input tabular-nums" value={form.imap_port} placeholder="993"
                    onChange={(e) => setForm({ ...form, imap_port: e.target.value })} />
                </label>
              </div>
              <label className="block">
                <span className="field-label">Beleg-Import-Adresse (optional)</span>
                <input className="input" value={form.import_adresse} placeholder="z. B. belege@deine-domain.de (Alias aufs selbe Postfach)"
                  onChange={(e) => setForm({ ...form, import_adresse: e.target.value })} />
                <span className="block text-xs text-ink/60 mt-1">
                  Leer = die +tab-Variante deiner Absender-Adresse. Falls dein Anbieter
                  +Adressen nicht zustellt, lege einen Alias an und trage ihn hier ein.
                </span>
              </label>
            </>
          ) : (
            <ol className="text-sm text-ink/70 list-decimal ml-5 space-y-1">
              <li>2-Faktor-Authentifizierung im Google-Konto aktivieren (falls noch nicht).</li>
              <li>
                <a className="text-royal font-medium hover:underline" href="https://myaccount.google.com/apppasswords" target="_blank" rel="noreferrer">
                  myaccount.google.com/apppasswords
                </a>{' '}
                öffnen, App-Passwort „Tab" erstellen.
              </li>
              <li>Die 16 Zeichen unten einfügen (Leerzeichen egal).</li>
            </ol>
          )}

          <label className="block">
            <span className="field-label">
              {custom ? 'Postfach-Passwort' : status?.konfiguriert ? 'Neues App-Passwort (ersetzt das alte)' : 'App-Passwort'}
            </span>
            <input
              type="password"
              className="input"
              value={form.passwort}
              onChange={(e) => setForm({ ...form, passwort: e.target.value })}
              placeholder={custom ? '••••••••' : 'xxxx xxxx xxxx xxxx'}
              autoComplete="off"
            />
            <span className="block text-xs text-ink/60 mt-1">
              Wird verschlüsselt gespeichert und beim Speichern direkt am Mail-Server getestet.
            </span>
          </label>
          <div className="flex flex-col-reverse sm:flex-row sm:justify-end gap-2">
            <button type="button" className="btn-ghost" onClick={onClose}>
              Schließen
            </button>
            <button type="submit" className="btn-primary" disabled={busy !== ''}>
              {busy === 'save' ? 'Prüft…' : 'Speichern & prüfen'}
            </button>
          </div>
        </form>

        <div className="pt-4 border-t border-ink/10 space-y-3">
          <div className="text-[11px] font-bold tracking-wider text-ink/60 uppercase">
            Beleg-Eingang per E-Mail
          </div>
          <p className="text-sm text-ink/70">
            Belege einfach weiterleiten an{' '}
            <code className="font-mono text-royal font-medium break-all">
              {status?.import_ziel || '…'}
            </code>{' '}
            — Tab holt sie alle 10 Minuten ab und legt die Anhänge (PDF/JPG/PNG/XML) in den
            Eingang. Importiert werden nur Mails von dir selbst bzw. freigeschalteten Absendern;
            an deinem Postfach wird nichts verändert.
          </p>
          <div className="flex flex-wrap items-center gap-3">
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                className="rounded border-ink/30 text-royal focus:ring-royal"
                checked={Boolean(status?.import_aktiv)}
                disabled={!status?.konfiguriert || busy !== ''}
                onChange={(e) => saveImport(e.target.checked, status?.import_gewerbe_id)}
              />
              <span className="font-bold">Mail-Import aktiv</span>
            </label>
            {status?.import_aktiv && gewerbe.length > 1 && (
              <div className="flex items-center gap-2 text-sm">
                <span className="text-ink/60">in Gewerbe:</span>
                <Dropdown
                  value={String(status?.import_gewerbe_id || gewerbe[0]?.id || '')}
                  onChange={(v) => saveImport(true, v)}
                  options={gewerbe.map((g) => ({ value: String(g.id), label: g.name }))}
                  variant="ghost"
                />
              </div>
            )}
          </div>
          {!status?.konfiguriert && (
            <p className="text-xs text-ink/50">
              Voraussetzung: Mail-Konto oben hinterlegen (der Abruf läuft über IMAP mit
              denselben Zugangsdaten).
            </p>
          )}
        </div>
      </div>
    </Modal>
  );
}
