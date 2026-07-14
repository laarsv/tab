import signaturUrl from '../assets/logo-signatur.svg';

// Marken-Bausteine gemäß VRWB CI (Design-Projekt „VRWB Markenidentität").
//
// Wordmark (default) — Produkt-Lockup „Standalone": vrwb in Roboto 900, der
// Unterstrich wird zum Trenner in Royal, der Toolname hängt direkt dran in
// Roboto Mono 500 Royal, ~0,83× Größe, Laufweite −1 %. Einsatz: Login-Hero,
// Footer, Browser-Titel.
export default function Wordmark({ onInk = false, className = '' }) {
  return (
    <span className={`font-black tracking-wordmark ${onInk ? 'text-paper' : 'text-ink'} ${className}`}>
      vrwb
      <span className={onInk ? 'text-royal-soft' : 'text-royal'}>
        _<span className="font-mono font-medium tracking-toolname text-[0.83em]">tab</span>
      </span>
    </span>
  );
}

// SignaturLockup — „Im Lockup" (präferierte Marke im App-Header, CI-Update):
// handschriftliche Signatur in Royal (CSS-Mask), Haarlinie, rechts vrwb_ mit
// dem Toolnamen als Subline in Roboto Mono. Proportionen aus dem CI-Sheet,
// auf die Header-Höhe skaliert.
export function SignaturLockup({ className = '' }) {
  const mask = `url(${signaturUrl}) center / contain no-repeat`;
  return (
    <span className={`flex items-center gap-2.5 ${className}`} aria-label="vrwb tab">
      <span
        aria-hidden="true"
        className="h-11 w-[22px] shrink-0 bg-royal"
        style={{ WebkitMask: mask, mask }}
      />
      <span aria-hidden="true" className="h-8 w-px bg-ink/15" />
      <span className="flex flex-col gap-0.5">
        <span className="font-black tracking-wordmark text-ink text-xl leading-none">
          vrwb<span className="text-royal">_</span>
        </span>
        <span className="font-mono font-medium text-[10px] tracking-[0.04em] text-ink/50 leading-none">
          tab
        </span>
      </span>
    </span>
  );
}
