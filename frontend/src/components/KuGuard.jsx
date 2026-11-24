import { Hinweis } from './PageParts.jsx';
import { formatEuro } from '../lib/format.js';

// Kleinunternehmer-Grenzen (§19 Abs. 1 UStG): Warnband für Buchungen und Übersicht; ohne Überschreitung nichts.
// Reihenfolge nach Dringlichkeit: laufendes Jahr > 100.000 €, Vorjahr > 25.000 € (KU gilt schon jetzt nicht),
// dieses Jahr > 25.000 € (KU entfällt im Folgejahr).
export default function KuGuard({ k }) {
  if (k.ku_warn_laufend) {
    return (
      <Hinweis ton="neg" titel="Kleinunternehmer-Grenze gerissen">
        Die KU-relevanten Einnahmen {formatEuro(k.ku_umsatz_cent)} (ohne steuerfreie Courtage und
        Anlagenverkäufe, §19 Abs. 2 UStG) überschreiten die laufende Grenze von{' '}
        {formatEuro(k.ku_grenze_laufend_cent)}. Der KU-Status entfällt — bitte Steuerberater
        kontaktieren. Die Regelbesteuerung stellst du unter Gewerbe → Besteuerung ein.
      </Hinweis>
    );
  }
  if (k.ku_warn_vorjahr) {
    return (
      <Hinweis ton="neg" titel="Vorjahresgrenze überschritten — kein Kleinunternehmer in diesem Jahr">
        Der Umsatz des Vorjahres lag bei {formatEuro(k.ku_umsatz_vorjahr_cent)} (ohne steuerfreie Courtage und
        Anlagenverkäufe) und damit über {formatEuro(k.ku_grenze_vorjahr_cent)}. Dann gilt die
        Kleinunternehmerregelung für dieses Jahr nicht — bitte mit der Steuerberatung klären und die
        Regelbesteuerung ab diesem Jahr unter Gewerbe → Besteuerung eintragen.
      </Hinweis>
    );
  }
  if (k.ku_warn_folgejahr) {
    return (
      <Hinweis ton="warn" titel="Grenze für das Folgejahr überschritten">
        Die KU-relevanten Einnahmen {formatEuro(k.ku_umsatz_cent)} (ohne steuerfreie Courtage und
        Anlagenverkäufe) liegen über {formatEuro(k.ku_grenze_vorjahr_cent)}. Für das Folgejahr ggf.
        kein KU mehr — im Zweifel Steuerberater fragen; den Wechsel ab dem Folgejahr trägst du unter
        Gewerbe → Besteuerung ein.
      </Hinweis>
    );
  }
  return null;
}
