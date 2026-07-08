import { useState } from 'react';
import { Navigate } from 'react-router-dom';
import toast from 'react-hot-toast';
import { useAuth } from '../auth/AuthContext.jsx';
import { apiError } from '../api/client.js';
import Spinner from '../components/Spinner.jsx';

export default function Login() {
  const { token, user, login } = useAuth();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);

  if (token && user) return <Navigate to="/buchungen" replace />;

  async function onSubmit(e) {
    e.preventDefault();
    setBusy(true);
    try {
      await login(username.trim(), password);
      window.location.href = '/buchungen';
    } catch (err) {
      toast.error(apiError(err, 'Anmeldung fehlgeschlagen.'));
      setBusy(false);
    }
  }

  return (
    <div className="relative min-h-screen bg-ink overflow-hidden flex items-center justify-center">
      <div
        className="pointer-events-none absolute -top-32 -left-32 h-[520px] w-[820px] rounded-[50%] bg-mint-soft/25 blur-2xl"
        style={{ transform: 'rotate(-40deg)' }}
      />
      <div
        className="pointer-events-none absolute -bottom-40 -right-40 h-[420px] w-[680px] rounded-[50%] bg-mint/15 blur-3xl"
        style={{ transform: 'rotate(-40deg)' }}
      />
      <div className="relative z-10 w-full max-w-md px-4 sm:px-8 py-12">
        <div className="text-center mb-8">
          <span className="text-4xl font-black tracking-wordmark text-paper">
            Tab<span className="text-mint">.</span>
          </span>
          <p className="mt-2 text-sm text-paper/70">EÜR-Buchhaltung für Kleinunternehmer</p>
        </div>

        <form onSubmit={onSubmit} className="card p-6 space-y-4">
          <label className="block">
            <span className="field-label">Benutzername</span>
            <input
              className="input"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoComplete="username"
              autoFocus
            />
          </label>
          <label className="block">
            <span className="field-label">Passwort</span>
            <input
              type="password"
              className="input"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
            />
          </label>
          <button type="submit" disabled={busy} className="btn-primary w-full shadow-lg">
            {busy ? <Spinner size="sm" /> : 'Anmelden'}
          </button>
        </form>
      </div>
    </div>
  );
}
