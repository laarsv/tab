import { Link } from 'react-router-dom';
import { Hinweis } from './PageParts.jsx';

// Band auf den Seiten, deren Daten das Jahres-Abschluss sperrt (Buchungen, AfA, Fahrten).
// Gesperrt wird in der Datenbank — das Band erklärt nur, warum Änderungen abgelehnt werden.
export default function AbschlussHinweis({ jahr, abgeschlossen }) {
  if (!abgeschlossen) return null;
  return (
    <Hinweis ton="warn" titel={`${jahr} ist abgeschlossen`} className="mt-5">
      Buchungen, Belege, AfA und Fahrten dieses Jahres sind gesperrt.{' '}
      <Link to="/abschluss" className="font-bold underline">
        Zum Jahresabschluss
      </Link>{' '}
      — dort lässt es sich mit Begründung wieder öffnen.
    </Hinweis>
  );
}
