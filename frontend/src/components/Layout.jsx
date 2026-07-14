import { useEffect, useMemo, useRef, useState, useCallback } from 'react';
import { Link, NavLink, Outlet } from 'react-router-dom';
import toast from 'react-hot-toast';
import { api, apiError } from '../api/client.js';
import { useAuth } from '../auth/AuthContext.jsx';
import { PageSpinner } from './Spinner.jsx';
import Dropdown from './Dropdown.jsx';
import MailSetupModal from './MailSetupModal.jsx';
import Wordmark from './Wordmark.jsx';
import { countOffeneTopics, loadCheckState } from '../lib/jahresCheck.js';

function NavBadge({ n }) {
  return (
    <span className="ml-2 inline-flex items-center justify-center min-w-[20px] h-5 px-1.5 rounded-full bg-royal text-paper text-[11px] font-black tabular-nums">
      {n}
    </span>
  );
}

const NAV = [
  { to: '/buchungen', label: 'Buchungen' },
  { to: '/rechnungen', label: 'Rechnungen' },
  { to: '/check', label: 'Jahres-Check' },
  { to: '/afa', label: 'Abschreibungen' },
];

// Einträge hinter der Profil-Bubble (Desktop) bzw. unten im Drawer (mobil).
const PROFIL_NAV = [
  { to: '/export', label: 'Export' },
  { to: '/gewerbe', label: 'Gewerbe' },
];

function initialen(user) {
  const name = (user?.name || user?.email || '?').trim();
  const parts = name.split(/[\s.@_-]+/).filter(Boolean);
  const chars = parts.length >= 2 ? parts[0][0] + parts[1][0] : name.slice(0, 2);
  return chars.toUpperCase();
}

function ProfilBubble({ user, onLogout, onMail }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    function onDoc(e) {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    }
    document.addEventListener('mousedown', onDoc);
    return () => document.removeEventListener('mousedown', onDoc);
  }, []);

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen((o) => !o)}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label="Profil-Menü"
        className="h-9 w-9 rounded-full bg-royal text-paper font-black text-sm inline-flex items-center justify-center hover:opacity-90 focus:ring-2 focus:ring-royal/40 outline-none"
        title={user?.name || user?.email}
      >
        {initialen(user)}
      </button>
      {open && (
        <div
          role="menu"
          className="absolute right-0 mt-2 w-56 rounded-lg border border-ink/10 bg-paper shadow-lg py-1 z-50"
        >
          <div className="px-4 py-2 border-b border-ink/10">
            <div className="text-sm font-bold truncate">{user?.name || 'Angemeldet'}</div>
            <div className="text-xs text-ink/50 truncate">{user?.email}</div>
          </div>
          {PROFIL_NAV.map((n) => (
            <Link
              key={n.to}
              to={n.to}
              onClick={() => setOpen(false)}
              className="block px-4 py-2 text-sm font-medium text-ink hover:bg-royal/10"
            >
              {n.label}
            </Link>
          ))}
          <button
            onClick={() => {
              setOpen(false);
              onMail();
            }}
            className="w-full text-left px-4 py-2 text-sm font-medium text-ink hover:bg-royal/10"
          >
            E-Mail-Versand
          </button>
          <button
            onClick={onLogout}
            className="w-full text-left px-4 py-2 text-sm font-medium text-ink hover:bg-royal/10 border-t border-ink/10"
          >
            Abmelden
          </button>
        </div>
      )}
    </div>
  );
}

