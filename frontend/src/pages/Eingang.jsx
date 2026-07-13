import { useEffect, useRef, useState } from 'react';
import { useOutletContext } from 'react-router-dom';
import toast from 'react-hot-toast';
import { api, apiError } from '../api/client.js';
import BuchungModal from '../components/BuchungModal.jsx';
import { PageSpinner } from '../components/Spinner.jsx';
import { openBeleg, fileSize, ACCEPT } from '../lib/belege.js';
import { formatDateDE } from '../lib/format.js';

function NoGewerbe() {
  return (
    <div className="card p-12 text-center text-ink/60">
      Kein Gewerbe gewählt. Lege unter „Gewerbe" zuerst ein Gewerbe an.
    </div>
  );
}

export default function Eingang() {
  const { gewerbeId, jahr, reloadEingang } = useOutletContext();
  const [items, setItems] = useState([]);
  const [kategorien, setKategorien] = useState([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [verbuchen, setVerbuchen] = useState(null); // beleg objekt
  const [wizard, setWizard] = useState(null); // { queue: beleg[], i } — Abarbeiten-Modus
  const inputRef = useRef(null);

  async function load() {
    if (!gewerbeId) {
      setLoading(false);
      return;
    }
    setLoading(true);
    try {
      const [bel, kat] = await Promise.all([
        api.get('/api/belege', { params: { gewerbe_id: gewerbeId, status: 'offen' } }),
        api.get('/api/kategorien', { params: { jahr } }),
      ]);
      setItems(bel.data);
      setKategorien(kat.data);
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

  async function upload(e) {
    const files = Array.from(e.target.files || []);
    if (!files.length) return;
    setBusy(true);
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
      setBusy(false);
      if (inputRef.current) inputRef.current.value = '';
    }
  }

  async function remove(b) {
    if (!window.confirm(`Beleg „${b.original_name}" endgültig löschen?`)) return;
    try {
      await api.delete(`/api/belege/${b.id}`);
      await load();
    } catch (e) {
      toast.error(apiError(e));
    }
  }

  // Wizard: einen Beleg nach dem anderen verbuchen (Warteschlange = Snapshot beim Start).
  function startWizard() {
    setWizard({ queue: items, i: 0 });
  }
  function advanceWizard(queue, i) {
    if (i + 1 < queue.length) {
      setWizard({ queue, i: i + 1 });
    } else {
      setWizard(null);
      toast.success('Alle Belege abgearbeitet. 🎉');
    }
  }

  if (!gewerbeId) return <NoGewerbe />;
  if (loading) return <PageSpinner />;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl sm:text-3xl font-black tracking-tight">Eingang</h1>
          <p className="text-xs text-ink/60 mt-0.5">
            {items.length > 0
              ? `Noch ${items.length} ${items.length === 1 ? 'Beleg' : 'Belege'} zu bearbeiten.`
              : 'Belege sammeln und später (z. B. monatlich) verbuchen. PDF/JPG/PNG.'}
          </p>
        </div>
        <div className="flex gap-2">
          {items.length > 0 && (
            <button className="btn-primary" onClick={startWizard}>
              Jetzt abarbeiten ({items.length})
            </button>
          )}
          <button
            className={items.length > 0 ? 'btn-outline' : 'btn-primary'}
            onClick={() => inputRef.current?.click()}
            disabled={busy}
          >
            {busy ? 'Lädt…' : '+ Belege hochladen'}
          </button>
        </div>
        <input ref={inputRef} type="file" accept={ACCEPT} multiple className="hidden" onChange={upload} />
      </div>

      {items.length === 0 ? (
        <div className="card p-12 text-center text-ink/60">
          Eingang leer. Lade Belege hoch — Kategorien vergibst du beim Verbuchen.
        </div>
      ) : (
        <div className="space-y-3">
          {items.map((b) => (
            <div key={b.id} className="card p-4 flex items-center justify-between gap-3">
              <button
                type="button"
                onClick={() => openBeleg(b.id)}
                className="min-w-0 text-left"
                title={b.original_name}
              >
                <div className="font-bold text-royal hover:underline truncate">{b.original_name}</div>
                <div className="text-xs text-ink/50 mt-0.5">
                  {formatDateDE(b.created_at.slice(0, 10))} · {fileSize(b.size_bytes)}
                </div>
              </button>
              <div className="flex items-center gap-2 shrink-0">
                <button className="btn-primary btn-sm" onClick={() => setVerbuchen(b)}>
                  Verbuchen
                </button>
                <button className="btn-ghost btn-sm text-red-700" onClick={() => remove(b)}>
                  Löschen
                </button>
              </div>
            </div>
          ))}
        </div>
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
