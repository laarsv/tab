import { useEffect, useRef, useState } from 'react';

// Custom-Dropdown gemäß DESIGN.md §5.8 — kein natives <select>.
// options: [{ value, label, group? }]
export default function Dropdown({
  value,
  onChange,
  options,
  placeholder = 'Bitte wählen',
  disabled = false,
  id,
}) {
  const [open, setOpen] = useState(false);
  const [highlight, setHighlight] = useState(-1);
  const rootRef = useRef(null);
  const listRef = useRef(null);

  const selected = options.find((o) => String(o.value) === String(value));

  useEffect(() => {
    function onDoc(e) {
      if (rootRef.current && !rootRef.current.contains(e.target)) setOpen(false);
    }
    document.addEventListener('mousedown', onDoc);
    return () => document.removeEventListener('mousedown', onDoc);
  }, []);

  useEffect(() => {
    if (open) {
      const idx = options.findIndex((o) => String(o.value) === String(value));
      setHighlight(idx);
    }
  }, [open]); // eslint-disable-line react-hooks/exhaustive-deps

  function choose(opt) {
    onChange(opt.value);
    setOpen(false);
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
      setOpen(false);
    } else if (e.key === 'ArrowDown') {
      e.preventDefault();
      setHighlight((h) => Math.min(options.length - 1, h + 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setHighlight((h) => Math.max(0, h - 1));
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (highlight >= 0 && options[highlight]) choose(options[highlight]);
    }
  }

  return (
    <div className="relative" ref={rootRef}>
      <button
        type="button"
        id={id}
        aria-haspopup="listbox"
        aria-expanded={open}
        disabled={disabled}
        onClick={() => !disabled && setOpen((o) => !o)}
        onKeyDown={onKeyDown}
        className="w-full flex items-center justify-between gap-2 border border-ink/20 rounded-lg
                   px-3 py-2.5 text-base bg-paper text-left
                   focus:border-mint focus:ring-2 focus:ring-mint/30 outline-none
                   disabled:opacity-50 disabled:cursor-not-allowed"
      >
        <span className={`truncate ${selected ? '' : 'text-ink/50'}`}>
          {selected ? selected.label : placeholder}
        </span>
        <svg
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          className="h-4 w-4 shrink-0 text-ink/60"
        >
          <path d="M6 9l6 6 6-6" />
        </svg>
      </button>

      {open && (
        <ul
          role="listbox"
          ref={listRef}
          className="absolute z-50 mt-1 w-full max-h-64 overflow-auto rounded-lg border border-ink/10
                     bg-paper shadow-lg py-1"
        >
          {options.length === 0 && (
            <li className="px-3 py-2 text-sm text-ink/50">Keine Einträge</li>
          )}
          {options.map((opt, i) => {
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
      )}
    </div>
  );
}
