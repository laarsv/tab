// Bausteine für die Seiten im Recap-Stil (siehe DESIGN.md §6): weiße Fläche, Zeilen statt
// Karten — Icon im Kreis, Titel, Zustandszeile, Beträge rechts, Icon-Knöpfe als Aktionen.

// Seitenkopf: Titel 34/900 (accent = gedämpfter Zusatz wie das Jahr), eine leise Zeile
// darunter, rechts die Werkzeuge (Icon-Knöpfe / die eine Hauptaktion).
export function PageHeader({ title, accent, sub, children }) {
  return (
    <div className="flex items-start justify-between gap-3">
      <div className="min-w-0">
        <h1 className="page-title">
          {title}
          {accent !== undefined && accent !== null && <span className="text-ink/45"> {accent}</span>}
        </h1>
        {sub && <p className="text-sm text-ink/60 mt-1.5">{sub}</p>}
      </div>
      {children && <div className="flex items-center gap-1 shrink-0 -mt-0.5">{children}</div>}
    </div>
  );
}

// Abschnittskopf: Eyebrow in Royal + Zahl in Mono, rechts frei belegbar.
export function SectionHead({ label, count, children, className = '' }) {
  return (
    <div className={`flex items-center gap-2.5 mt-8 mb-1 ${className}`}>
      <span className="eyebrow">{label}</span>
      {count !== undefined && count !== null && (
        <span className="font-mono text-xs font-bold text-ink/60 tabular-nums">{count}</span>
      )}
      {children && <div className="ml-auto flex items-center gap-1">{children}</div>}
    </div>
  );
}

// kind: 'file' (Royal-Tint) | 'in' (Einnahme, Royal) | 'out' (Ausgabe, Ink-Tint) | 'neg' (überfällig)
const KREIS = {
  file: 'bg-royal/[0.08] text-royal',
  in: 'bg-royal/[0.08] text-royal',
  out: 'bg-ink/[0.06] text-ink/80',
  neg: 'bg-red-700/10 text-red-700',
};

// Eine Zeile. title/sub dürfen JSX sein; amount rechts (Royal bei Einnahme); actions =
// Icon-Knöpfe — am Handy rutschen sie unter den Text, damit die Touch-Ziele 44 px behalten.
export function Row({ kind = 'file', icon: Icon, title, sub, amount, amountIn = false, actions, onTitleClick, titleHint }) {
  const titel = onTitleClick ? (
    <button type="button" onClick={onTitleClick} title={titleHint} className="block max-w-full text-left">
      <span className="block truncate font-bold text-[15px] leading-snug hover:text-royal">{title}</span>
    </button>
  ) : (
    <span className="block truncate font-bold text-[15px] leading-snug">{title}</span>
  );
  return (
    <div className="flex flex-wrap sm:flex-nowrap items-center gap-x-3.5 gap-y-0.5 py-2.5 border-b border-ink/[0.08]">
      <span className={`h-10 w-10 shrink-0 rounded-full inline-flex items-center justify-center ${KREIS[kind]}`}>
        {Icon && <Icon className="h-[18px] w-[18px]" />}
      </span>
      <div className="min-w-0 flex-1">
        {titel}
        {sub && <div className="flex items-center flex-wrap gap-x-1.5 text-[13px] text-ink/60 leading-snug">{sub}</div>}
      </div>
      {amount && (
        <div
          className={`shrink-0 text-right font-black tabular-nums tracking-tight text-base ${amountIn ? 'text-royal' : ''}`}
        >
          {amount}
        </div>
      )}
      {actions && (
        <div className="flex items-center justify-end gap-0.5 w-full sm:w-auto shrink-0 text-ink/60">{actions}</div>
      )}
    </div>
  );
}

// Leerer Zustand: nennt die nächste Aktion, kein Kasten.
export function Leer({ children }) {
  return <p className="py-8 text-center text-sm text-ink/60">{children}</p>;
}
