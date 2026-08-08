import { belegTyp, belegInlineUrl, openBeleg, TYP_LABEL } from '../lib/belege.js';

// Icons (inline SVG, currentColor, stroke-2 gemäß DESIGN.md).
function TypIcon({ typ, className = 'h-5 w-5' }) {
  const common = { viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: 2, className };
  if (typ === 'bild') {
    return (
      <svg {...common}>
        <rect x="3" y="3" width="18" height="18" rx="2" />
        <circle cx="8.5" cy="8.5" r="1.5" />
        <path d="M21 15l-5-5L5 21" />
      </svg>
    );
  }
  if (typ === 'xml') {
    return (
      <svg {...common}>
        <path d="M8 6l-5 6 5 6M16 6l5 6-5 6" />
      </svg>
    );
  }
  // pdf / sonst: Dokument
  return (
    <svg {...common}>
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <path d="M14 2v6h6" />
    </svg>
  );
}

// Farbiges Dateityp-Badge (Royal-Palette, CI-konform) für Listen.
export function BelegTypBadge({ beleg, className = '' }) {
  const typ = belegTyp(beleg);
  return (
    <span
      className={`inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-lg
                  bg-royal-soft/25 text-royal ${className}`}
      title={TYP_LABEL[typ]}
    >
      <TypIcon typ={typ} />
    </span>
  );
}

// Dokument-Vorschau (Split-View beim Verbuchen): PDF/Bild inline, XML als Hinweis.
export default function BelegVorschau({ beleg, className = '' }) {
  const typ = belegTyp(beleg);
  const src = belegInlineUrl(beleg.id);

  return (
    <div className={`flex flex-col rounded-lg border border-ink/10 bg-ink/[0.03] overflow-hidden ${className}`}>
      <div className="flex items-center justify-between gap-2 px-3 py-2 border-b border-ink/10 bg-paper">
        <div className="flex items-center gap-2 min-w-0">
          <span className="text-royal"><TypIcon typ={typ} className="h-4 w-4" /></span>
          <span className="text-sm font-medium truncate" title={beleg.original_name}>
            {beleg.original_name}
          </span>
        </div>
        <button
          type="button"
          className="btn-ghost btn-sm shrink-0"
          onClick={() => openBeleg(beleg.id)}
          title="Im neuen Tab öffnen"
        >
          Öffnen
        </button>
      </div>

      <div className="flex-1 min-h-[14rem] h-56 lg:h-[70vh] bg-ink/5">
        {typ === 'bild' ? (
          <img src={src} alt={beleg.original_name} className="h-full w-full object-contain" />
        ) : typ === 'pdf' ? (
          <iframe src={`${src}#toolbar=0&navpanes=0`} title={beleg.original_name} className="h-full w-full" />
        ) : (
          <div className="h-full flex flex-col items-center justify-center gap-2 p-4 text-center text-sm text-ink/60">
            <TypIcon typ={typ} className="h-8 w-8 text-royal/60" />
            {typ === 'xml' ? (
              <span>E-Rechnung (XML) — keine Bildvorschau. Die Daten stehen im Vorschlag rechts.</span>
            ) : (
              <span>Keine Vorschau möglich.</span>
            )}
            <button type="button" className="btn-outline btn-sm mt-1" onClick={() => openBeleg(beleg.id)}>
              Datei öffnen
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
