import { useEffect, useMemo, useRef, useState } from 'react';

// Custom-Dropdown gemäß DESIGN.shared.md §5.8 — kein natives <select>.
// options: [{ value, label }]; searchable: Tipp-Filter im Panel;
// variant: 'standard' (Feld-Optik, Formular) | 'ghost' (Inline-Wert in Zeile).
export default function Dropdown({
  value,
  onChange,
  options,
  placeholder = 'Bitte wählen',
  disabled = false,
  searchable = false,
  variant = 'standard',
  id,
}) {
  const ghost = variant === 'ghost';
  const [open, setOpen] = useState(false);
  const [highlight, setHighlight] = useState(-1);
  const [query, setQuery] = useState('');
  const rootRef = useRef(null);
  const searchRef = useRef(null);

  const selected = options.find((o) => String(o.value) === String(value));

  const filtered = useMemo(() => {
    if (!searchable || !query.trim()) return options;
    const q = query.trim().toLowerCase();
    return options.filter((o) => o.label.toLowerCase().includes(q));
  }, [options, query, searchable]);

  useEffect(() => {
    function onDoc(e) {
      if (rootRef.current && !rootRef.current.contains(e.target)) close();
    }
    document.addEventListener('mousedown', onDoc);
    return () => document.removeEventListener('mousedown', onDoc);
  }, []);

  useEffect(() => {
    if (open) {
      const idx = filtered.findIndex((o) => String(o.value) === String(value));
      setHighlight(idx);
      if (searchable) requestAnimationFrame(() => searchRef.current?.focus());
    }
  }, [open]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    setHighlight(filtered.length ? 0 : -1);
  }, [query]); // eslint-disable-line react-hooks/exhaustive-deps

  function close() {
    setOpen(false);
    setQuery('');
  }

  function choose(opt) {
    onChange(opt.value);
    close();
  }

  function onKeyDown(e) {
    if (disabled) return;
    if (!open && (e.key === 'Enter' || e.key === ' ' || e.key === 'ArrowDown')) {
      e.preventDefault();
      setOpen(true);
      return;
    }
    if (!open) return;
    if (e.key === 'Escape') {
      close();
    } else if (e.key === 'ArrowDown') {
      e.preventDefault();
      setHighlight((h) => Math.min(filtered.length - 1, h + 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setHighlight((h) => Math.max(0, h - 1));
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (highlight >= 0 && filtered[highlight]) choose(filtered[highlight]);
    }
  }

  return (
    <div className={ghost ? 'relative inline-block' : 'relative'} ref={rootRef}>
      <button
        type="button"
        id={id}
        aria-haspopup="listbox"
        aria-expanded={open}
        disabled={disabled}
        onClick={() => !disabled && (open ? close() : setOpen(true))}
        onKeyDown={onKeyDown}
        className={
          ghost
            ? `relative flex items-center justify-between gap-1.5 border border-transparent rounded-lg
               px-2 py-1 text-[13px] font-medium bg-ink/[0.04] hover:bg-ink/[0.07] text-left
               before:absolute before:-inset-y-2 before:inset-x-0 before:content-['']
               focus:border-mint focus:ring-2 focus:ring-mint/30 outline-none
               disabled:opacity-50 disabled:cursor-not-allowed`
            : `w-full flex items-center justify-between gap-2 border border-ink/20 rounded-lg
               px-3 py-2.5 text-base sm:py-1.5 sm:text-sm bg-paper text-left
               focus:border-mint focus:ring-2 focus:ring-mint/30 outline-none
               disabled:opacity-50 disabled:cursor-not-allowed`
        }
      >
        <span className={`truncate ${selected ? '' : 'text-ink/50'}`}>
          {selected ? selected.label : placeholder}
        </span>
        <svg
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          className={`${ghost ? 'h-3.5 w-3.5' : 'h-4 w-4'} shrink-0 text-ink/60`}
        >
          <path d="M6 9l6 6 6-6" />
        </svg>
      </button>

      {open && (
        <div
          className="absolute z-50 mt-1 w-full min-w-[176px] rounded-lg border border-ink/10 bg-paper shadow-lg"
        >
          {searchable && (
            <div className="p-2 border-b border-ink/10">
              <input
                ref={searchRef}
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={onKeyDown}
                placeholder="Suchen…"
                className="w-full border border-ink/20 rounded-lg px-3 py-2 text-base
                           sm:py-1.5 sm:text-sm
                           focus:border-mint focus:ring-2 focus:ring-mint/30 outline-none"
              />
            </div>
          )}
          <ul role="listbox" className="max-h-60 overflow-auto py-1">
            {filtered.length === 0 && (
              <li className="px-3 py-2 text-sm text-ink/50">Kein Treffer</li>
            )}
            {filtered.map((opt, i) => {
              const isSel = String(opt.value) === String(value);
              const isHi = i === highlight;
              return (
                <li
                  key={`${opt.value}`}
                  role="option"
                  aria-selected={isSel}
                  onMouseEnter={() => setHighlight(i)}
                  onClick={() => choose(opt)}
                  className={`px-3 py-2 text-sm cursor-pointer flex items-center justify-between
                    ${isSel ? 'bg-mint-soft/20 text-ink' : isHi ? 'bg-mint/10 text-ink' : 'text-ink'}`}
                >
                  <span className="truncate">{opt.label}</span>
                  {isSel && (
                    <svg
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2"
                      className="h-4 w-4 text-mint shrink-0"
                    >
                      <path d="M20 6L9 17l-5-5" />
                    </svg>
                  )}
                </li>
              );
            })}
          </ul>
        </div>
      )}
    </div>
  );
}
