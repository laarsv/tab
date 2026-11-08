import { Hinweis } from './PageParts.jsx';
import { formatEuro } from '../lib/format.js';

// Kleinunternehmer-Grenzen (§19 UStG): Warnband für Buchungen und Übersicht; ohne Überschreitung nichts.
export default function KuGuard({ k }) {
  if (k.ku_warn_laufend) {
    return (
      <Hinweis ton="neg" titel="Kleinunternehmer-Grenze gerissen">
        Die KU-relevanten Einnahmen {formatEuro(k.ku_umsatz_cent)} (ohne steuerfreie Courtage und
        Anlagenverkäufe, §19 Abs. 2 UStG) überschreiten die laufende Grenze von{' '}
        {formatEuro(k.ku_grenze_laufend_cent)}. Der KU-Status entfällt — bitte Steuerberater
        kontaktieren. Tab deckt die Regelbesteuerung nicht ab.
      </Hinweis>
    );
  }
  if (k.ku_warn_vorjahr) {
    return (
      <Hinweis ton="warn" titel="Vorjahresgrenze überschritten">
        Die KU-relevanten Einnahmen {formatEuro(k.ku_umsatz_cent)} (ohne steuerfreie Courtage und
        Anlagenverkäufe) liegen über {formatEuro(k.ku_grenze_vorjahr_cent)}. Für das Folgejahr ggf.
        kein KU mehr — im Blick behalten, im Zweifel Steuerberater fragen.
      </Hinweis>
    );
  }
  return null;
}
