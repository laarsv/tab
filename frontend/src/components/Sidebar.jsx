import { useEffect, useRef, useState } from 'react';
import { Link, NavLink, useNavigate } from 'react-router-dom';
import Dropdown from './Dropdown.jsx';
import Wordmark from './Wordmark.jsx';
import {
  IconArrowRight,
  IconBriefcase,
  IconChecklist,
  IconChevronDown,
  IconDownload,
  IconInfo,
  IconList,
  IconLogOut,
  IconMail,
  IconPlus,
  IconReceipt,
  IconSparkles,
  IconTrendDown,
  IconUpload,
} from './Icons.jsx';

// Royal-Seitenleiste (Recap-Stil). Desktop: fest links; mobil: dieselbe Leiste als Schublade.
// Farben nur Weiß mit Alpha auf Royal (Text mindestens 78 %).

const NAV = [
  { to: '/buchungen', label: 'Buchungen', icon: IconList },
  { to: '/rechnungen', label: 'Rechnungen', icon: IconReceipt },
  { to: '/check', label: 'Jahres-Check', icon: IconChecklist, badge: 'check' },
  { to: '/afa', label: 'Abschreibungen', icon: IconTrendDown },
];

const WEITERE = [
  { to: '/export', label: 'Export', icon: IconDownload },
  { to: '/gewerbe', label: 'Gewerbe', icon: IconBriefcase },
  { to: '/einrichtung', label: 'Einrichtung & Hilfe', icon: IconInfo },
];

export function initialen(user) {
  const name = (user?.name || user?.email || '?').trim();
  const parts = name.split(/[\s.@_-]+/).filter(Boolean);
  const chars = parts.length >= 2 ? parts[0][0] + parts[1][0] : name.slice(0, 2);
  return chars.toUpperCase();
}

function NavItem({ item, badge, onNavigate }) {
  const Icon = item.icon;
  return (
    <NavLink
      to={item.to}
      onClick={onNavigate}
      className={({ isActive }) =>
        `flex h-11 lg:h-[38px] items-center gap-2.5 rounded-[10px] px-3 text-[15px] text-paper outline-none
         focus-visible:ring-2 focus-visible:ring-paper/70
         ${isActive ? 'bg-paper/[0.18] font-bold' : 'hover:bg-paper/10'}`
      }
    >
      <Icon className="h-[19px] w-[19px] shrink-0" />
      <span className="truncate">{item.label}</span>
      {badge > 0 && (
        <span className="ml-auto inline-flex h-5 min-w-[20px] items-center justify-center rounded-full bg-paper px-1.5 text-xs font-bold tabular-nums text-royal">
          {badge}
        </span>
      )}
    </NavLink>
  );
}

function ProfilZeile({ user, jahr, jahrVorlaeufig, onMail, onNews, onLogout, onNavigate }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    function onDoc(e) {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    }
    function onKey(e) {
      if (e.key === 'Escape') setOpen(false);
    }
    document.addEventListener('mousedown', onDoc);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDoc);
      document.removeEventListener('keydown', onKey);
    };
  }, []);

  function run(fn) {
    setOpen(false);
    onNavigate?.();
    fn();
  }

  const eintrag =
    'flex w-full items-center gap-2.5 px-4 py-2.5 lg:py-2 text-left text-sm font-medium text-ink hover:bg-royal/10';

  return (
    <div className="relative mt-2" ref={ref}>
      {open && (
        <div
          role="menu"
          className="absolute bottom-full left-0 right-0 z-50 mb-2 rounded-xl border border-ink/10 bg-paper py-1 text-ink shadow-lg"
        >
          <div className="border-b border-ink/10 px-4 py-2">
            <div className="truncate text-sm font-bold">{user?.name || 'Angemeldet'}</div>
            <div className="truncate text-xs text-ink/60">{user?.email}</div>
          </div>
          <button role="menuitem" className={eintrag} onClick={() => run(onMail)}>
            <IconMail className="h-[18px] w-[18px] text-ink/60" /> E-Mail-Versand
          </button>
          <button role="menuitem" className={eintrag} onClick={() => run(onNews)}>
            <IconSparkles className="h-[18px] w-[18px] text-ink/60" /> Neuigkeiten
          </button>
          <button role="menuitem" className={`${eintrag} border-t border-ink/10`} onClick={() => run(onLogout)}>
            <IconLogOut className="h-[18px] w-[18px] text-ink/60" /> Abmelden
          </button>
        </div>
      )}
      <button
        type="button"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label="Profil-Menü"
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center gap-2.5 rounded-xl px-2 py-1.5 text-left outline-none hover:bg-paper/10 focus-visible:ring-2 focus-visible:ring-paper/70"
      >
        <span className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-paper/[0.18] text-[13px] font-black">
          {initialen(user)}
        </span>
        <span className="min-w-0 flex-1">
          <span className="block truncate text-sm font-bold leading-tight">{user?.name || user?.email}</span>
          <span className="block truncate text-xs leading-snug text-paper/80">
            EÜR {jahr}
            {jahrVorlaeufig ? ' (vorläufig)' : ''}
          </span>
        </span>
        <IconChevronDown className="h-4 w-4 shrink-0 rotate-180 text-paper/80" />
      </button>
    </div>
  );
}

