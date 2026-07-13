import { useEffect, useMemo, useState } from 'react';
import { Link, useOutletContext } from 'react-router-dom';
import toast from 'react-hot-toast';
import { api, apiError } from '../api/client.js';
import BuchungModal from '../components/BuchungModal.jsx';
import { PageSpinner } from '../components/Spinner.jsx';
import { formatEuro } from '../lib/format.js';
import { TOPICS, NICHT_ABSETZBAR, loadCheckState, saveCheckState } from '../lib/jahresCheck.js';

function NoGewerbe() {
  return (
    <div className="card p-12 text-center text-ink/60">
      Kein Gewerbe gewählt. Lege unter „Gewerbe" zuerst ein Gewerbe an.
    </div>
  );
}

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

  if (!gewerbeId) return <NoGewerbe />;
  if (loading) return <PageSpinner />;

  const erledigtCount = TOPICS.filter(
    (t) => topicStats(t).anzahl > 0 || check.erledigt.has(t.key) || check.nichtRelevant.has(t.key),
  ).length;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl sm:text-3xl font-black tracking-tight">Jahres-Check {jahr}</h1>
        <p className="text-xs text-ink/60 mt-0.5">
          Die häufigsten Absetz-Themen für Selbstständige — einmal im Jahr durchgehen, nichts
          vergessen. Keine Steuerberatung.
        </p>
      </div>

      <div className="card p-4">
        <div className="flex items-baseline justify-between gap-3">
          <div className="text-[11px] font-bold tracking-wider text-ink/60 uppercase">Fortschritt</div>
          <div className="text-sm tabular-nums text-ink/70">
            {erledigtCount} von {TOPICS.length} Themen erledigt
          </div>
        </div>
        <div className="h-2 rounded-full bg-ink/5 mt-2">
          <div
            className="h-2 rounded-full bg-royal transition-all"
            style={{ width: `${(erledigtCount / TOPICS.length) * 100}%` }}
          />
        </div>
        {erledigtCount === TOPICS.length && (
          <div className="text-sm text-ink/70 mt-2">
            Alles durch! 🎉 Weiter geht's beim <Link to="/export" className="text-royal font-medium hover:underline">Export</Link>.
          </div>
        )}
      </div>

      <div className="space-y-3">
        {TOPICS.map((t) => {
          const { cent, anzahl } = topicStats(t);
          const isNichtRelevant = check.nichtRelevant.has(t.key);
          const isErledigt = check.erledigt.has(t.key);
          const done = anzahl > 0 || isErledigt;
          return (
            <div key={t.key} className={`card p-4 space-y-2 ${isNichtRelevant && !done ? 'opacity-60' : ''}`}>
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div className="font-bold">{t.frage}</div>
                {anzahl > 0 ? (
                  <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-royal text-paper text-[11px] font-bold tabular-nums shrink-0">
                    ✓ {anzahl} {anzahl === 1 ? 'Buchung' : 'Buchungen'} · {formatEuro(cent)}
                  </span>
                ) : isErledigt ? (
                  <span className="inline-flex items-center px-2 py-0.5 rounded-full bg-royal text-paper text-[11px] font-bold shrink-0">
                    ✓ Erledigt
                  </span>
                ) : isNichtRelevant ? (
                  <span className="inline-flex items-center px-2 py-0.5 rounded-full bg-ink/10 text-ink/60 text-[11px] font-bold shrink-0">
                    Nicht relevant
                  </span>
                ) : (
                  <span className="inline-flex items-center px-2 py-0.5 rounded-full bg-yellow-100 text-yellow-900 text-[11px] font-bold shrink-0">
                    Offen
                  </span>
                )}
              </div>
              <p className="text-sm text-ink/70">{t.text}</p>
              <div className="flex flex-wrap gap-2 pt-1">
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
                {t.info && (
                  <button className="btn-outline btn-sm" onClick={() => toggle('erledigt', t.key)}>
                    {isErledigt ? '✓ Erledigt — zurücknehmen' : 'Erledigt'}
                  </button>
                )}
                {!done && (
                  <button className="btn-ghost btn-sm" onClick={() => toggle('nichtRelevant', t.key)}>
                    {isNichtRelevant ? 'Doch relevant' : 'Nicht relevant'}
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>

      <div className="rounded-lg bg-red-50 border-l-4 border-red-400 p-4 space-y-2">
        <div className="font-bold text-red-900">Gehört NICHT in die Buchhaltung</div>
        <p className="text-sm text-red-900/80">
          Die häufigsten Anfängerfehler — diese Dinge sind keine Betriebsausgaben:
        </p>
        <ul className="text-sm text-red-900/80 space-y-1">
          {NICHT_ABSETZBAR.map(([titel, erklaerung]) => (
            <li key={titel}>
              <strong>{titel}</strong> — {erklaerung}
            </li>
          ))}
        </ul>
      </div>

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
