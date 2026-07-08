import { useEffect, useState } from 'react';

// Modal gemäß DESIGN.md §5.14 — Overlay + zentrierte Card, Mount-Transition, ESC + Backdrop.
export default function Modal({ title, eyebrow, onClose, children, maxWidth = 'max-w-lg' }) {
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
      onMouseDown={(e) => e.target === e.currentTarget && onClose()}
      className={`fixed inset-0 z-50 backdrop-blur-sm flex items-start justify-center p-4
                  overflow-y-auto bg-ink/60 transition-opacity duration-200 ${shown ? 'opacity-100' : 'opacity-0'}`}
    >
      <div
        className={`card ${maxWidth} w-full p-6 space-y-4 my-8 transform transition-all duration-200
                    ${shown ? 'opacity-100 scale-100' : 'opacity-0 scale-95'}`}
      >
        {eyebrow && (
          <p className="eyebrow">{eyebrow}</p>
        )}
        <h2 className="text-xl font-black">{title}</h2>
        {children}
      </div>
    </div>
  );
}
