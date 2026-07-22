import { useState } from 'react';
import { Link } from 'react-router-dom';
import Modal from './Modal.jsx';
import { NEUIGKEITEN, alleGelesen, gelesenIds, speichereGelesen } from '../lib/neuigkeiten.js';
import { formatDateDE } from '../lib/format.js';

// „Was ist neu?" — zeigt alle noch nicht bestätigten Einträge; jeder wird einzeln
// per „Gelesen"-Haken quittiert (Schließen allein reicht nicht). Ist alles
// gelesen, dient das Fenster als Archiv aller bisherigen Neuigkeiten.
export default function NeuigkeitenModal({ onClose }) {
  const [gelesen, setGelesen] = useState(gelesenIds());
  const offen = NEUIGKEITEN.filter((n) => !gelesen.has(n.id));
  const archiv = offen.length === 0;
  const liste = archiv ? NEUIGKEITEN : offen;

  function markiere(id) {
    const next = new Set(gelesen);
    next.add(id);
    setGelesen(next);
    speichereGelesen(next);
  }

  function markiereAlle() {
    setGelesen(alleGelesen());
  }

  return (
    <Modal title={archiv ? 'Neuigkeiten (Archiv)' : 'Neu in tab'} onClose={onClose} maxWidth="max-w-2xl">
      <div className="space-y-3">
        {archiv && (
          <p className="text-sm text-ink/60">
            Alles gelesen — hier zum Nachschlagen alle bisherigen Neuigkeiten.
          </p>
        )}
        {liste.map((n) => (
          <div key={n.id} className="rounded-lg border border-ink/10 p-3.5 space-y-1.5">
            <div className="flex items-center justify-between gap-2">
              <div className="font-bold">{n.titel}</div>
              <span className="text-xs text-ink/40 tabular-nums shrink-0">{formatDateDE(n.datum)}</span>
            </div>
            <p className="text-sm text-ink/70">{n.text}</p>
            <div className="flex items-center justify-between gap-2 pt-0.5">
              {n.link ? (
                <Link to={n.link.to} onClick={onClose} className="text-sm text-royal font-medium hover:underline">
                  {n.link.label} →
                </Link>
              ) : (
                <span />
              )}
              {!archiv && (
                <button className="btn-ghost btn-sm" onClick={() => markiere(n.id)}>
                  ✓ Gelesen — nicht mehr anzeigen
                </button>
              )}
            </div>
          </div>
        ))}
        <div className="flex flex-wrap justify-end gap-2 pt-1">
          {!archiv && (
            <button className="btn-outline" onClick={markiereAlle}>
              Alle als gelesen markieren
            </button>
          )}
          <button className="btn-primary" onClick={onClose}>
            Schließen
          </button>
        </div>
      </div>
    </Modal>
  );
}
