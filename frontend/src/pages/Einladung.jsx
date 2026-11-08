import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { api, apiError } from '../api/client.js';
import { PageSpinner } from '../components/Spinner.jsx';
import Wordmark from '../components/Wordmark.jsx';

// Öffentliche Seite: die Steuerberatung legt mit dem Einladungslink ihren Zugang an.
export default function Einladung() {
  const { token } = useParams();
  const [info, setInfo] = useState(null);
  const [fehler, setFehler] = useState('');
  const [form, setForm] = useState({ name: '', email: '', passwort: '', passwort2: '' });
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api
      .get(`/api/berater/einladung/${encodeURIComponent(token)}`)
      .then((r) => setInfo(r.data))
      .catch((e) => setFehler(apiError(e, 'Dieser Einladungslink ist ungültig oder abgelaufen.')));
  }, [token]);

  async function absenden(e) {
    e.preventDefault();
    setFehler('');
    if (form.passwort.length < 12) return setFehler('Das Passwort braucht mindestens 12 Zeichen.');
    if (form.passwort !== form.passwort2) return setFehler('Die Passwörter stimmen nicht überein.');
    setBusy(true);
    try {
      await api.post(`/api/berater/einladung/${encodeURIComponent(token)}/annehmen`, {
        name: form.name.trim(),
        email: form.email.trim(),
        passwort: form.passwort,
      });
      window.location.href = '/berater';
    } catch (err) {
      setFehler(apiError(err));
      setBusy(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-ink px-4 py-12">
      <div className="w-full max-w-md">
        <div className="mb-8 text-center">
          <Wordmark onInk className="text-4xl" />
          <p className="mt-2 text-sm text-paper/70">Zugang für die Steuerberatung</p>
        </div>
        <div className="card space-y-4 p-6">
          {!info && !fehler ? (
            <PageSpinner />
          ) : !info ? (
            <div role="alert" className="rounded border-l-4 border-red-500 bg-red-50 p-3 text-sm text-red-900">
              {fehler}
            </div>
          ) : (
            <form onSubmit={absenden} className="space-y-3">
              <p className="text-sm text-ink/80">
                Du wurdest als <strong>{info.bezeichnung}</strong> eingeladen, die Zahlen einer EÜR in vrwb_tab
                einzusehen. Der Zugang kann <strong>nur lesen</strong>.
              </p>
              {fehler && (
                <div role="alert" className="rounded border-l-4 border-red-500 bg-red-50 p-3 text-sm text-red-900">
                  {fehler}
                </div>
              )}
              <label className="block">
                <span className="field-label">Name</span>
                <input className="input" value={form.name} autoFocus onChange={(e) => setForm({ ...form, name: e.target.value })} />
              </label>
              <label className="block">
                <span className="field-label">E-Mail</span>
                <input className="input" type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
              </label>
              <label className="block">
                <span className="field-label">Passwort (mindestens 12 Zeichen)</span>
                <input className="input" type="password" autoComplete="new-password" value={form.passwort}
                  onChange={(e) => setForm({ ...form, passwort: e.target.value })} />
              </label>
              <label className="block">
                <span className="field-label">Passwort wiederholen</span>
                <input className="input" type="password" autoComplete="new-password" value={form.passwort2}
                  onChange={(e) => setForm({ ...form, passwort2: e.target.value })} />
              </label>
              <button type="submit" className="btn-primary w-full" disabled={busy || !form.name.trim() || !form.email.trim()}>
                {busy ? 'Legt an…' : 'Zugang anlegen'}
              </button>
              <p className="text-xs text-ink/60">Später meldest du dich auf der Anmeldeseite unter „Zugang für die Steuerberatung“ an.</p>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}
