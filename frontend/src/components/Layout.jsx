import { useEffect, useMemo, useRef, useState, useCallback } from 'react';
import { Link, NavLink, Outlet, useNavigate } from 'react-router-dom';
import toast from 'react-hot-toast';
import { api, apiError } from '../api/client.js';
import { useAuth } from '../auth/AuthContext.jsx';
import { PageSpinner } from './Spinner.jsx';
import MailSetupModal from './MailSetupModal.jsx';
import NeuigkeitenModal from './NeuigkeitenModal.jsx';
import Sidebar from './Sidebar.jsx';
import Wordmark from './Wordmark.jsx';
import { IconChecklist, IconInbox, IconList, IconMenu, IconReceipt, IconX } from './Icons.jsx';
import { countOffeneTopics, loadCheckState } from '../lib/jahresCheck.js';
import { syncGelesen, ungelesene } from '../lib/neuigkeiten.js';
import { ACCEPT } from '../lib/belege.js';
import { todayISO } from '../lib/format.js';

// Tab-Leiste am Handy (unter lg): die drei Hauptziele + „Mehr“ öffnet die Schublade.
const TABS = [
  { to: '/buchungen', label: 'Buchungen', icon: IconList },
  { to: '/rechnungen', label: 'Rechnungen', icon: IconReceipt },
  { to: '/check', label: 'Check', icon: IconChecklist, badge: 'check' },
];

