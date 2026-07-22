import { Link } from 'react-router-dom';
import Modal from './Modal.jsx';
import { NEUIGKEITEN, gesehenBis } from '../lib/neuigkeiten.js';
import { formatDateDE } from '../lib/format.js';

// „Was ist neu?" — Einträge kommen aus lib/neuigkeiten.js; ungelesene sind markiert.
export default function NeuigkeitenModal({ onClose }) {
  const bis = gesehenBis();
  return (
    <Modal title="Neu in tab" onClose={onClose} maxWidth="max-w-2xl">
      <div className="space-y-3">
        {NEUIGKEITEN.map((n) => (
          <div key={n.id} className="rounded-lg border border-ink/10 p-3.5 space-y-1">
            <div className="flex items-center justify-between gap-2">
              <div className="font-bold flex items-center gap-2">
                {n.titel}
                {n.id > bis && (
                  <span className="inline-flex items-center px-2 py-0.5 rounded-full bg-royal text-paper text-[10px] font-bold uppercase tracking-wider">
                    Neu
                  </span>
                )}
              </div>
              <span className="text-xs text-ink/40 tabular-nums shrink-0">{formatDateDE(n.datum)}</span>
            </div>
            <p className="text-sm text-ink/70">{n.text}</p>
            {n.link && (
              <Link to={n.link.to} onClick={onClose} className="inline-block text-sm text-royal font-medium hover:underline">
                {n.link.label} →
              </Link>
            )}
          </div>
        ))}
        <div className="flex justify-end pt-1">
          <button className="btn-primary" onClick={onClose}>
            Alles klar
          </button>
        </div>
      </div>
    </Modal>
  );
}
