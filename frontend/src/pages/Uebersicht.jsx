import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useOutletContext } from 'react-router-dom';
import toast from 'react-hot-toast';
import { api, apiError } from '../api/client.js';
import KuGuard from '../components/KuGuard.jsx';
import {
  IconArrowIn,
  IconArrowOut,
  IconBank,
  IconCalendar,
  IconChecklist,
  IconFileText,
  IconInbox,
  IconLock,
  IconPencil,
  IconPlus,
  IconReceipt,
  IconRepeat,
} from '../components/Icons.jsx';
import {
  Hinweis,
  Kennzahl,
  Kennzahlen,
  KeinGewerbe,
  Leer,
  PageHeader,
  PUNKT,
  Row,
  SectionHead,
  Zustand,
} from '../components/PageParts.jsx';
import { PageSpinner } from '../components/Spinner.jsx';
import { formatDateDE, formatEuro } from '../lib/format.js';

// Übersicht (Startseite, Aufbau wie Haben): Kennzahlen des Jahres, was gerade wartet, offene
// Rechnungen, zuletzt Gebuchtes. Die Seite rechnet nichts selbst — alles kommt aus /api/uebersicht;
// nur der Jahres-Check kommt aus dem Layout, weil sein Stand im Browser liegt.

const ICON = {
  ueberfaellig: IconReceipt,
  frist: IconCalendar,
  dauerbelege: IconRepeat,
  eingang: IconInbox,
  bank: IconBank,
  entwuerfe: IconPencil,
  angebote: IconFileText,
  abschluss: IconLock,
  check: IconChecklist,
};
const KIND = { neg: 'neg', warn: 'warn', leise: 'file' };

function tageText(t) {
  return `${t} ${t === 1 ? 'Tag' : 'Tage'}`;
}

