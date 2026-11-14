import { useEffect, useState } from 'react';
import { IconX } from './Icons.jsx';

// „Neue Version verfügbar“ — Pflicht für jede installierbare App der vrwb-Familie (Hub: design/vorlagen/app-shell.md §4).
// Eine installierte App bleibt tagelang offen und liefe nach einem Release mit altem Code weiter. Jeder Build nennt sein
// Skript `assets/index-<hash>.js`; Tab vergleicht das laufende mit dem in der frisch geladenen index.html (beim Start, wenn
// die App wieder nach vorn kommt, und alle 15 Minuten). Es lädt nie von selbst neu — ein halb ausgefülltes Fenster bleibt.
// Der Service Worker cacht nichts (public/sw.js), deshalb genügt ein normales Neuladen.

const ALLE_MINUTEN = 15;
const SKRIPT = /\/assets\/index-[\w-]+\.js/;

export function laufendesSkript(doc = document) {
  return [...doc.querySelectorAll('script[src]')].map((s) => s.getAttribute('src').match(SKRIPT)?.[0]).find(Boolean) || '';
}

export async function ausgeliefertesSkript() {
  try {
    const res = await fetch('/', { cache: 'no-store', credentials: 'same-origin' });
    if (!res.ok) return '';
    return (await res.text()).match(SKRIPT)?.[0] || '';
  } catch {
    return ''; // offline oder mitten im Release: später wieder fragen
  }
}

export default function NeueVersion() {
  const [neu, setNeu] = useState('');
  const [spaeter, setSpaeter] = useState('');

  useEffect(() => {
    const laeuft = laufendesSkript();
    if (!laeuft) return undefined; // Entwicklungsserver hat kein gebautes Skript
    let aktiv = true;
    const schauen = async () => {
      if (document.visibilityState === 'hidden') return;
      const da = await ausgeliefertesSkript();
      if (aktiv && da && da !== laeuft) setNeu(da);
    };
    const timer = setInterval(schauen, ALLE_MINUTEN * 60_000);
    document.addEventListener('visibilitychange', schauen);
    window.addEventListener('focus', schauen);
    schauen();
    return () => {
      aktiv = false;
      clearInterval(timer);
      document.removeEventListener('visibilitychange', schauen);
      window.removeEventListener('focus', schauen);
    };
  }, []);

  if (!neu || neu === spaeter) return null;
  return (
    <div
      role="status"
      className="fixed left-1/2 z-40 flex max-w-[calc(100vw-2rem)] -translate-x-1/2 items-center gap-3 rounded-2xl border border-ink/10 bg-paper py-2 pl-4 pr-2 shadow-lg
                 bottom-[calc(env(safe-area-inset-bottom)+5rem)] lg:bottom-6 motion-safe:animate-[neue-version_.25s_ease-out]"
    >
      <span className="whitespace-nowrap text-sm font-bold">Neue Version verfügbar</span>
      <button type="button" className="btn-primary btn-sm" onClick={() => window.location.reload()}>
        Neu laden
      </button>
      <button type="button" className="btn-icon-ghost" title="Später" aria-label="Später" onClick={() => setSpaeter(neu)}>
        <IconX />
      </button>
    </div>
  );
}
