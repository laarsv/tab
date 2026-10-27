import { useEffect, useState } from 'react';
import { IconX } from './Icons.jsx';

// Dialog im Recap-Stil (DESIGN.md §6): weiße Karte, Radius 16, Schatten nur hier (schwebend);
// Titel 26/900 links mit leiser Zeile darunter, rechts das Schließen-Kreuz.
// Overlay + Mount-Transition, ESC + Backdrop schließen.
// flush: Karte ohne Innenabstand und ohne eigenen Titel — der Inhalt gestaltet sich selbst
// (BuchungModal: Beleg links bündig, Felder rechts). Dann gilt title als Dialog-Beschriftung.
export default function Modal({
  title,
  eyebrow,
  subtitle,
  onClose,
  children,
  maxWidth = 'max-w-lg',
  flush = false,
}) {
  const [shown, setShown] = useState(false);

  useEffect(() => {
    const raf = requestAnimationFrame(() => setShown(true));
    function onKey(e) {
      if (e.key === 'Escape') onClose();
    }
    document.addEventListener('keydown', onKey);
    document.body.style.overflow = 'hidden';
    return () => {
      cancelAnimationFrame(raf);
      document.removeEventListener('keydown', onKey);
      document.body.style.overflow = '';
    };
  }, [onClose]);

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={flush ? title : undefined}
      onMouseDown={(e) => e.target === e.currentTarget && onClose()}
      className={`fixed inset-0 z-50 backdrop-blur-sm flex items-start justify-center p-4
                  overflow-y-auto bg-ink/60 transition-opacity duration-200 ${shown ? 'opacity-100' : 'opacity-0'}`}
    >
      <div
        className={`card shadow-xl ${maxWidth} w-full my-8 transform transition-all duration-200
                    ${flush ? 'overflow-hidden' : 'p-5 sm:p-7 space-y-5'}
                    ${shown ? 'opacity-100 scale-100' : 'opacity-0 scale-95'}`}
      >
        {!flush && (
          <div className="flex items-start gap-3">
            <div className="min-w-0 flex-1">
              {eyebrow && <p className="eyebrow mb-1">{eyebrow}</p>}
              <h2 className="text-2xl font-black leading-tight tracking-[-0.035em]">{title}</h2>
              {subtitle && <p className="mt-1 text-sm text-ink/60">{subtitle}</p>}
            </div>
            <button
              type="button"
              onClick={onClose}
              aria-label="Schließen"
              title="Schließen"
              className="btn-icon-ghost -mr-2 -mt-1.5 shrink-0"
            >
              <IconX />
            </button>
          </div>
        )}
        {children}
      </div>
    </div>
  );
}