export default function Layout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [drawer, setDrawer] = useState(false);
  const [eingang, setEingang] = useState({ offen: 0, ueberfaellig: 0 }); // Beleg-Eingang (Seitenleiste)
  const [eingangTick, setEingangTick] = useState(0); // zählt hoch, wenn der Eingang von außen wächst
  const [uploading, setUploading] = useState(false);
  const uploadRef = useRef(null);
  const [mailModal, setMailModal] = useState(false);
  const [newsModal, setNewsModal] = useState(false);

  // Neuigkeiten automatisch zeigen, wenn es für DIESEN Account Ungelesenes gibt
  // (Gelesen-Stand kommt vom Server, s. lib/neuigkeiten.js).
  useEffect(() => {
    if (!user?.email) return undefined;
    let aktiv = true;
    syncGelesen(user.email).then((gelesen) => {
      if (aktiv && ungelesene(gelesen) > 0) setNewsModal(true);
    });
    return () => {
      aktiv = false;
    };
  }, [user?.email]);

  function closeNews() {
    // Schließen markiert nichts als gelesen — Ungelesenes kommt beim nächsten
    // Login wieder, bis es im Fenster einzeln bestätigt wird.
    setNewsModal(false);
  }

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

  // Seitenleiste: offene Jahres-Check-Themen + Beleg-Eingang für Gewerbe + Jahr.
  const loadBadges = useCallback(async (gid, j) => {
    if (!gid) {
      setCheckOffen(0);
      setEingang({ offen: 0, ueberfaellig: 0 });
      return;
    }
    try {
      const [kat, buch, bel] = await Promise.all([
        api.get('/api/kategorien', { params: { jahr: j } }),
        api.get('/api/buchungen', { params: { gewerbe_id: gid, jahr: j } }),
        api.get('/api/belege', { params: { gewerbe_id: gid, status: 'offen' } }),
      ]);
      setCheckOffen(countOffeneTopics(kat.data, buch.data, loadCheckState(gid, j)));
      const heute = todayISO();
      setEingang({
        offen: bel.data.length,
        ueberfaellig: bel.data.filter((b) => b.faellig_am && b.faellig_am < heute).length,
      });
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
  // Belege in den Eingang hochladen (Seitenleiste und Buchungen-Seite teilen sich das).
  async function uploadBelege(files) {
    if (!files.length || !gewerbeId) return;
    setUploading(true);
    try {
      for (const file of files) {
        const form = new FormData();
        form.append('file', file);
        form.append('gewerbe_id', gewerbeId);
        await api.post('/api/belege', form);
      }
      toast.success(files.length > 1 ? `${files.length} Belege hochgeladen.` : 'Beleg hochgeladen.');
    } catch (err) {
      toast.error(apiError(err, 'Upload fehlgeschlagen.'));
    } finally {
      setUploading(false);
      setEingangTick((t) => t + 1);
      loadBadges(gewerbeId, jahr);
    }
  }

  const ctx = {
    gewerbeId,
    jahr: Number(jahr),
    gewerbe,
    jahre,
    reloadGewerbe: loadGewerbe,
    reloadBadges: () => loadBadges(gewerbeId, jahr),
    setGewerbeId,
    openMailSetup: () => setMailModal(true),
    uploadBelege,
    uploading,
    eingangTick,
  };

  function doLogout() {
    logout(); // POST /logout + Redirect nach /login übernimmt der AuthContext
  }

  // Schublade (mobil): ESC schließt, Seite scrollt nicht mit.
  useEffect(() => {
    if (!drawer) return undefined;
    function onKey(e) {
      if (e.key === 'Escape') setDrawer(false);
    }
    document.addEventListener('keydown', onKey);
    document.body.style.overflow = 'hidden';
    return () => {
      document.removeEventListener('keydown', onKey);
      document.body.style.overflow = '';
    };
  }, [drawer]);

  const jahrVorlaeufig = Boolean(jahre.find((j) => String(j.jahr) === String(jahr))?.vorlaeufig);

  const sidebarProps = {
    user,
    gewerbeOptions,
    gewerbeId,
    onGewerbe: setGewerbeId,
    // In der schmalen Seitenleiste nur die Zahl — „vorläufig" steht in der Profilzeile.
    jahrOptions: jahre.map((j) => ({ value: String(j.jahr), label: String(j.jahr) })),
    jahr,
    onJahr: setJahr,
    jahrVorlaeufig,
    eingang,
    checkOffen,
    onNeueBuchung: () => {
      setDrawer(false);
      navigate(`/buchungen?neu=${Date.now()}`);
    },
    onUpload: () => uploadRef.current?.click(),
    onAbarbeiten: () => {
      setDrawer(false);
      navigate(`/buchungen?abarbeiten=${Date.now()}`);
    },
    onMail: () => setMailModal(true),
    onNews: () => setNewsModal(true),
    onLogout: doLogout,
    onNavigate: () => setDrawer(false),
  };

  return (
    <div className="min-h-full lg:pl-[262px]">
      <input
        ref={uploadRef}
        type="file"
        accept={ACCEPT}
        multiple
        className="hidden"
        onChange={(e) => {
          uploadBelege(Array.from(e.target.files || []));
          e.target.value = '';
        }}
      />

      {/* Desktop: Royal-Seitenleiste fest links */}
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-[262px] lg:block">
        <Sidebar {...sidebarProps} />
      </aside>

      {/* Handy/Tablet: schmale Royal-Leiste oben */}
      <header className="sticky top-0 z-30 bg-royal pt-[env(safe-area-inset-top)] text-paper lg:hidden">
        <div className="flex h-14 items-center gap-2 px-4">
          <Link to="/buchungen" className="rounded-md outline-none focus-visible:ring-2 focus-visible:ring-paper/70">
            <Wordmark onRoyal className="text-xl leading-none" />
          </Link>
          <div className="flex-1" />
          {eingang.offen > 0 && (
            <button
              type="button"
              onClick={sidebarProps.onAbarbeiten}
              title="Beleg-Eingang abarbeiten"
              aria-label={`Beleg-Eingang abarbeiten, ${eingang.offen} offen`}
              className="relative inline-flex h-11 w-11 items-center justify-center rounded-xl bg-paper/[0.18] outline-none hover:bg-paper/25 focus-visible:ring-2 focus-visible:ring-paper/70"
            >
              <IconInbox className="h-[22px] w-[22px]" />
              <span className="absolute -right-0.5 -top-0.5 inline-flex h-5 min-w-[20px] items-center justify-center rounded-full bg-paper px-1.5 text-xs font-bold tabular-nums text-royal">
                {eingang.offen}
              </span>
            </button>
          )}
          <button
            type="button"
            onClick={() => setDrawer(true)}
            aria-label="Menü öffnen"
            className="inline-flex h-11 w-11 items-center justify-center rounded-xl outline-none hover:bg-paper/10 focus-visible:ring-2 focus-visible:ring-paper/70"
          >
            <IconMenu className="h-6 w-6" />
          </button>
        </div>
      </header>

      {/* Schublade: dieselbe Seitenleiste von links */}
      {drawer && (
        <div role="dialog" aria-modal="true" aria-label="Menü" className="fixed inset-0 z-50 lg:hidden">
          <button
            className="absolute inset-0 bg-ink/60 backdrop-blur-sm"
            onClick={() => setDrawer(false)}
            aria-label="Menü schließen"
          />
          <div className="absolute inset-y-0 left-0 w-[88%] max-w-[320px] shadow-xl">
            <Sidebar {...sidebarProps} />
            <button
              onClick={() => setDrawer(false)}
              aria-label="Schließen"
              className="absolute right-2 top-2 inline-flex h-11 w-11 items-center justify-center rounded-xl text-paper outline-none hover:bg-paper/10 focus-visible:ring-2 focus-visible:ring-paper/70"
            >
              <IconX className="h-5 w-5" />
            </button>
          </div>
        </div>
      )}

      {mailModal && <MailSetupModal onClose={() => setMailModal(false)} />}
      {newsModal && <NeuigkeitenModal onClose={closeNews} />}

      <main className="px-4 pb-28 pt-6 sm:px-6 sm:pt-8 lg:px-10 lg:pb-12 lg:pt-9">
        <div className="mx-auto max-w-5xl">
          {loading ? <PageSpinner /> : <Outlet context={ctx} />}
          <p className="mt-12 text-xs text-ink/60">
            Tab ist die bessere Excel-Liste für die EÜR (§19 UStG) und keine Steuerberatung — im Zweifel prüfen
            lassen.
          </p>
        </div>
      </main>

      {/* Handy/Tablet: Tab-Leiste unten, 64 px hoch (44-px-Ziele) */}
      <nav
        aria-label="Hauptnavigation"
        className="fixed inset-x-0 bottom-0 z-30 border-t border-ink/10 bg-paper pb-[env(safe-area-inset-bottom)] lg:hidden"
      >
        <div className="flex h-16">
          {TABS.map((t) => {
            const Icon = t.icon;
            return (
              <NavLink
                key={t.to}
                to={t.to}
                className={({ isActive }) =>
                  `relative flex flex-1 flex-col items-center justify-center gap-0.5 text-[11px] outline-none focus-visible:bg-royal/10
                   ${isActive ? 'font-bold text-royal' : 'font-medium text-ink/60'}`
                }
              >
                <Icon className="h-[22px] w-[22px]" />
                {t.label}
                {t.badge === 'check' && checkOffen > 0 && (
                  <span className="absolute left-1/2 top-1.5 ml-2 inline-flex h-4 min-w-[16px] items-center justify-center rounded-full bg-royal px-1 text-[10px] font-bold tabular-nums text-paper">
                    {checkOffen}
                  </span>
                )}
              </NavLink>
            );
          })}
          <button
            type="button"
            onClick={() => setDrawer(true)}
            className="flex flex-1 flex-col items-center justify-center gap-0.5 text-[11px] font-medium text-ink/60 outline-none focus-visible:bg-royal/10"
          >
            <IconMenu className="h-[22px] w-[22px]" />
            Mehr
          </button>
        </div>
      </nav>
    </div>
  );
}