export default function Sidebar({
  user,
  gewerbeOptions,
  gewerbeId,
  onGewerbe,
  jahrOptions,
  jahr,
  onJahr,
  jahrVorlaeufig,
  eingang,
  checkOffen,
  onNavigate,
  onNeueBuchung,
  onUpload,
  onAbarbeiten,
  onMail,
  onNews,
  onLogout,
}) {
  const navigate = useNavigate();

  return (
    <nav aria-label="Seitenleiste, Navigation" className="flex h-full w-full flex-col overflow-y-auto bg-royal px-3.5 pb-3.5 pt-5 text-paper">
      <Link
        to="/buchungen"
        onClick={onNavigate}
        title="Zu den Buchungen"
        className="self-start rounded-md px-2 outline-none focus-visible:ring-2 focus-visible:ring-paper/70"
      >
        <Wordmark onRoyal className="text-[22px] leading-none" />
      </Link>

      <div className="mb-2.5 mt-4 flex gap-2">
        <button
          type="button"
          onClick={onNeueBuchung}
          className="inline-flex h-11 lg:h-10 flex-1 items-center justify-center gap-2 rounded-[10px] bg-paper text-[15px] font-bold text-royal outline-none hover:bg-paper/90 focus-visible:ring-2 focus-visible:ring-paper/70"
        >
          <IconPlus className="h-[18px] w-[18px]" /> Neue Buchung
        </button>
        <button
          type="button"
          onClick={onUpload}
          title="Belege hochladen"
          aria-label="Belege hochladen"
          className="inline-flex h-11 w-11 lg:h-10 lg:w-10 items-center justify-center rounded-[10px] bg-paper/[0.18] outline-none hover:bg-paper/25 focus-visible:ring-2 focus-visible:ring-paper/70"
        >
          <IconUpload className="h-[18px] w-[18px]" />
        </button>
      </div>

      <div className="flex gap-2">
        <div className="min-w-0 flex-1">
          <Dropdown
            variant="onRoyal"
            value={gewerbeId}
            onChange={(v) => onGewerbe(String(v))}
            options={gewerbeOptions}
            placeholder="Kein Gewerbe"
          />
        </div>
        <div className="w-[84px] shrink-0">
          <Dropdown variant="onRoyal" alignRight value={jahr} onChange={(v) => onJahr(String(v))} options={jahrOptions} />
        </div>
      </div>

      {/* „Jetzt“-Zeile von recap: der Beleg-Eingang — nur, wenn etwas wartet */}
      {eingang.offen > 0 && (
        <div className="mb-1 mt-2.5 flex items-center gap-2.5 rounded-xl bg-paper/10 py-2.5 pl-3 pr-2.5">
          <button
            type="button"
            onClick={() => {
              onNavigate?.();
              navigate('/buchungen');
            }}
            className="flex min-w-0 flex-1 items-center gap-2.5 rounded-md text-left outline-none focus-visible:ring-2 focus-visible:ring-paper/70"
          >
            <span
              className={`h-2.5 w-2.5 shrink-0 rounded-full ${eingang.ueberfaellig > 0 ? 'bg-paper' : 'border-2 border-paper'}`}
              aria-hidden="true"
            />
            <span className="min-w-0">
              <span className="block text-sm font-bold leading-tight">Beleg-Eingang</span>
              <span className="block text-xs leading-snug text-paper/90">
                {eingang.offen} offen
                {eingang.ueberfaellig > 0 ? ` · ${eingang.ueberfaellig} überfällig` : ''}
              </span>
            </span>
          </button>
          <button
            type="button"
            onClick={onAbarbeiten}
            title="Jetzt abarbeiten"
            aria-label="Beleg-Eingang jetzt abarbeiten"
            className="inline-flex h-10 w-10 lg:h-9 lg:w-9 shrink-0 items-center justify-center rounded-full bg-paper text-royal outline-none hover:bg-paper/90 focus-visible:ring-2 focus-visible:ring-paper/70"
          >
            <IconArrowRight className="h-[18px] w-[18px]" />
          </button>
        </div>
      )}

      <div className="mt-2 space-y-0.5">
        {NAV.map((n) => (
          <NavItem key={n.to} item={n} badge={n.badge === 'check' ? checkOffen : 0} onNavigate={onNavigate} />
        ))}
      </div>

      <div className="mb-1 mt-4 px-3 text-xs font-bold uppercase tracking-[0.1em] text-paper/80">Weitere</div>
      <div className="space-y-0.5">
        {WEITERE.map((n) => (
          <NavItem key={n.to} item={n} onNavigate={onNavigate} />
        ))}
      </div>

      <div className="min-h-4 flex-1" />

      <ProfilZeile
        user={user}
        jahr={jahr}
        jahrVorlaeufig={jahrVorlaeufig}
        onMail={onMail}
        onNews={onNews}
        onLogout={onLogout}
        onNavigate={onNavigate}
      />
    </nav>
  );
}
