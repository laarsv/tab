import { useEffect, useState } from 'react';
import { Link, useOutletContext } from 'react-router-dom';
import toast from 'react-hot-toast';
import { api, apiError } from '../api/client.js';
import { IconFileText } from '../components/Icons.jsx';
import { Hinweis, KeinGewerbe, Leer, PageHeader, PUNKT, Row, Zustand } from '../components/PageParts.jsx';
import RechnungenTabs from '../components/RechnungenTabs.jsx';
import { PageSpinner } from '../components/Spinner.jsx';
import { formatDateDE, formatEuro } from '../lib/format.js';
import { openMahnungPdf, STUFEN } from '../lib/mahnwesen.js';

// Mahnwesen-Reiter (Aufbau wie Haben): überfällige Rechnungen mit Tagen, offenem Betrag, letzter
// Mahnung samt Frist und der Schaltfläche für die nächste Stufe.
export default function Mahnwesen() {
  const { gewerbeId } = useOutletContext();
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!gewerbeId) {
      setLoading(false);
      return;
    }
    setLoading(true);
    api
      .get('/api/mahnwesen/ueberfaellig', { params: { gewerbe_id: gewerbeId } })
      .then((res) => setItems(res.data.items))
      .catch((e) => toast.error(apiError(e)))
      .finally(() => setLoading(false));
  }, [gewerbeId]);

  if (!gewerbeId) return <KeinGewerbe />;

  return (
    <div>
      <PageHeader title="Rechnungen" sub="Überfällige Rechnungen mahnen — Zahlungserinnerung, Mahnung, letzte Mahnung" />
      <RechnungenTabs ueberfaellig={items.length} />

      {loading ? (
        <PageSpinner />
      ) : items.length === 0 ? (
        <Leer>
          Keine überfälligen Rechnungen. Überfällig ist eine versendete Rechnung, die nicht als bezahlt markiert ist
          und deren Fälligkeit abgelaufen ist.
        </Leer>
      ) : (
        <div className="mt-2">
          {items.map((r) => {
            const letzte = r.letzte_mahnung;
            return (
              <Row
                key={r.id}
                kind="late"
                icon={IconFileText}
                title={
                  <>
                    <span className="tabular-nums">{r.nummer}</span> · {r.empfaenger_name}
                  </>
                }
                sub={
                  <>
                    <Zustand ton="late">{r.tage_ueberfaellig} {r.tage_ueberfaellig === 1 ? 'Tag' : 'Tage'} überfällig</Zustand>
                    {PUNKT}
                    <span>
                      fällig {formatDateDE(r.faellig_am)}
                      {r.ohne_ziel ? ' (30 Tage nach Rechnungsdatum)' : ''}
                    </span>
                    {PUNKT}
                    {letzte ? (
                      <span>
                        <button
                          type="button"
                          className="underline decoration-ink/30 hover:text-royal"
                          onClick={() => openMahnungPdf(letzte.id)}
                        >
                          {STUFEN[letzte.stufe]}
                        </button>{' '}
                        vom {formatDateDE(letzte.datum)}, Frist bis {formatDateDE(letzte.frist_am)}
                      </span>
                    ) : (
                      <span>noch nicht gemahnt</span>
                    )}
                  </>
                }
                amount={formatEuro(r.offen_cent)}
                actionsClass="sm:w-[11rem]"
                actions={
                  <Link
                    to={`/rechnungen/mahnwesen/${r.id}`}
                    className={`${r.wartet ? 'btn-outline' : 'btn-primary'} btn-sm w-full sm:w-auto`}
                  >
                    {STUFEN[r.naechste_stufe]}
                  </Link>
                }
              />
            );
          })}
        </div>
      )}

      <Hinweis className="mt-6 text-xs">
        Läuft die Frist der letzten Mahnung noch, ist die nächste Stufe hell dargestellt. Standard-Zahlungsziel,
        Mahnfrist, Mahngebühren und Basiszinssatz stellst du beim{' '}
        <Link to="/gewerbe" className="font-bold underline">
          Gewerbe
        </Link>{' '}
        ein.
      </Hinweis>
    </div>
  );
}