export default function Uebersicht() {
  const { gewerbeId, jahr, checkOffen, eingangTick } = useOutletContext();
  const navigate = useNavigate();
  const [daten, setDaten] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!gewerbeId) {
      setLoading(false);
      return undefined;
    }
    let aktiv = true;
    setLoading(true);
    api
      .get('/api/uebersicht', { params: { gewerbe_id: gewerbeId, jahr } })
      .then((res) => aktiv && setDaten(res.data))
      .catch((e) => toast.error(apiError(e, 'Übersicht konnte nicht geladen werden.')))
      .finally(() => aktiv && setLoading(false));
    return () => {
      aktiv = false;
    };
  }, [gewerbeId, jahr, eingangTick]);

  const aufgaben = useMemo(() => {
    const liste = daten ? [...daten.aufgaben] : [];
    if (daten && checkOffen > 0) {
      liste.push({
        schluessel: 'check',
        ton: 'leise',
        titel: `${checkOffen} ${checkOffen === 1 ? 'Thema' : 'Themen'} im Jahres-Check offen`,
        sub: `Dein Jahr ${jahr} Schritt für Schritt durchgehen`,
        to: '/check',
        aktion: 'Öffnen',
      });
    }
    return liste;
  }, [daten, checkOffen, jahr]);

  if (!gewerbeId) return <KeinGewerbe />;

  function gehe(a) {
    // Der Eingang startet den Wizard über einen Parameter, den die Buchungen-Seite einmal verbraucht.
    navigate(a.schluessel === 'eingang' ? `/buchungen?abarbeiten=${Date.now()}` : a.to);
  }

  const heuteText = new Date().toLocaleDateString('de-DE', {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  });
  const k = daten?.kennzahlen;
  const vj = k?.vorjahr;
  const hatVorjahr = vj && (vj.einnahmen_cent > 0 || vj.ausgaben_cent > 0);
  const f = daten?.forderungen;
  const leer = daten && daten.letzte_buchungen.length === 0 && f.anzahl === 0;

  return (
    <div>
      <PageHeader title="Übersicht" accent={jahr} sub={heuteText}>
        <Link to={`/buchungen?neu=${Date.now()}`} className="btn-primary lg:hidden">
          <IconPlus className="mr-1 h-4 w-4" /> Buchung
        </Link>
      </PageHeader>

      {loading && !daten ? (
        <PageSpinner />
      ) : !daten ? null : (
        <>
          {k && (
            <div className="mt-4 empty:hidden">
              <KuGuard k={k} />
            </div>
          )}

          {leer && (
            <Hinweis titel="Noch nichts gebucht" className="mt-4">
              Fang mit „Neue Buchung“ an, lade Belege in den Eingang oder folge der Anleitung unter{' '}
              <Link to="/einrichtung" className="font-bold text-royal hover:underline">
                Einrichtung &amp; Hilfe
              </Link>
              .
            </Hinweis>
          )}

          <Kennzahlen className="mt-6">
            <Kennzahl
              label="Einnahmen"
              value={formatEuro(k.einnahmen_cent)}
              hint={hatVorjahr ? `Vorjahr ${formatEuro(vj.einnahmen_cent)}` : undefined}
              royal
            />
            <Kennzahl
              label="Ausgaben"
              value={formatEuro(k.ausgaben_cent)}
              hint={hatVorjahr ? `Vorjahr ${formatEuro(vj.ausgaben_cent)}` : undefined}
            />
            <Kennzahl
              label="Saldo"
              value={formatEuro(k.einnahmen_cent - k.ausgaben_cent)}
              hint={hatVorjahr ? `Vorjahr ${formatEuro(vj.einnahmen_cent - vj.ausgaben_cent)}` : 'vor AfA und Abzugsquoten'}
            />
          </Kennzahlen>
          <Kennzahlen cols={2} className="mt-3">
            <Kennzahl
              label="Offene Forderungen"
              value={formatEuro(f.offen_cent)}
              hint={
                f.anzahl === 0
                  ? 'keine offene Rechnung'
                  : `${f.anzahl} ${f.anzahl === 1 ? 'Rechnung' : 'Rechnungen'}${f.ueberfaellig_anzahl ? ` · ${f.ueberfaellig_anzahl} überfällig` : ''}`
              }
            />
            <Kennzahl
              label="Umsatz nach § 19"
              value={formatEuro(k.ku_umsatz_cent)}
              hint={`Grenze: ${formatEuro(k.ku_grenze_vorjahr_cent)} Vorjahr · ${formatEuro(k.ku_grenze_laufend_cent)} laufend`}
            />
          </Kennzahlen>

          <SectionHead label="Zu erledigen" count={aufgaben.length} />
          {aufgaben.length === 0 ? (
            <Leer>Gerade wartet nichts auf dich.</Leer>
          ) : (
            aufgaben.map((a) => (
              <Row
                key={a.schluessel}
                kind={KIND[a.ton]}
                icon={ICON[a.schluessel]}
                title={a.titel}
                wrapTitle
                onTitleClick={() => gehe(a)}
                sub={a.ton === 'neg' ? <Zustand ton="neg">{a.sub}</Zustand> : a.sub}
                actions={
                  <button type="button" className="btn-outline btn-sm w-full sm:w-auto" onClick={() => gehe(a)}>
                    {a.aktion}
                  </button>
                }
              />
            ))
          )}

          {f.anzahl > 0 && (
            <>
              <SectionHead label="Offene Rechnungen" count={f.anzahl}>
                <Link to="/rechnungen" className="text-sm font-bold text-royal hover:underline">
                  Alle Rechnungen
                </Link>
              </SectionHead>
              {f.items.map((r) => (
                <Row
                  key={r.id}
                  kind={r.ueberfaellig ? 'neg' : 'file'}
                  icon={IconReceipt}
                  title={
                    <>
                      <span className="tabular-nums">{r.nummer}</span> · {r.empfaenger_name}
                    </>
                  }
                  onTitleClick={() => navigate('/rechnungen')}
                  titleHint="Zu den Rechnungen"
                  sub={
                    r.ueberfaellig ? (
                      <>
                        <Zustand ton="neg">{tageText(r.tage_ueberfaellig)} überfällig</Zustand>
                        {PUNKT}
                        <span className="tabular-nums">fällig {formatDateDE(r.faellig_am)}</span>
                      </>
                    ) : (
                      <span className="tabular-nums">fällig {formatDateDE(r.faellig_am)}</span>
                    )
                  }
                  amount={formatEuro(r.offen_cent)}
                />
              ))}
            </>
          )}

          {daten.letzte_buchungen.length > 0 && (
            <>
              <SectionHead label="Zuletzt gebucht">
                <Link to="/buchungen" className="text-sm font-bold text-royal hover:underline">
                  Alle Buchungen
                </Link>
              </SectionHead>
              {daten.letzte_buchungen.map((b) => (
                <Row
                  key={b.id}
                  kind={b.typ === 'einnahme' ? 'in' : 'out'}
                  icon={b.typ === 'einnahme' ? IconArrowIn : IconArrowOut}
                  title={b.beschreibung || b.kategorie}
                  onTitleClick={() => navigate('/buchungen')}
                  titleHint="Zu den Buchungen"
                  sub={
                    <>
                      <span className="tabular-nums">{formatDateDE(b.datum)}</span>
                      {b.beschreibung && (
                        <>
                          {PUNKT}
                          <span>{b.kategorie}</span>
                        </>
                      )}
                    </>
                  }
                  amount={`${b.typ ? (b.typ === 'einnahme' ? '+' : '−') : ''}${formatEuro(b.summe_cent)}`}
                  amountIn={b.typ === 'einnahme'}
                />
              ))}
            </>
          )}
        </>
      )}
    </div>
  );
}
