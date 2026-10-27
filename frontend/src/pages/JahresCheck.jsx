import { useEffect, useMemo, useState } from 'react';
import { Link, useOutletContext } from 'react-router-dom';
import toast from 'react-hot-toast';
import { api, apiError } from '../api/client.js';
import BuchungModal from '../components/BuchungModal.jsx';
import { IconBan, IconButton, IconCheck, IconCircle, IconCircleCheck } from '../components/Icons.jsx';
import { Fortschritt, Hinweis, KeinGewerbe, PageHeader, Row, Zustand } from '../components/PageParts.jsx';
import { PageSpinner } from '../components/Spinner.jsx';
import { formatEuro } from '../lib/format.js';
import { TOPICS, NICHT_ABSETZBAR, loadCheckState, saveCheckState } from '../lib/jahresCheck.js';

export default function JahresCheck() {
  const { gewerbeId, jahr, reloadBadges } = useOutletContext();
  const [kategorien, setKategorien] = useState([]);
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [modal, setModal] = useState(null); // { presetKategorieId }
  const [check, setCheck] = useState({ nichtRelevant: new Set(), erledigt: new Set() });

  async function load() {
    if (!gewerbeId) {
      setLoading(false);
      return;
    }
    setLoading(true);
    try {
      const [kat, buch] = await Promise.all([
        api.get('/api/kategorien', { params: { jahr } }),
        api.get('/api/buchungen', { params: { gewerbe_id: gewerbeId, jahr } }),
      ]);
      setKategorien(kat.data);
      setItems(buch.data);
      reloadBadges?.();
    } catch (e) {
      toast.error(apiError(e));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    setCheck(loadCheckState(gewerbeId, jahr));
  }, [gewerbeId, jahr]); // eslint-disable-line react-hooks/exhaustive-deps

  const katByKey = useMemo(() => Object.fromEntries(kategorien.map((k) => [k.key, k])), [kategorien]);
  const katKeyById = useMemo(
    () => Object.fromEntries(kategorien.map((k) => [k.id, k.key])),
    [kategorien],
  );

  // Summe + Anzahl je Kategorie-Key aus den echten Buchungen des Jahres.
  const statsByKey = useMemo(() => {
    const map = {};
    for (const b of items) {
      for (const p of b.positionen) {
        const key = katKeyById[p.kategorie_id];
        if (!key) continue;
        const cur = map[key] || { cent: 0, anzahl: 0 };
        cur.cent += p.betrag_cent;
        cur.anzahl += 1;
        map[key] = cur;
      }
    }
    return map;
  }, [items, katKeyById]);

  function topicStats(topic) {
    let cent = 0;
    let anzahl = 0;
    for (const a of topic.aktionen) {
      const s = statsByKey[a.katKey];
      if (s) {
        cent += s.cent;
        anzahl += s.anzahl;
      }
    }
    return { cent, anzahl };
  }

  function toggle(set, key) {
    const next = {
      nichtRelevant: new Set(check.nichtRelevant),
      erledigt: new Set(check.erledigt),
    };
    if (next[set].has(key)) next[set].delete(key);
    else next[set].add(key);
    setCheck(next);
    saveCheckState(gewerbeId, jahr, next);
    reloadBadges?.();
  }

  if (!gewerbeId) return <KeinGewerbe />;
  if (loading) return <PageSpinner />;

  const erledigtCount = TOPICS.filter(
    (t) => topicStats(t).anzahl > 0 || check.erledigt.has(t.key) || check.nichtRelevant.has(t.key),
  ).length;

  return (
    <div>
      <PageHeader
        title="Jahres-Check"
        accent={jahr}
        sub="Die häufigsten Absetz-Themen für Selbstständige — einmal im Jahr durchgehen, nichts vergessen. Keine Steuerberatung."
      />

      <Fortschritt text={`${erledigtCount} von ${TOPICS.length} Themen erledigt`} value={erledigtCount} max={TOPICS.length}>
        {erledigtCount === TOPICS.length && (
          <p className="mt-2 text-sm text-ink/70">
            Alles durch! Weiter geht's beim{' '}
            <Link to="/export" className="font-medium text-royal hover:underline">
              Export
            </Link>
            .
          </p>
        )}
      </Fortschritt>

      <div className="mt-4">
        {TOPICS.map((t) => {
          const { cent, anzahl } = topicStats(t);
          const isNichtRelevant = check.nichtRelevant.has(t.key);
          const isErledigt = check.erledigt.has(t.key);
          const done = anzahl > 0 || isErledigt;
          return (
            <Row
              key={t.key}
              kind={done ? 'in' : isNichtRelevant ? 'out' : 'warn'}
              icon={done ? IconCheck : isNichtRelevant ? IconBan : IconCircle}
              title={t.frage}
              wrapTitle
              muted={isNichtRelevant && !done}
              sub={
                anzahl > 0 ? (
                  <Zustand ton="royal">
                    {anzahl} {anzahl === 1 ? 'Buchung' : 'Buchungen'} · {formatEuro(cent)}
                  </Zustand>
                ) : isErledigt ? (
                  <Zustand ton="royal">Erledigt</Zustand>
                ) : isNichtRelevant ? (
                  <Zustand>Nicht relevant</Zustand>
                ) : (
                  <Zustand ton="warn">Offen</Zustand>
                )
              }
              actions={
                <>
                  {t.info && (
                    <IconButton
                      icon={IconCircleCheck}
                      label={isErledigt ? 'Erledigt — zurücknehmen' : 'Als erledigt abhaken'}
                      onClick={() => toggle('erledigt', t.key)}
                    />
                  )}
                  {!done && (
                    <IconButton
                      icon={IconBan}
                      label={isNichtRelevant ? 'Doch relevant' : 'Nicht relevant'}
                      onClick={() => toggle('nichtRelevant', t.key)}
                    />
                  )}
                </>
              }
            >
              <p className="mt-1 text-sm leading-snug text-ink/70">{t.text}</p>
              {(t.aktionen.some((a) => katByKey[a.katKey]) || (t.links || []).length > 0) && (
                <div className="mt-2 flex flex-wrap gap-2">
                  {t.aktionen.map((a) =>
                    katByKey[a.katKey] ? (
                      <button
                        key={a.katKey}
                        className="btn-outline btn-sm"
                        onClick={() => setModal({ presetKategorieId: katByKey[a.katKey].id })}
                      >
                        + {a.label}
                      </button>
                    ) : null,
                  )}
                  {(t.links || []).map((l) => (
                    <Link key={l.to} to={l.to} className="btn-outline btn-sm">
                      {l.label}
                    </Link>
                  ))}
                </div>
              )}
            </Row>
          );
        })}
      </div>

      <Hinweis ton="neg" titel="Gehört NICHT in die Buchhaltung" className="mt-8">
        <p>Die häufigsten Anfängerfehler — diese Dinge sind keine Betriebsausgaben:</p>
        <ul className="mt-1.5 space-y-1">
          {NICHT_ABSETZBAR.map(([titel, erklaerung]) => (
            <li key={titel}>
              <strong>{titel}</strong> — {erklaerung}
            </li>
          ))}
        </ul>
      </Hinweis>

      {modal && (
        <BuchungModal
          gewerbeId={gewerbeId}
          jahr={jahr}
          kategorien={kategorien}
          presetKategorieId={modal.presetKategorieId}
          onClose={() => setModal(null)}
          onSaved={load}
        />
      )}
    </div>
  );
}
