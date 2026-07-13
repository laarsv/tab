import { useMemo, useEffect, useRef, useState } from 'react';
import { useOutletContext } from 'react-router-dom';
import toast from 'react-hot-toast';
import { api, apiError } from '../api/client.js';
import BuchungModal from '../components/BuchungModal.jsx';
import Dropdown from '../components/Dropdown.jsx';
import { PageSpinner } from '../components/Spinner.jsx';
import { openBeleg, fileSize, ACCEPT } from '../lib/belege.js';
import { formatEuro, formatDateDE } from '../lib/format.js';

const MONATE = [
  'Januar', 'Februar', 'März', 'April', 'Mai', 'Juni',
  'Juli', 'August', 'September', 'Oktober', 'November', 'Dezember',
];

function NoGewerbe() {
  return (
    <div className="card p-12 text-center text-ink/60">
      Kein Gewerbe gewählt. Lege oben links bzw. unter „Gewerbe" zuerst ein Gewerbe an.
    </div>
  );
}

export default function Buchungen() {
  const { gewerbeId, jahr, reloadBadges } = useOutletContext();
  const [kategorien, setKategorien] = useState([]);
  const [items, setItems] = useState([]);
  const [belege, setBelege] = useState([]); // offener Beleg-Eingang
  const [kennzahlen, setKennzahlen] = useState(null);
  const [loading, setLoading] = useState(true);
  const [modal, setModal] = useState(null); // { buchung? } | null
  const [verbuchen, setVerbuchen] = useState(null); // einzelner Eingangs-Beleg
  const [wizard, setWizard] = useState(null); // { queue: beleg[], i } — Abarbeiten-Modus
  const [query, setQuery] = useState('');
  const [filterKat, setFilterKat] = useState('');
  const [filterMonat, setFilterMonat] = useState('');
  const [importing, setImporting] = useState(false);
  const [uploading, setUploading] = useState(false);
  const importRef = useRef(null);
  const uploadRef = useRef(null);

  async function load() {
    if (!gewerbeId) {
      setLoading(false);
      return;
    }
    setLoading(true);
    try {
      const [kat, buch, kenn, bel] = await Promise.all([
        api.get('/api/kategorien', { params: { jahr } }),
        api.get('/api/buchungen', { params: { gewerbe_id: gewerbeId, jahr } }),
        api.get('/api/kennzahlen', { params: { gewerbe_id: gewerbeId, jahr } }),
        api.get('/api/belege', { params: { gewerbe_id: gewerbeId, status: 'offen' } }),
      ]);
      setKategorien(kat.data);
      setItems(buch.data);
      setKennzahlen(kenn.data);
      setBelege(bel.data);
      reloadBadges?.();
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

  function duplicate(b) {
    // Kopie ohne id/datum: Modal startet als „Neue Buchung" mit heutigem Datum.
    setModal({
      buchung: {
        beschreibung: b.beschreibung,
        positionen: b.positionen.map((p) => ({
          kategorie_id: p.kategorie_id,
          betrag_cent: p.betrag_cent,
          beleg_details: p.beleg_details,
        })),
      },
    });
  }

  // ── Beleg-Eingang (integriert) ─────────────────────────────────────────────
  async function uploadBelege(e) {
    const files = Array.from(e.target.files || []);
    if (!files.length) return;
    setUploading(true);
    try {
      for (const file of files) {
        const form = new FormData();
        form.append('file', file);
        form.append('gewerbe_id', gewerbeId);
        await api.post('/api/belege', form);
      }
      toast.success(files.length > 1 ? `${files.length} Belege hochgeladen.` : 'Beleg hochgeladen.');
      await load();
    } catch (err) {
      toast.error(apiError(err, 'Upload fehlgeschlagen.'));
    } finally {
      setUploading(false);
      if (uploadRef.current) uploadRef.current.value = '';
    }
  }

  async function removeBeleg(b) {
    if (!window.confirm(`Beleg „${b.original_name}" endgültig löschen?`)) return;
    try {
      await api.delete(`/api/belege/${b.id}`);
      await load();
    } catch (e) {
      toast.error(apiError(e));
    }
  }

  function startWizard() {
    setWizard({ queue: belege, i: 0 });
  }
  function advanceWizard(queue, i) {
    if (i + 1 < queue.length) {
      setWizard({ queue, i: i + 1 });
    } else {
      setWizard(null);
      toast.success('Alle Belege abgearbeitet. 🎉');
    }
  }

  async function importCsv(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    setImporting(true);
    try {
      const form = new FormData();
      form.append('file', file);
      form.append('gewerbe_id', gewerbeId);
      const res = await api.post('/api/buchungen/import', form);
      toast.success(`${res.data.angelegt} Buchungen importiert.`);
      await load();
    } catch (err) {
      toast.error(apiError(err, 'Import fehlgeschlagen.'), { duration: 10000 });
    } finally {
      setImporting(false);
      if (importRef.current) importRef.current.value = '';
    }
  }

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return items.filter((b) => {
      if (filterMonat && b.datum.slice(5, 7) !== filterMonat) return false;
      if (filterKat && !b.positionen.some((p) => String(p.kategorie_id) === filterKat)) return false;
      if (!q) return true;
      const haystack = [
        b.beschreibung,
        formatDateDE(b.datum),
        ...b.positionen.flatMap((p) => [p.kategorie_name, p.beleg_details, formatEuro(p.betrag_cent)]),
      ]
        .filter(Boolean)
        .join(' ')
        .toLowerCase();
      return haystack.includes(q);
    });
  }, [items, query, filterKat, filterMonat]);

  const hasFilter = query.trim() || filterKat || filterMonat;

  const katOptions = useMemo(
    () => [
      { value: '', label: 'Alle Kategorien' },
      ...kategorien.filter((k) => !k.ist_afa).map((k) => ({ value: String(k.id), label: k.name })),
    ],
    [kategorien],
  );
  const monatOptions = useMemo(
    () => [
      { value: '', label: 'Alle Monate' },
      ...MONATE.map((m, i) => ({ value: String(i + 1).padStart(2, '0'), label: m })),
    ],
    [],
  );

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
        <div className="flex gap-2 shrink-0">
          <button
            className="btn-outline btn-sm hidden sm:inline-flex"
            onClick={() => importRef.current?.click()}
            disabled={importing}
            title="Semikolon-CSV: Datum;Betrag;Kategorie;Beschreibung;Beleg-Details — Datum TT.MM.JJJJ, Betrag 12,34, Kategorie als Name oder Key."
          >
            {importing ? 'Importiert…' : 'CSV-Import'}
          </button>
          <input ref={importRef} type="file" accept=".csv,text/csv" className="hidden" onChange={importCsv} />
          <button className="btn-primary" onClick={() => setModal({})}>
            + Buchung
          </button>
        </div>
      </div>

      {/* Beleg-Eingang: sammeln, später verbuchen — integriert statt eigener Seite */}
      <div className="card p-4 space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <div className="text-[11px] font-bold tracking-wider text-ink/60 uppercase">Beleg-Eingang</div>
            <div className="text-sm text-ink/70 mt-0.5">
              {belege.length > 0
                ? `Noch ${belege.length} ${belege.length === 1 ? 'Beleg' : 'Belege'} zu verbuchen.`
                : 'Leer. Belege (PDF/JPG/PNG) hochladen und später in Ruhe verbuchen.'}
            </div>
          </div>
          <div className="flex gap-2">
            {belege.length > 0 && (
              <button className="btn-primary btn-sm" onClick={startWizard}>
                Jetzt abarbeiten ({belege.length})
              </button>
            )}
            <button className="btn-outline btn-sm" onClick={() => uploadRef.current?.click()} disabled={uploading}>
              {uploading ? 'Lädt…' : '+ Belege hochladen'}
            </button>
          </div>
          <input ref={uploadRef} type="file" accept={ACCEPT} multiple className="hidden" onChange={uploadBelege} />
        </div>
        {belege.length > 0 && (
          <ul className="divide-y divide-ink/5 rounded-lg bg-royal-soft/5">
            {belege.map((b) => (
              <li key={b.id} className="flex items-center justify-between gap-3 px-3 py-2 text-sm">
                <button
                  type="button"
                  onClick={() => openBeleg(b.id)}
                  className="min-w-0 text-left text-royal font-medium hover:underline truncate"
                  title={b.original_name}
                >
                  {b.original_name}
                </button>
                <div className="flex items-center gap-2 shrink-0">
                  <span className="text-xs text-ink/50 hidden sm:inline">
                    {formatDateDE(b.created_at.slice(0, 10))} · {fileSize(b.size_bytes)}
                  </span>
                  <button className="btn-outline btn-sm" onClick={() => setVerbuchen(b)}>
                    Verbuchen
                  </button>
                  <button className="btn-ghost btn-sm text-red-700" onClick={() => removeBeleg(b)}>
                    Löschen
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>

      {kennzahlen && <KuGuard k={kennzahlen} />}

      {kennzahlen && (
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <Kennzahl label="Einnahmen" cent={kennzahlen.einnahmen_cent} />
          <Kennzahl label="Ausgaben" cent={kennzahlen.ausgaben_cent} />
          <Kennzahl
            label="Saldo (vor AfA & Abzugsquoten)"
            cent={kennzahlen.einnahmen_cent - kennzahlen.ausgaben_cent}
            hint="Gewinn laut EÜR: siehe Export"
          />
        </div>
      )}

      {items.length > 0 && <KategorieSummen items={items} jahr={jahr} />}

      {items.length > 0 && (
        <div className="flex flex-col sm:flex-row gap-2">
          <input
            className="input sm:max-w-xs"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Suchen (Beschreibung, Kategorie, Betrag)…"
          />
          <Dropdown value={filterKat} onChange={(v) => setFilterKat(String(v))} options={katOptions} variant="ghost" />
          <Dropdown value={filterMonat} onChange={(v) => setFilterMonat(String(v))} options={monatOptions} variant="ghost" />
          {hasFilter && (
            <button
              className="btn-ghost btn-sm self-start sm:self-center"
              onClick={() => {
                setQuery('');
                setFilterKat('');
                setFilterMonat('');
              }}
            >
              Zurücksetzen ({filtered.length}/{items.length})
            </button>
          )}
        </div>
      )}

      {items.length === 0 ? (
        <div className="card p-12 text-center text-ink/60">
          Keine Buchungen für {jahr}. Tipp: Altdaten aus der Excel-Liste per CSV-Import übernehmen.
        </div>
      ) : filtered.length === 0 ? (
        <div className="card p-12 text-center text-ink/60">Keine Treffer für die aktuelle Suche/Filter.</div>
      ) : (
        <div className="space-y-3">
          {filtered.map((b) => (
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

              <ul className="divide-y divide-ink/5 rounded-lg bg-royal-soft/5">
                {b.positionen.map((p) => (
                  <li key={p.id} className="flex items-center justify-between gap-3 px-3 py-2 text-sm">
                    <span className={p.kategorie_typ === 'einnahme' ? 'text-royal font-bold' : ''}>
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
                <button className="btn-ghost btn-sm" onClick={() => duplicate(b)}>
                  Duplizieren
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
          jahr={jahr}
          kategorien={kategorien}
          onClose={() => setModal(null)}
          onSaved={load}
        />
      )}

      {verbuchen && (
        <BuchungModal
          preBelege={[verbuchen]}
          gewerbeId={gewerbeId}
          jahr={jahr}
          kategorien={kategorien}
          onClose={() => setVerbuchen(null)}
          onSaved={load}
        />
      )}

      {wizard && (
        <BuchungModal
          key={wizard.queue[wizard.i].id}
          preBelege={[wizard.queue[wizard.i]]}
          gewerbeId={gewerbeId}
          jahr={jahr}
          kategorien={kategorien}
          wizard={{
            pos: wizard.i + 1,
            total: wizard.queue.length,
            onSkip: () => advanceWizard(wizard.queue, wizard.i),
          }}
          onClose={() => setWizard(null)}
          onSaved={async () => {
            // onClose läuft im Modal vor onSaved (setzt wizard=null) — hier mit den
            // eingefangenen Werten weiterschalten, damit der Wizard nicht abbricht.
            await load();
            advanceWizard(wizard.queue, wizard.i);
          }}
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

function Kennzahl({ label, cent, hint }) {
  return (
    <div className="card p-4">
      <div className="text-[11px] font-bold tracking-wider text-ink/60 uppercase">{label}</div>
      <div className="text-xl font-black tabular-nums mt-1">{formatEuro(cent)}</div>
      {hint && <div className="text-[11px] text-ink/50 mt-0.5">{hint}</div>}
    </div>
  );
}

// „Wohin ging das Geld" — Summen je Kategorie (das Pivot der Excel-Liste).
function KategorieSummen({ items, jahr }) {
  const [open, setOpen] = useState(false);
  const summen = useMemo(() => {
    const map = new Map();
    for (const b of items) {
      for (const p of b.positionen) {
        const cur = map.get(p.kategorie_name) || { name: p.kategorie_name, typ: p.kategorie_typ, cent: 0, anzahl: 0 };
        cur.cent += p.betrag_cent;
        cur.anzahl += 1;
        map.set(p.kategorie_name, cur);
      }
    }
    const list = [...map.values()].sort((a, b) => b.cent - a.cent);
    return {
      einnahmen: list.filter((s) => s.typ === 'einnahme'),
      ausgaben: list.filter((s) => s.typ === 'ausgabe'),
    };
  }, [items]);

  const maxCent = Math.max(1, ...summen.einnahmen.map((s) => s.cent), ...summen.ausgaben.map((s) => s.cent));

  return (
    <div className="card">
      <button
        type="button"
        className="w-full flex items-center justify-between px-4 py-3 text-left"
        onClick={() => setOpen((o) => !o)}
      >
        <span className="text-[11px] font-bold tracking-wider text-ink/60 uppercase">
          Summen je Kategorie {jahr}
        </span>
        <svg
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          className={`h-4 w-4 text-ink/50 transition-transform ${open ? 'rotate-180' : ''}`}
        >
          <path d="M6 9l6 6 6-6" />
        </svg>
      </button>
      {open && (
        <div className="px-4 pb-4 grid grid-cols-1 md:grid-cols-2 gap-x-8 gap-y-1">
          {[
            ['Einnahmen', summen.einnahmen],
            ['Ausgaben', summen.ausgaben],
          ].map(([label, list]) => (
            <div key={label}>
              <div className="text-xs font-bold text-ink/50 uppercase tracking-wider py-1">{label}</div>
              {list.length === 0 ? (
                <div className="text-sm text-ink/40 py-1">—</div>
              ) : (
                list.map((s) => (
                  <div key={s.name} className="py-1.5">
                    <div className="flex items-baseline justify-between gap-3 text-sm">
                      <span className="truncate">
                        {s.name} <span className="text-ink/40 text-xs">× {s.anzahl}</span>
                      </span>
                      <span className="tabular-nums whitespace-nowrap font-medium">{formatEuro(s.cent)}</span>
                    </div>
                    <div className="h-1 rounded-full bg-ink/5 mt-1">
                      <div
                        className={`h-1 rounded-full ${s.typ === 'einnahme' ? 'bg-royal' : 'bg-royal-soft'}`}
                        style={{ width: `${Math.max(2, (s.cent / maxCent) * 100)}%` }}
                      />
                    </div>
                  </div>
                ))
              )}
            </div>
          ))}
        </div>
      )}
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
            Die KU-relevanten Einnahmen {formatEuro(k.ku_umsatz_cent)} (ohne steuerfreie Courtage und
            Anlagenverkäufe, §19 Abs. 2 UStG) überschreiten die laufende Grenze von{' '}
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
            Die KU-relevanten Einnahmen {formatEuro(k.ku_umsatz_cent)} (ohne steuerfreie Courtage und
            Anlagenverkäufe) liegen über {formatEuro(k.ku_grenze_vorjahr_cent)}. Für das Folgejahr ggf.
            kein KU mehr — im Blick behalten, im Zweifel Steuerberater fragen.
          </div>
        </div>
      </div>
    );
  }
  return null;
}
