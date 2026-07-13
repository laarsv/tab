import { useEffect, useState } from 'react';
import toast from 'react-hot-toast';
import { api, apiError } from '../api/client.js';
import Modal from './Modal.jsx';

// E-Mail-Versand einrichten: Gmail-App-Passwort des eingeloggten Nutzers.
// Individuell je Login (verschlüsselt in der DB), Versand von der eigenen Adresse.
export default function MailSetupModal({ onClose }) {
  const [status, setStatus] = useState(null); // { email, konfiguriert }
  const [passwort, setPasswort] = useState('');
  const [busy, setBusy] = useState('');

  async function load() {
    try {
      const res = await api.get('/api/einstellungen/mail');
      setStatus(res.data);
    } catch (e) {
      toast.error(apiError(e));
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function save(e) {
    e.preventDefault();
    if (!passwort.trim()) return toast.error('Bitte App-Passwort eingeben.');
    setBusy('save');
    try {
      await api.put('/api/einstellungen/mail', { app_passwort: passwort.trim() });
      toast.success('Gespeichert — Login bei Google hat geklappt.');
      setPasswort('');
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
      toast.success('Test-Mail an dich selbst gesendet — check dein Postfach.');
    } catch (err) {
      toast.error(apiError(err), { duration: 10000 });
    } finally {
      setBusy('');
    }
  }

  async function remove() {
    if (!window.confirm('App-Passwort aus Tab entfernen?')) return;
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

  return (
    <Modal title="E-Mail-Versand einrichten" onClose={onClose}>
      <div className="space-y-4">
        <p className="text-sm text-ink/70">
          Rechnungen werden direkt von <strong>{status?.email || 'deiner Adresse'}</strong>{' '}
          verschickt (landen auch in deinem „Gesendet"-Ordner). Dafür braucht Tab einmalig ein{' '}
          <strong>App-Passwort</strong> deines Google-Kontos — nicht dein normales Passwort.
        </p>
        <ol className="text-sm text-ink/70 list-decimal ml-5 space-y-1">
          <li>2-Faktor-Authentifizierung im Google-Konto aktivieren (falls noch nicht).</li>
          <li>
            <a
              className="text-royal font-medium hover:underline"
              href="https://myaccount.google.com/apppasswords"
              target="_blank"
              rel="noreferrer"
            >
              myaccount.google.com/apppasswords
            </a>{' '}
            öffnen, App-Passwort „Tab" erstellen.
          </li>
          <li>Die 16 Zeichen hier einfügen (Leerzeichen egal).</li>
        </ol>

        {status?.konfiguriert && (
          <div className="rounded-lg bg-royal-soft/15 p-3 text-sm text-ink/80 flex items-center justify-between gap-2">
            <span>✓ App-Passwort hinterlegt — Versand aktiv.</span>
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
          <label className="block">
            <span className="field-label">
              {status?.konfiguriert ? 'Neues App-Passwort (ersetzt das alte)' : 'App-Passwort'}
            </span>
            <input
              type="password"
              className="input"
              value={passwort}
              onChange={(e) => setPasswort(e.target.value)}
              placeholder="xxxx xxxx xxxx xxxx"
              autoComplete="off"
            />
            <span className="block text-xs text-ink/60 mt-1">
              Wird verschlüsselt gespeichert und beim Speichern direkt bei Google getestet.
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
      </div>
    </Modal>
  );
}
