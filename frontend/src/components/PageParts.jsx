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

// kind: 'file' (Royal-Tint) | 'in' (Einnahme, Royal) | 'out' (Ausgabe, Ink-Tint) |
//       'warn' (offen/wartet) | 'pos' (bezahlt/erledigt) | 'neg' (überfällig/storniert)
export const KREIS = {
  file: 'bg-royal/[0.08] text-royal',
  in: 'bg-royal/[0.08] text-royal',
  out: 'bg-ink/[0.06] text-ink/80',
  warn: 'bg-[#b26a00]/[0.12] text-[#9a5900]',
  pos: 'bg-[#177245]/10 text-[#177245]',
  neg: 'bg-red-700/10 text-red-700',
};

// Eine Zeile. title/sub dürfen JSX sein; amount rechts (Royal bei Einnahme); actions =
// Icon-Knöpfe — am Handy rutschen sie unter den Text, damit die Touch-Ziele 44 px behalten.
// leading: statt Icon beliebiger Inhalt im Kreis (z. B. eine Zeilennummer); children: Inhalt
// unter der Zustandszeile (Erklärtext, Auswahl-Knöpfe); wrapTitle: Titel darf umbrechen;
// muted: zurückgenommene Zeile; actionsClass: z. B. feste Breite, damit Beträge bündig bleiben.
export function Row({
  kind = 'file',
  icon: Icon,
  leading,
  title,
  sub,
  amount,
  amountIn = false,
  actions,
  actionsClass = '',
  onTitleClick,
  titleHint,
  wrapTitle = false,
  muted = false,
  children,
}) {
  const titelKlasse = `block ${wrapTitle ? '' : 'truncate'} font-bold text-[15px] leading-snug`;
  const titel = onTitleClick ? (
    <button type="button" onClick={onTitleClick} title={titleHint} className="block max-w-full text-left">
      <span className={`${titelKlasse} hover:text-royal`}>{title}</span>
    </button>
  ) : (
    <span className={titelKlasse}>{title}</span>
  );
  return (
    <div
      className={`flex flex-wrap sm:flex-nowrap ${children ? 'items-start' : 'items-center'} gap-x-3.5 gap-y-0.5 py-2.5 border-b border-ink/[0.08] ${muted ? 'opacity-60' : ''}`}
    >
      <span
        className={`h-10 w-10 shrink-0 rounded-full inline-flex items-center justify-center ${children ? '' : 'self-start sm:self-center'} ${KREIS[kind]}`}
      >
        {leading ?? (Icon && <Icon className="h-[18px] w-[18px]" />)}
      </span>
      <div className="min-w-0 flex-1">
        {titel}
        {sub && <div className="flex items-center flex-wrap gap-x-1.5 text-[13px] text-ink/60 leading-snug">{sub}</div>}
        {children}
      </div>
      {amount && (
        <div
          className={`shrink-0 text-right font-black tabular-nums tracking-tight text-base ${amountIn ? 'text-royal' : ''}`}
        >
          {amount}
        </div>
      )}
      {actions && (
        <div className={`flex items-center justify-end gap-0.5 w-full sm:w-auto shrink-0 text-ink/60 ${actionsClass}`}>
          {actions}
        </div>
      )}
    </div>
  );
}

// Trenner „·" in Zustandszeilen.
export const PUNKT = (
  <span aria-hidden="true" className="text-ink/45">
    ·
  </span>
);

const ZUSTAND = {
  leise: '',
  royal: 'font-bold text-royal',
  warn: 'font-bold text-[#9a5900]',
  neg: 'font-bold text-[#c0392b]',
  pos: 'font-bold text-[#177245]',
};

// Zustand in der Zustandszeile einer Zeile: Wort (+ Icon) in Zustandsfarbe, kein Chip.
export function Zustand({ ton = 'leise', icon: Icon, children, className = '' }) {
  return (
    <span className={`inline-flex items-center gap-1 ${ZUSTAND[ton]} ${className}`}>
      {Icon && <Icon className="h-3.5 w-3.5" />}
      {children}
    </span>
  );
}

// Hinweis-Band (Recap: Banner): Fehler rot getönt, Warnung gelb, Info/Erfolg Royal-Tint.
const HINWEIS = {
  info: 'bg-royal/[0.08]',
  warn: 'bg-[#b26a00]/[0.12]',
  neg: 'bg-[#c0392b]/10',
};
const HINWEIS_TITEL = { info: 'text-ink', warn: 'text-[#9a5900]', neg: 'text-[#c0392b]' };

export function Hinweis({ ton = 'info', titel, children, className = '' }) {
  return (
    <div
      role={ton === 'neg' ? 'alert' : undefined}
      className={`rounded-xl px-4 py-3 text-sm leading-snug text-ink/80 ${HINWEIS[ton]} ${className}`}
    >
      {titel && <div className={`mb-0.5 font-bold ${HINWEIS_TITEL[ton]}`}>{titel}</div>}
      {children}
    </div>
  );
}

// Kennzahlen: flache Reihe mit Haarlinien statt Kacheln.
const SPALTEN = { 1: 'grid-cols-1', 2: 'grid-cols-2', 3: 'grid-cols-3' };

export function Kennzahlen({ cols = 3, children, className = '' }) {
  return <div className={`grid ${SPALTEN[cols]} border-y border-ink/[0.08] ${className}`}>{children}</div>;
}

export function Kennzahl({ label, value, hint, royal = false }) {
  return (
    <div className="border-l border-ink/[0.08] py-3 pl-3 first:border-l-0 first:pl-0 sm:pl-6 sm:first:pl-0">
      <div className="text-[11px] font-bold uppercase tracking-[0.1em] text-ink/60 sm:text-xs">{label}</div>
      <div
        className={`text-lg font-black leading-tight tabular-nums tracking-tight sm:text-[26px] ${royal ? 'text-royal' : ''}`}
      >
        {value}
      </div>
      {hint && <div className="mt-0.5 hidden text-[11px] leading-snug text-ink/60 sm:block">{hint}</div>}
    </div>
  );
}

// Fortschritt: Eyebrow, Zählung, dünner Balken — ohne Kasten.
export function Fortschritt({ label = 'Fortschritt', text, value, max, children }) {
  return (
    <div className="mt-6">
      <div className="flex items-baseline justify-between gap-3">
        <span className="eyebrow">{label}</span>
        <span className="text-sm tabular-nums text-ink/60">{text}</span>
      </div>
      <div className="mt-2 h-1.5 rounded-full bg-ink/[0.06]">
        <div
          className="h-1.5 rounded-full bg-royal transition-all"
          style={{ width: `${max ? Math.min(100, (value / max) * 100) : 0}%` }}
        />
      </div>
      {children}
    </div>
  );
}

// Leerer Zustand: nennt die nächste Aktion, kein Kasten.
export function Leer({ children }) {
  return <p className="py-8 text-center text-sm text-ink/60">{children}</p>;
}

export function KeinGewerbe() {
  return <Leer>Kein Gewerbe gewählt. Lege unter „Gewerbe" zuerst ein Gewerbe an.</Leer>;
}
