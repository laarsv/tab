import { useEffect, useState } from 'react';
import { Navigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext.jsx';
import { api, apiError, loginUrl } from '../api/client.js';
import { PageSpinner } from '../components/Spinner.jsx';
import Wordmark from '../components/Wordmark.jsx';

const ERRORS = {
  not_allowed: 'Diese Google-Adresse ist nicht freigeschaltet.',
  oauth_failed: 'Anmeldung fehlgeschlagen. Bitte erneut versuchen.',
};

export default function Login() {
  const { user, loading } = useAuth();
  const [params] = useSearchParams();
  const oauthError = params.get('error');

  const [passwortAktiv, setPasswortAktiv] = useState(false);
  const [modus, setModus] = useState('login'); // login | register | verify | reset1 | reset2
  const [form, setForm] = useState({ email: '', passwort: '', passwort2: '', name: '', code: '' });
  const [hinweis, setHinweis] = useState(null); // { typ: 'ok'|'fehler', text }
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.get('/api/auth/methoden').then((r) => setPasswortAktiv(Boolean(r.data.passwort))).catch(() => {});
  }, []);

  if (loading) return <PageSpinner />;
  if (user) return <Navigate to="/buchungen" replace />;

  function wechsle(m) {
    setModus(m);
    setHinweis(null);
  }

  async function absenden(e) {
    e.preventDefault();
    setHinweis(null);
    setBusy(true);
    try {
      if (modus === 'login') {
        await api.post('/api/auth/passwort-login', { email: form.email, passwort: form.passwort });
        window.location.href = '/buchungen';
      } else if (modus === 'register') {
        if (form.passwort.length < 8) throw { selbst: 'Passwort: mindestens 8 Zeichen.' };
        if (form.passwort !== form.passwort2) throw { selbst: 'Die Passwörter stimmen nicht überein.' };
        await api.post('/api/auth/register', {
          email: form.email, passwort: form.passwort, name: form.name.trim() || null,
        });
        setHinweis({ typ: 'ok', text: `Code an ${form.email} gesendet — bitte unten eingeben.` });
        setModus('verify');
      } else if (modus === 'verify') {
        await api.post('/api/auth/verify', { email: form.email, code: form.code.trim() });
        window.location.href = '/buchungen';
      } else if (modus === 'reset1') {
        await api.post('/api/auth/reset-anfordern', { email: form.email });
        setHinweis({ typ: 'ok', text: 'Falls ein Konto existiert, ist ein Code unterwegs.' });
        setModus('reset2');
      } else if (modus === 'reset2') {
        if (form.passwort.length < 8) throw { selbst: 'Passwort: mindestens 8 Zeichen.' };
        await api.post('/api/auth/reset', {
          email: form.email, code: form.code.trim(), passwort: form.passwort,
        });
        setHinweis({ typ: 'ok', text: 'Passwort geändert — jetzt einloggen.' });
        setModus('login');
      }
    } catch (err) {
      setHinweis({ typ: 'fehler', text: err?.selbst || apiError(err) });
    } finally {
      setBusy(false);
    }
  }

  const feld = 'input';

  return (
    <div className="relative min-h-screen bg-ink overflow-hidden flex items-center justify-center">
      <div
        className="pointer-events-none absolute -top-32 -left-32 h-[520px] w-[820px] rounded-[50%] bg-royal-soft/25 blur-2xl"
        style={{ transform: 'rotate(-40deg)' }}
      />
      <div
        className="pointer-events-none absolute -bottom-40 -right-40 h-[420px] w-[680px] rounded-[50%] bg-royal/15 blur-3xl"
        style={{ transform: 'rotate(-40deg)' }}
      />
      <div className="relative z-10 w-full max-w-md px-4 sm:px-8 py-12">
        <div className="text-center mb-8">
          {/* Produkt-Lockup (standalone) gemäß CI — auf Ink: weiß, _toolname in Royal Soft */}
          <Wordmark onInk className="text-4xl" />
          <p className="mt-2 text-sm text-paper/70">
            Die bessere Excel-Liste für deine EÜR (§19 UStG)
          </p>
          <p className="mt-1 text-xs text-paper/50">
            Keine Steuerberatung — Zahlen vor der Abgabe prüfen (lassen).
          </p>
        </div>

        <div className="card p-6 space-y-4">
          {oauthError && (
            <div className="p-3 rounded bg-red-50 border-l-4 border-red-500 text-red-900 text-sm">
              {ERRORS[oauthError] || 'Anmeldung fehlgeschlagen.'}
            </div>
          )}
          {hinweis && (
            <div className={`p-3 rounded text-sm ${hinweis.typ === 'ok'
              ? 'bg-royal-soft/20 text-ink'
              : 'bg-red-50 border-l-4 border-red-500 text-red-900'}`}>
              {hinweis.text}
            </div>
          )}

          {modus === 'login' && (
            <>
              <a href={loginUrl} className="btn-primary w-full shadow-lg gap-2">
                <svg viewBox="0 0 24 24" className="h-4 w-4" aria-hidden="true">
                  <path
                    fill="currentColor"
                    d="M21.35 11.1H12v2.98h5.35c-.23 1.4-1.63 4.1-5.35 4.1a5.16 5.16 0 1 1 0-10.32c1.47 0 2.46.63 3.02 1.17l2.06-1.99A8.03 8.03 0 0 0 12 4.5 8.5 8.5 0 1 0 12 21.5c4.91 0 8.15-3.45 8.15-8.3 0-.56-.06-.99-.14-1.42z"
                  />
                </svg>
                Mit Google anmelden
              </a>
              {passwortAktiv && (
                <>
                  <div className="flex items-center gap-3 text-xs text-ink/40">
                    <span className="h-px flex-1 bg-ink/10" /> oder mit E-Mail <span className="h-px flex-1 bg-ink/10" />
                  </div>
                  <form onSubmit={absenden} className="space-y-3">
                    <input className={feld} type="email" placeholder="E-Mail" value={form.email}
                      onChange={(e) => setForm({ ...form, email: e.target.value })} />
                    <input className={feld} type="password" placeholder="Passwort" value={form.passwort}
                      onChange={(e) => setForm({ ...form, passwort: e.target.value })} />
                    <button type="submit" className="btn-outline w-full" disabled={busy}>
                      {busy ? 'Prüft…' : 'Anmelden'}
                    </button>
                  </form>
                  <div className="flex justify-between text-xs">
                    <button className="text-royal font-medium hover:underline" onClick={() => wechsle('register')}>
                      Neu hier? Registrieren
                    </button>
                    <button className="text-ink/50 hover:underline" onClick={() => wechsle('reset1')}>
                      Passwort vergessen?
                    </button>
                  </div>
                </>
              )}
            </>
          )}

          {modus === 'register' && (
            <form onSubmit={absenden} className="space-y-3">
              <div className="text-sm font-bold">Konto erstellen</div>
              <input className={feld} type="email" placeholder="E-Mail" value={form.email}
                onChange={(e) => setForm({ ...form, email: e.target.value })} autoFocus />
              <input className={feld} placeholder="Name (optional)" value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })} />
              <input className={feld} type="password" placeholder="Passwort (min. 8 Zeichen)" value={form.passwort}
                onChange={(e) => setForm({ ...form, passwort: e.target.value })} />
              <input className={feld} type="password" placeholder="Passwort wiederholen" value={form.passwort2}
                onChange={(e) => setForm({ ...form, passwort2: e.target.value })} />
              <button type="submit" className="btn-primary w-full" disabled={busy}>
                {busy ? 'Sendet Code…' : 'Registrieren'}
              </button>
              <button type="button" className="text-xs text-ink/50 hover:underline" onClick={() => wechsle('login')}>
                ← zurück zur Anmeldung
              </button>
            </form>
          )}

          {modus === 'verify' && (
            <form onSubmit={absenden} className="space-y-3">
              <div className="text-sm font-bold">E-Mail bestätigen</div>
              <p className="text-xs text-ink/60">Wir haben einen 6-stelligen Code an {form.email} gesendet.</p>
              <input className={`${feld} tabular-nums tracking-widest text-center`} inputMode="numeric"
                maxLength={6} placeholder="000000" value={form.code} autoFocus
                onChange={(e) => setForm({ ...form, code: e.target.value })} />
              <button type="submit" className="btn-primary w-full" disabled={busy}>
                {busy ? 'Prüft…' : 'Bestätigen & loslegen'}
              </button>
              <button type="button" className="text-xs text-ink/50 hover:underline" onClick={() => wechsle('login')}>
                ← zurück zur Anmeldung
              </button>
            </form>
          )}

          {(modus === 'reset1' || modus === 'reset2') && (
            <form onSubmit={absenden} className="space-y-3">
              <div className="text-sm font-bold">Passwort zurücksetzen</div>
              <input className={feld} type="email" placeholder="E-Mail" value={form.email}
                onChange={(e) => setForm({ ...form, email: e.target.value })} disabled={modus === 'reset2'} />
              {modus === 'reset2' && (
                <>
                  <input className={`${feld} tabular-nums tracking-widest text-center`} inputMode="numeric"
                    maxLength={6} placeholder="Code aus der Mail" value={form.code} autoFocus
                    onChange={(e) => setForm({ ...form, code: e.target.value })} />
                  <input className={feld} type="password" placeholder="Neues Passwort (min. 8 Zeichen)"
                    value={form.passwort}
                    onChange={(e) => setForm({ ...form, passwort: e.target.value })} />
                </>
              )}
              <button type="submit" className="btn-primary w-full" disabled={busy}>
                {busy ? 'Bitte warten…' : modus === 'reset1' ? 'Code anfordern' : 'Passwort setzen'}
              </button>
              <button type="button" className="text-xs text-ink/50 hover:underline" onClick={() => wechsle('login')}>
                ← zurück zur Anmeldung
              </button>
            </form>
          )}

          {modus === 'login' && (
            <p className="text-xs text-ink/50">
              Kostenlos, keine versteckten Haken. Mit der Anmeldung startet dein eigener,
              privater Bereich.
            </p>
          )}
        </div>

        <p className="mt-6 text-center text-xs text-paper/50">
          ein Werkzeug von{' '}
          <a
            href="https://vrwb.de"
            target="_blank"
            rel="noreferrer"
            className="font-black tracking-wordmark text-paper/80 hover:text-paper"
          >
            vrwb<span className="text-royal-soft wordmark-cursor-blink">_</span>
          </a>
        </p>
      </div>
    </div>
  );
}
