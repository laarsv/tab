import { useEffect, useState } from 'react';
import { useOutletContext } from 'react-router-dom';
import toast from 'react-hot-toast';
import { api, apiError } from '../api/client.js';
import BuchungModal from '../components/BuchungModal.jsx';
import { PageSpinner } from '../components/Spinner.jsx';
import { formatEuro, formatDateDE } from '../lib/format.js';

function NoGewerbe() {
  return (
    <div className="card p-12 text-center text-ink/60">
      Kein Gewerbe gewählt. Lege oben links bzw. unter „Gewerbe" zuerst ein Gewerbe an.
    </div>
  );
}

export default function Buchungen() {
  const { gewerbeId, jahr, reloadEingang } = useOutletContext();
  const [kategorien, setKategorien] = useState([]);
  const [items, setItems] = useState([]);
  const [kennzahlen, setKennzahlen] = useState(null);
  const [loading, setLoading] = useState(true);
  const [modal, setModal] = useState(null); // { buchung? } | null

  async function load() {
    if (!gewerbeId) {
      setLoading(false);
      return;
    }
    setLoading(true);
    try {
      const [kat, buch, kenn] = await Promise.all([
        api.get('/api/kategorien', { params: { jahr } }),
        api.get('/api/buchungen', { params: { gewerbe_id: gewerbeId, jahr } }),
        api.get('/api/kennzahlen', { params: { gewerbe_id: gewerbeId, jahr } }),
      ]);
      setKategorien(kat.data);
      setItems(buch.data);
      setKennzahlen(kenn.data);
      reloadEingang?.();
    } catch (e) {
      toast.error(apiError(e));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, [gewerbeId, jahr]); // eslint-disable-line react-hooks/exhaustive-deps

  async function remove(id) {
    if (!window.confirm('Diese Buchung wirklich löschen? Angehängte Belege wandern zurück in den Eingang.'))
      return;
    try {
      await api.delete(`/api/buchungen/${id}`);
      toast.success('Gelöscht.');
      await load();
    } catch (e) {
      toast.error(apiError(e));
    }
  }

  if (!gewerbeId) return <NoGewerbe />;
  if (loading) return <PageSpinner />;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl sm:text-3xl font-black tracking-tight">Buchungen {jahr}</h1>
          <p className="text-xs text-ink/60 mt-0.5">
            Eine Buchung = ein Beleg/Vorgang mit einer oder mehreren Positionen.
          </p>
        </div>
        <button className="btn-primary w-full sm:w-auto" onClick={() => setModal({})}>
          + Buchung
        </button>
      </div>

      {kennzahlen && <KuGuard k={kennzahlen} />}

      {kennzahlen && (
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <Kennzahl label="Einnahmen" cent={kennzahlen.einnahmen_cent} />
          <Kennzahl label="Ausgaben" cent={kennzahlen.ausgaben_cent} />
          <Kennzahl label="Saldo (ohne AfA)" cent={kennzahlen.einnahmen_cent - kennzahlen.ausgaben_cent} />
        </div>
      )}

      {items.length === 0 ? (
        <div className="card p-12 text-center text-ink/60">Keine Buchungen für {jahr}.</div>
      ) : (
        <div className="space-y-3">
          {items.map((b) => (
            <div key={b.id} className="card p-4 space-y-3">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-bold">{formatDateDE(b.datum)}</span>
                    {b.beleg_count > 0 && <Paperclip count={b.beleg_count} />}
                  </div>
                  {b.beschreibung && <div className="text-sm text-ink/70 mt-0.5">{b.beschreibung}</div>}
                </div>
                <div className="text-right shrink-0">
                  <div className="tabular-nums font-black">{formatEuro(b.summe_cent)}</div>
                  {b.positionen.length > 1 && (
                    <div className="text-[11px] text-ink/50">{b.positionen.length} Positionen</div>
                  )}
                </div>
              </div>

              <ul className="divide-y divide-ink/5 rounded-lg bg-mint-soft/5">
                {b.positionen.map((p) => (
                  <li key={p.id} className="flex items-center justify-between gap-3 px-3 py-2 text-sm">
                    <span className={p.kategorie_typ === 'einnahme' ? 'text-mint font-bold' : ''}>
                      {p.kategorie_name}
                    </span>
                    <span className="tabular-nums whitespace-nowrap">
                      {p.kategorie_typ === 'einnahme' ? '+' : '−'}
                      {formatEuro(p.betrag_cent)}
                    </span>
                  </li>
                ))}
              </ul>

              <div className="flex gap-2">
                <button className="btn-outline btn-sm" onClick={() => setModal({ buchung: b })}>
                  Bearbeiten
                </button>
                <button className="btn-ghost btn-sm text-red-700" onClick={() => remove(b.id)}>
                  Löschen
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {modal && (
        <BuchungModal
          buchung={modal.buchung}
          gewerbeId={gewerbeId}
          kategorien={kategorien}
          onClose={() => setModal(null)}
          onSaved={load}
        />
      )}
    </div>
  );
}

function Paperclip({ count }) {
  return (
    <span className="inline-flex items-center gap-1 align-middle text-ink/50 text-xs" title={`${count} Beleg(e)`}>
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-3.5 w-3.5">
        <path d="M21.44 11.05l-9.19 9.19a6 6 0 01-8.49-8.49l9.19-9.19a4 4 0 015.66 5.66l-9.2 9.19a2 2 0 01-2.83-2.83l8.49-8.48" />
      </svg>
      <span className="tabular-nums">{count}</span>
    </span>
  );
}

function Kennzahl({ label, cent }) {
  return (
    <div className="card p-4">
      <div className="text-[11px] font-bold tracking-wider text-ink/60 uppercase">{label}</div>
      <div className="text-xl font-black tabular-nums mt-1">{formatEuro(cent)}</div>
    </div>
  );
}

function KuGuard({ k }) {
  if (k.ku_warn_laufend) {
    return (
      <div className="p-4 rounded flex items-start gap-3 bg-red-50 border-l-4 border-red-500 text-red-900">
        <div>
          <div className="font-bold">Kleinunternehmer-Grenze gerissen</div>
          <div className="text-sm mt-0.5">
            Einnahmen {formatEuro(k.einnahmen_cent)} überschreiten die laufende Grenze von{' '}
            {formatEuro(k.ku_grenze_laufend_cent)}. Der KU-Status entfällt — bitte Steuerberater
            kontaktieren. Tab deckt die Regelbesteuerung nicht ab.
          </div>
        </div>
      </div>
    );
  }
  if (k.ku_warn_vorjahr) {
    return (
      <div className="p-4 rounded flex items-start gap-3 bg-yellow-100 text-yellow-900">
        <div>
          <div className="font-bold">Vorjahresgrenze überschritten</div>
          <div className="text-sm mt-0.5">
            Einnahmen {formatEuro(k.einnahmen_cent)} liegen über {formatEuro(k.ku_grenze_vorjahr_cent)}.
            Für das Folgejahr ggf. kein KU mehr — im Blick behalten, im Zweifel Steuerberater fragen.
          </div>
        </div>
      </div>
    );
  }
  return null;
}