export default function Layout() {
  const { user, logout } = useAuth();
  const [drawer, setDrawer] = useState(false);
  const [mailModal, setMailModal] = useState(false);

  const [gewerbe, setGewerbe] = useState([]);
  const [jahre, setJahre] = useState([]);
  const [loading, setLoading] = useState(true);
  const [checkOffen, setCheckOffen] = useState(0);

  const [gewerbeId, setGewerbeId] = useState(
    () => localStorage.getItem('tab_gewerbe') || '',
  );
  const [jahr, setJahr] = useState(
    () => localStorage.getItem('tab_jahr') || String(new Date().getFullYear()),
  );

  const loadGewerbe = useCallback(async () => {
    const res = await api.get('/api/gewerbe');
    setGewerbe(res.data);
    return res.data;
  }, []);

  useEffect(() => {
    Promise.all([loadGewerbe(), api.get('/api/meta/jahre')])
      .then(([g, jahreRes]) => {
        setJahre(jahreRes.data);
        if ((!gewerbeId || !g.find((x) => String(x.id) === String(gewerbeId))) && g[0]) {
          setGewerbeId(String(g[0].id));
        }
      })
      .catch((e) => toast.error(apiError(e, 'Laden fehlgeschlagen.')))
      .finally(() => setLoading(false));
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Nav-Badge: offene Jahres-Check-Themen für Gewerbe + Jahr.
  const loadBadges = useCallback(async (gid, j) => {
    if (!gid) {
      setCheckOffen(0);
      return;
    }
    try {
      const [kat, buch] = await Promise.all([
        api.get('/api/kategorien', { params: { jahr: j } }),
        api.get('/api/buchungen', { params: { gewerbe_id: gid, jahr: j } }),
      ]);
      setCheckOffen(countOffeneTopics(kat.data, buch.data, loadCheckState(gid, j)));
    } catch {
      setCheckOffen(0);
    }
  }, []);

  useEffect(() => {
    loadBadges(gewerbeId, jahr);
  }, [gewerbeId, jahr, loadBadges]);

  useEffect(() => {
    if (gewerbeId) localStorage.setItem('tab_gewerbe', gewerbeId);
  }, [gewerbeId]);
  useEffect(() => {
    if (jahr) localStorage.setItem('tab_jahr', jahr);
  }, [jahr]);

  const gewerbeOptions = useMemo(
    () => gewerbe.map((g) => ({ value: String(g.id), label: g.name })),
    [gewerbe],
  );
  const jahrOptions = useMemo(
    () =>
      jahre.map((j) => ({
        value: String(j.jahr),
        label: j.vorlaeufig ? `${j.jahr} (vorläufig)` : String(j.jahr),
      })),
    [jahre],
  );

  const ctx = {
    gewerbeId,
    jahr: Number(jahr),
    gewerbe,
    jahre,
    reloadGewerbe: loadGewerbe,
    reloadBadges: () => loadBadges(gewerbeId, jahr),
    setGewerbeId,
  };

  function doLogout() {
    logout(); // POST /logout + Redirect nach /login übernimmt der AuthContext
  }

  const linkBase = 'px-3 py-1.5 rounded-md text-sm font-bold transition';

  return (
    <div className="min-h-full flex flex-col">
      <header className="bg-paper border-b border-royal-soft/30 sticky top-0 z-30">
        <div className="mx-auto max-w-6xl px-4 sm:px-6 h-16 flex items-center justify-between gap-3">
          <div className="flex items-center min-w-0">
            <Wordmark className="text-2xl" />
            <span className="ml-2 sm:ml-3 text-sm sm:text-base font-light text-ink/60 truncate hidden sm:inline">
              EÜR-Buchhaltung
            </span>
          </div>

          <div className="flex items-center gap-2">
            <nav className="hidden md:flex items-center gap-2">
              {NAV.map((n) => (
                <NavLink
                  key={n.to}
                  to={n.to}
                  className={({ isActive }) =>
                    `${linkBase} inline-flex items-center ${isActive ? 'text-royal' : 'text-ink/70 hover:text-ink'}`
                  }
                >
                  {n.label}
                  {n.to === '/check' && checkOffen > 0 && <NavBadge n={checkOffen} />}
                </NavLink>
              ))}
            </nav>

            <div className="hidden md:block">
              <ProfilBubble user={user} onLogout={doLogout} onMail={() => setMailModal(true)} />
            </div>

            <button
              className="md:hidden p-2 -mr-2 rounded-md hover:bg-royal/10 text-ink/80"
              onClick={() => setDrawer(true)}
              aria-label="Menü öffnen"
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-6 w-6">
                <path d="M4 6h16M4 12h16M4 18h16" />
              </svg>
            </button>
          </div>
        </div>

        {/* Globale Filter: Gewerbe + Jahr — Ghost-Inline-Werte (DESIGN.shared.md §5.8) */}
        <div className="mx-auto max-w-6xl px-4 sm:px-6 pb-3 flex flex-wrap items-center gap-2">
          <Dropdown
            value={gewerbeId}
            onChange={(v) => setGewerbeId(String(v))}
            options={gewerbeOptions}
            placeholder="Kein Gewerbe — zuerst anlegen"
            variant="ghost"
          />
          <Dropdown
            value={jahr}
            onChange={(v) => setJahr(String(v))}
            options={jahrOptions}
            variant="ghost"
          />
        </div>
      </header>

      {drawer && (
        <div role="dialog" aria-modal="true" className="fixed inset-0 z-50 md:hidden">
          <button
            className="absolute inset-0 bg-ink/60 backdrop-blur-sm"
            onClick={() => setDrawer(false)}
            aria-label="Menü schließen"
          />
          <aside className="absolute top-0 right-0 h-full w-[85%] max-w-xs bg-paper shadow-xl flex flex-col">
            <div className="flex items-center justify-between px-4 py-3 border-b border-ink/10">
              <span className="font-black">Menü</span>
              <button onClick={() => setDrawer(false)} className="p-2 rounded-md hover:bg-royal/10" aria-label="Schließen">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-5 w-5">
                  <path d="M6 6l12 12M18 6L6 18" />
                </svg>
              </button>
            </div>
            <nav className="flex-1 overflow-y-auto py-2">
              {NAV.map((n) => (
                <NavLink
                  key={n.to}
                  to={n.to}
                  onClick={() => setDrawer(false)}
                  className={({ isActive }) =>
                    `flex items-center justify-between px-4 py-3 text-sm font-bold transition ${
                      isActive ? 'text-royal bg-royal-soft/10' : 'text-ink hover:bg-royal/10'
                    }`
                  }
                >
                  <span>{n.label}</span>
                  {n.to === '/check' && checkOffen > 0 && <NavBadge n={checkOffen} />}
                </NavLink>
              ))}
              <div className="my-2 border-t border-ink/10" />
              {PROFIL_NAV.map((n) => (
                <NavLink
                  key={n.to}
                  to={n.to}
                  onClick={() => setDrawer(false)}
                  className={({ isActive }) =>
                    `flex items-center px-4 py-3 text-sm font-bold transition ${
                      isActive ? 'text-royal bg-royal-soft/10' : 'text-ink hover:bg-royal/10'
                    }`
                  }
                >
                  {n.label}
                </NavLink>
              ))}
              <button
                onClick={() => {
                  setDrawer(false);
                  setMailModal(true);
                }}
                className="w-full text-left px-4 py-3 text-sm font-bold text-ink hover:bg-royal/10"
              >
                E-Mail-Versand
              </button>
            </nav>
            <div className="border-t border-ink/10 p-2">
              <div className="px-4 py-2 text-xs text-ink/50 truncate">{user?.email}</div>
              <button
                onClick={doLogout}
                className="w-full text-left px-4 py-3 text-sm font-bold rounded-md text-ink hover:bg-royal/10"
              >
                Abmelden
              </button>
            </div>
          </aside>
        </div>
      )}

      {mailModal && <MailSetupModal onClose={() => setMailModal(false)} />}

      <main className="flex-1">
        <div className="mx-auto max-w-6xl px-4 sm:px-6 py-6 sm:py-8">
          {loading ? <PageSpinner /> : <Outlet context={ctx} />}
        </div>
      </main>

      <footer className="border-t border-ink/10">
        <div className="mx-auto max-w-6xl px-4 sm:px-6 py-4 text-xs text-ink/50 flex flex-wrap items-center gap-x-1.5">
          <a href="https://vrwb.de" target="_blank" rel="noreferrer" className="hover:opacity-80">
            <Wordmark className="text-base" />
          </a>
          <span>
            · EÜR für Kleinunternehmer (§19 UStG) · keine Steuerberatung · angemeldet als{' '}
            {user?.name || user?.email}
          </span>
        </div>
      </footer>
    </div>
  );
}
