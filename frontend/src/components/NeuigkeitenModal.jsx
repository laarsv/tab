import { useState } from 'react';
import { Link } from 'react-router-dom';
import { DialogFuss } from './DialogParts.jsx';
import Modal from './Modal.jsx';
import { useAuth } from '../auth/AuthContext.jsx';
import { NEUIGKEITEN, gelesenIds, markiereGelesen } from '../lib/neuigkeiten.js';
import { formatDateDE } from '../lib/format.js';

// „Was ist neu?" — zeigt alle noch nicht bestätigten Einträge; jeder wird einzeln
// per „Gelesen"-Haken quittiert (Schließen allein reicht nicht). Ist alles
// gelesen, dient das Fenster als Archiv aller bisherigen Neuigkeiten.
export default function NeuigkeitenModal({ onClose }) {
  const { user } = useAuth();
  const email = user?.email || '';
  const [gelesen, setGelesen] = useState(() => gelesenIds(email));
  const offen = NEUIGKEITEN.filter((n) => !gelesen.has(n.id));
  const archiv = offen.length === 0;
  const liste = archiv ? NEUIGKEITEN : offen;

  function markiere(id) {
    setGelesen(markiereGelesen(email, [id]));
  }

  function markiereAlle() {
    setGelesen(markiereGelesen(email, NEUIGKEITEN.map((n) => n.id)));
  }

  return (
    <Modal
      title={archiv ? 'Neuigkeiten (Archiv)' : 'Neu in tab'}
      subtitle={archiv ? 'Alles gelesen — hier zum Nachschlagen alle bisherigen Neuigkeiten.' : undefined}
      onClose={onClose}
      maxWidth="max-w-2xl"
    >
      <div className="space-y-4">
        <div className="border-t border-ink/[0.08]">
          {liste.map((n) => (
            <div key={n.id} className="space-y-1.5 border-b border-ink/[0.08] py-3.5">
              <div className="flex items-baseline justify-between gap-3">
                <div className="font-bold leading-snug">{n.titel}</div>
                <span className="shrink-0 font-mono text-xs tabular-nums text-ink/60">{formatDateDE(n.datum)}</span>
              </div>
              <p className="text-sm leading-snug text-ink/70">{n.text}</p>
              {(n.link || !archiv) && (
                <div className="flex items-center justify-between gap-2 pt-0.5">
                  {n.link ? (
                    <Link to={n.link.to} onClick={onClose} className="text-sm font-medium text-royal hover:underline">
                      {n.link.label} →
                    </Link>
                  ) : (
                    <span />
                  )}
                  {!archiv && (
                    <button className="btn-ghost btn-sm text-royal" onClick={() => markiere(n.id)}>
                      ✓ Gelesen — nicht mehr anzeigen
                    </button>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
        <DialogFuss
          links={
            !archiv && (
              <button className="btn-ghost" onClick={markiereAlle}>
                Alle als gelesen markieren
              </button>
            )
          }
        >
          <button className="btn-primary" onClick={onClose}>
            Schließen
          </button>
        </DialogFuss>
      </div>
    </Modal>
  );
}
