import { Navigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext.jsx';
import { loginUrl } from '../api/client.js';
import { PageSpinner } from '../components/Spinner.jsx';

const ERRORS = {
  not_allowed: 'Diese Google-Adresse ist nicht freigeschaltet.',
  oauth_failed: 'Anmeldung fehlgeschlagen. Bitte erneut versuchen.',
};

export default function Login() {
  const { user, loading } = useAuth();
  const [params] = useSearchParams();
  const error = params.get('error');

  if (loading) return <PageSpinner />;
  if (user) return <Navigate to="/buchungen" replace />;

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
          <span className="text-4xl font-black tracking-wordmark text-paper">
            Tab<span className="text-royal-soft">_</span>
          </span>
          <p className="mt-2 text-sm text-paper/70">EÜR-Buchhaltung für Kleinunternehmer</p>
        </div>

        <div className="card p-6 space-y-4">
          {error && (
            <div className="p-3 rounded bg-red-50 border-l-4 border-red-500 text-red-900 text-sm">
              {ERRORS[error] || 'Anmeldung fehlgeschlagen.'}
            </div>
          )}
          <p className="text-sm text-ink/60">Melde dich mit deinem freigeschalteten Google-Konto an.</p>
          <a href={loginUrl} className="btn-primary w-full shadow-lg gap-2">
            <svg viewBox="0 0 24 24" className="h-4 w-4" aria-hidden="true">
              <path
                fill="currentColor"
                d="M21.35 11.1H12v2.98h5.35c-.23 1.4-1.63 4.1-5.35 4.1a5.16 5.16 0 1 1 0-10.32c1.47 0 2.46.63 3.02 1.17l2.06-1.99A8.03 8.03 0 0 0 12 4.5 8.5 8.5 0 1 0 12 21.5c4.91 0 8.15-3.45 8.15-8.3 0-.56-.06-.99-.14-1.42z"
              />
            </svg>
            Mit Google anmelden
          </a>
        </div>
      </div>
    </div>
  );
}
