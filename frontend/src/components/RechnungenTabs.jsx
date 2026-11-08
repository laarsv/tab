import { NavLink } from 'react-router-dom';

// Reiter der Rechnungsseiten (Aufbau wie Haben: Kopf und Reiter bleiben, nur der Inhalt wechselt).
const TABS = [
  { to: '/rechnungen', label: 'Alle Rechnungen', end: true },
  { to: '/rechnungen/wiederkehrend', label: 'Wiederkehrend', end: false },
  { to: '/rechnungen/mahnwesen', label: 'Mahnwesen', end: false, badge: true },
];

export default function RechnungenTabs({ ueberfaellig = 0 }) {
  return (
    <nav aria-label="Bereiche der Rechnungen" className="mt-5 flex gap-1 overflow-x-auto border-b border-ink/[0.08]">
      {TABS.map((t) => (
        <NavLink
          key={t.to}
          to={t.to}
          end={t.end}
          className={({ isActive }) =>
            `-mb-px inline-flex h-11 shrink-0 items-center gap-1.5 border-b-2 px-3.5 text-[15px] outline-none
             focus-visible:bg-royal/10 sm:h-10
             ${isActive ? 'border-royal font-bold text-royal' : 'border-transparent font-medium text-ink/60 hover:text-ink'}`
          }
        >
          {t.label}
          {t.badge && ueberfaellig > 0 && (
            <span className="inline-flex h-5 min-w-[20px] items-center justify-center rounded-full bg-red-700/10 px-1.5 text-xs font-bold tabular-nums text-red-700">
              {ueberfaellig}
            </span>
          )}
        </NavLink>
      ))}
    </nav>
  );
}
