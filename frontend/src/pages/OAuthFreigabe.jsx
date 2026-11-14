import { useEffect, useState } from 'react';
import { Navigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext.jsx';
import { api, apiError } from '../api/client.js';
import { Schalter } from '../components/DialogParts.jsx';
import { PageSpinner } from '../components/Spinner.jsx';
import Wordmark from '../components/Wordmark.jsx';

// Freigabe für KI-Apps (OAuth, siehe routes/oauth.py): Eine App (z. B. Claude.ai) will lesend auf die Buchhaltung
// zugreifen. Der Server prüft die Anfrage bei „Zulassen" noch einmal vollständig — diese Seite zeigt nur an.
export const OAUTH_ZURUECK = 'tab_oauth_zurueck';

export default function OAuthFreigabe() {
  const { user, loading } = useAuth();
  const [params] = useSearchParams();
  const [info, setInfo] = useState(null);
  const [fehler, setFehler] = useState('');
  const [busy, setBusy] = useState(false);
  const [vorschlaege, setVorschlaege] = useState(false);
  const anfrage = Object.fromEntries(
    ['client_id', 'redirect_uri', 'code_challenge', 'state', 'scope', 'resource'].map((k) => [k, params.get(k)]).filter(([, v]) => v),
  );

  useEffect(() => {
    if (!user) return;
    api
      .get('/api/oauth/freigabe/info', { params: { client_id: anfrage.client_id, redirect_uri: anfrage.redirect_uri } })
      .then((r) => setInfo(r.data))
      .catch((e) => setFehler(apiError(e, 'Diese Anfrage ist ungültig oder abgelaufen.')));
  }, [user]); // eslint-disable-line react-hooks/exhaustive-deps

  if (loading) return <PageSpinner />;
  if (!user) {
    // Erst anmelden, danach führt das Layout hierher zurück.
    try {
      sessionStorage.setItem(OAUTH_ZURUECK, JSON.stringify({ q: window.location.search, t: Date.now() }));
    } catch {
      /* ohne Speicher geht es nur nicht automatisch weiter */
    }
    return <Navigate to="/login" replace />;
  }

  async function antworten(erlauben) {
    setBusy(true);
    try {
      const res = await api.post('/api/oauth/freigabe', { ...anfrage, erlauben, vorschlaege });
      window.location.href = res.data.redirect;
    } catch (e) {
      setFehler(apiError(e, 'Die Freigabe ist fehlgeschlagen.'));
      setBusy(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-ink px-4 py-12">
      <div className="w-full max-w-md">
        <div className="mb-8 text-center">
          <Wordmark onInk className="text-4xl" />
        </div>
        <div className="card space-y-4 p-6">
          {fehler && !info ? (
            <div role="alert" className="rounded border-l-4 border-red-500 bg-red-50 p-3 text-sm text-red-900">{fehler}</div>
          ) : !info ? (
            <PageSpinner />
          ) : (
            <>
              <h1 className="text-2xl font-black leading-tight">„{info.client_name}“ möchte mitlesen</h1>
              <p className="text-sm text-ink/80">
                Die App bekommt <strong>nur lesenden</strong> Zugriff auf die Buchhaltung von <strong>{info.konto}</strong>: Kennzahlen,
                EÜR-Summenblatt, Buchungen, Rechnungen, Anlagen, Fristen und die Übersicht. Buchen, ändern oder löschen kann sie nicht,
                und Belegdateien, Bank, Einstellungen und Mail-Zugang bleiben tabu.
              </p>
              <div className="flex items-start gap-3 rounded-xl bg-surface p-3">
                <Schalter checked={vorschlaege} onChange={setVorschlaege} label="Darf Änderungen vorschlagen" />
                <div className="text-[13px] leading-snug">
                  <div className="font-bold">Darf auch Änderungen vorschlagen</div>
                  <div className="text-ink/70">
                    Z. B. ein Abo umstellen oder einen Rechnungsentwurf anlegen — als Vorschlag, den du in Tab bestätigst. Ohne diesen Schalter
                    bleibt es beim Lesen.
                  </div>
                </div>
              </div>
              <p className="rounded-xl bg-royal/[0.08] px-3 py-2 text-sm">
                Die Antwort geht an <strong>{info.ziel}</strong>. Gib nur frei, wenn du diese App gerade selbst verbunden hast. Was die App
                abfragt, geht an deren Anbieter.
              </p>
              {fehler && (
                <div role="alert" className="rounded border-l-4 border-red-500 bg-red-50 p-3 text-sm text-red-900">{fehler}</div>
              )}
              <div className="flex gap-3">
                <button type="button" className="btn-outline flex-1" disabled={busy} onClick={() => antworten(false)}>Ablehnen</button>
                <button type="button" className="btn-primary flex-1" disabled={busy} onClick={() => antworten(true)}>Zulassen</button>
              </div>
              <p className="text-xs text-ink/60">Du kannst den Zugriff jederzeit in den Einstellungen unter „KI-Assistenten“ widerrufen.</p>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
