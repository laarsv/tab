// Produkt-Lockup „Standalone" gemäß VRWB CI (Abschnitt „Produkt-Lockups — Tools"):
// vrwb in Roboto 900 (Ink bzw. Weiß auf Ink), der Unterstrich wird zum Trenner in
// Royal, der Toolname hängt direkt dran in Roboto Mono 500 Royal, ~0,83× Größe,
// Laufweite −1 %. Toolnamen immer klein, ein Wort.
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
