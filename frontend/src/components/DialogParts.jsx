import { IconButton, IconPlus, IconX } from './Icons.jsx';
import { formatEuro } from '../lib/format.js';

// Bausteine für Dialoge im Recap-Stil (DESIGN.md §6): Schalter statt Häkchen, Fußzeile mit
// Haarlinie, ruhige Gruppen, Positionen als getönte Flächen statt Rahmen.

// Schalter (Recap: Toggle) — Royal an, Ink-Tint aus, 44 × 26.
export function Schalter({ checked, onChange, disabled = false, label }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={`relative h-[26px] w-11 shrink-0 rounded-full outline-none transition-colors
        focus-visible:ring-2 focus-visible:ring-royal/40 disabled:cursor-not-allowed disabled:opacity-50
        ${checked ? 'bg-royal' : 'bg-ink/20'}`}
    >
      <span
        className={`absolute top-[3px] h-5 w-5 rounded-full bg-paper transition-all ${checked ? 'left-[21px]' : 'left-[3px]'}`}
      />
    </button>
  );
}

// Zeile mit Titel, Erklärsatz und Schalter rechts (die Einstellungs-Zeile von recap).
export function SchalterZeile({ titel, hinweis, checked, onChange, disabled }) {
  return (
    <div className="flex items-center gap-4 border-t border-ink/[0.08] py-3">
      <div className="min-w-0 flex-1">
        <div className="text-[15px] font-bold leading-snug">{titel}</div>
        {hinweis && <div className="text-[13px] leading-snug text-ink/60">{hinweis}</div>}
      </div>
      <Schalter checked={checked} onChange={onChange} disabled={disabled} label={titel} />
    </div>
  );
}

// Gruppe im Dialog: Eyebrow in Royal, darunter der Inhalt.
export function Gruppe({ titel, children, className = '' }) {
  return (
    <section className={`space-y-2 ${className}`}>
      {titel && <div className="eyebrow">{titel}</div>}
      {children}
    </section>
  );
}

// Fußzeile: Haarlinie, Aktionen rechts (am Handy gestapelt, Hauptaktion unten = zuletzt im Code).
// links: z. B. eine Nebenaktion („Vorschau"), steht links.
export function DialogFuss({ links, children }) {
  return (
    <div className="flex flex-col-reverse gap-2 border-t border-ink/[0.08] pt-4 sm:flex-row sm:items-center sm:justify-between">
      <div className="flex flex-col sm:flex-row">{links}</div>
      <div className="flex flex-col-reverse gap-2 sm:flex-row">{children}</div>
    </div>
  );
}

export function leerePosition() {
  return { beschreibung: '', menge: '1', preisInput: '' };
}

// Positionen einer Rechnung/eines Abos: je Position eine getönte Fläche (Beschreibung, Menge,
// Einzelpreis) + Summe. Gemeinsam für RechnungModal und AboModal.
export function PositionenEditor({ positionen, onChange, summeCent, platzhalter }) {
  function setPos(i, patch) {
    onChange(positionen.map((p, idx) => (idx === i ? { ...p, ...patch } : p)));
  }
  return (
    <Gruppe titel="Positionen">
      {positionen.map((p, i) => (
        <div key={i} className="space-y-2 rounded-xl bg-surface p-3">
          <div className="flex items-start gap-1">
            <input
              className="input flex-1"
              value={p.beschreibung}
              placeholder={platzhalter}
              onChange={(e) => setPos(i, { beschreibung: e.target.value })}
            />
            {positionen.length > 1 && (
              <IconButton
                icon={IconX}
                label="Position entfernen"
                onClick={() => onChange(positionen.filter((_, idx) => idx !== i))}
              />
            )}
          </div>
          <div className="grid grid-cols-2 gap-3">
            <label className="block">
              <span className="field-label">Menge</span>
              <input
                className="input tabular-nums"
                inputMode="decimal"
                value={p.menge}
                onChange={(e) => setPos(i, { menge: e.target.value })}
              />
            </label>
            <label className="block">
              <span className="field-label">Einzelpreis (€)</span>
              <input
                className="input tabular-nums"
                inputMode="decimal"
                value={p.preisInput}
                placeholder="0,00"
                onChange={(e) => setPos(i, { preisInput: e.target.value })}
              />
            </label>
          </div>
        </div>
      ))}
      <div className="flex items-center justify-between">
        <button type="button" className="btn-ghost btn-sm" onClick={() => onChange([...positionen, leerePosition()])}>
          <IconPlus className="mr-1 h-3.5 w-3.5" /> Position
        </button>
        <span className="text-sm tabular-nums text-ink/60">Summe {formatEuro(summeCent)}</span>
      </div>
    </Gruppe>
  );
}
