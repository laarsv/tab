import { useEffect, useState } from 'react';
import { IconKey, IconMail, IconSparkles, IconUsers, IconX } from './Icons.jsx';
import KiModal from './KiModal.jsx';
import MailSetupModal from './MailSetupModal.jsx';
import { Eingebettet } from './Modal.jsx';
import PasskeyModal from './PasskeyModal.jsx';
import Steuerberatung from '../pages/Steuerberatung.jsx';

// Einstellungen als ein Fenster (Aufbau wie vrwb_flow, DESIGN.md §4): links die Bereiche, rechts Titel und Inhalt;
// am Handy der ganze Schirm mit den Bereichen als Reihe oben. Die Inhalte sind die bisherigen Dialoge — sie laufen hier
// „eingebettet“ (Modal.jsx: kein eigenes Overlay, kein eigener Titel). Neuer Bereich = Eintrag in BEREICHE.

export const BEREICHE = [
  { key: 'mail', label: 'E-Mail', titel: 'E-Mail-Versand & Beleg-Import', icon: IconMail, inhalt: MailSetupModal },
  { key: 'passkeys', label: 'Passkeys', titel: 'Passkeys', icon: IconKey, inhalt: PasskeyModal },
  { key: 'ki', label: 'KI-Assistenten', titel: 'KI-Assistenten', icon: IconSparkles, inhalt: KiModal },
  { key: 'steuerberatung', label: 'Steuerberatung', titel: 'Steuerberatung', icon: IconUsers, inhalt: Steuerberatung },
];

export default function EinstellungenFenster({ bereich = 'mail', onBereich, onClose }) {
  const [shown, setShown] = useState(false);
  const aktiv = BEREICHE.find((b) => b.key === bereich) || BEREICHE[0];
  const Inhalt = aktiv.inhalt;

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
      aria-label="Einstellungen"
      onMouseDown={(e) => e.target === e.currentTarget && onClose()}
      className={`fixed inset-0 z-50 flex items-stretch justify-center bg-ink/60 backdrop-blur-sm transition-opacity duration-200 sm:items-center sm:p-4 ${shown ? 'opacity-100' : 'opacity-0'}`}
    >
      <div className="flex h-full w-full flex-col overflow-hidden bg-paper shadow-xl sm:h-[680px] sm:max-h-[calc(100vh-2rem)] sm:max-w-[980px] sm:flex-row sm:rounded-2xl">
        {/* Bereiche: links als Spalte, am Handy als Reihe oben */}
        <nav aria-label="Bereiche der Einstellungen" className="shrink-0 border-b border-ink/[0.08] bg-surface sm:w-[220px] sm:border-b-0 sm:border-r">
          <div className="flex items-center justify-between px-4 pt-4 sm:px-5 sm:pt-6">
            <span className="eyebrow">Einstellungen</span>
            <button type="button" onClick={onClose} aria-label="Schließen" title="Schließen" className="btn-icon-ghost -mr-2 sm:hidden">
              <IconX />
            </button>
          </div>
          <div className="flex gap-1 overflow-x-auto px-2 pb-2 pt-2 sm:flex-col sm:overflow-visible sm:px-3 sm:pt-3">
            {BEREICHE.map((b) => {
              const Icon = b.icon;
              const offen = b.key === aktiv.key;
              return (
                <button
                  key={b.key}
                  type="button"
                  aria-current={offen ? 'page' : undefined}
                  ref={(el) => offen && el?.scrollIntoView({ block: 'nearest', inline: 'nearest' })}
                  onClick={() => onBereich(b.key)}
                  className={`flex h-11 shrink-0 items-center gap-2.5 whitespace-nowrap rounded-[10px] px-3 text-[15px] outline-none focus-visible:ring-2 focus-visible:ring-royal/40 sm:h-[38px]
                    ${offen ? 'bg-royal/[0.1] font-bold text-royal' : 'text-ink hover:bg-ink/5'}`}
                >
                  <Icon className="h-[18px] w-[18px] shrink-0" />
                  {b.label}
                </button>
              );
            })}
          </div>
        </nav>

        <section className="flex min-h-0 min-w-0 flex-1 flex-col">
          <div className="flex items-start gap-3 px-5 pt-5 sm:px-7 sm:pt-6">
            <h2 className="min-w-0 flex-1 text-2xl font-black leading-tight tracking-[-0.035em]">{aktiv.titel}</h2>
            <button type="button" onClick={onClose} aria-label="Schließen" title="Schließen" className="btn-icon-ghost -mr-2 -mt-1 hidden shrink-0 sm:inline-flex">
              <IconX />
            </button>
          </div>
          <div className="min-h-0 flex-1 overflow-y-auto px-5 pb-6 pt-2 sm:px-7">
            <Eingebettet.Provider value={true}>
              <Inhalt key={aktiv.key} onClose={onClose} />
            </Eingebettet.Provider>
          </div>
        </section>
      </div>
    </div>
  );
}
