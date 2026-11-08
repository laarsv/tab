import { useEffect, useState } from 'react';
import toast from 'react-hot-toast';
import { api, apiError } from '../api/client.js';
import { IconButton, IconLock, IconTrash, IconUnlock, IconUsers, IconX } from '../components/Icons.jsx';
import { Hinweis, Leer, PageHeader, PUNKT, Row, SectionHead, Zustand } from '../components/PageParts.jsx';
import { PageSpinner } from '../components/Spinner.jsx';

// Zugang für die Steuerberatung (Aufbau nach Haben): Einladungslink erzeugen, Zugänge sperren/entfernen.
// Die Steuerberatung kann nur lesen — der Server erzwingt das (auth/berater_guard.py), nicht diese Seite.

function datumZeit(iso) {
  if (!iso) return '';
  const d = new Date(`${iso}Z`);
  return d.toLocaleString('de-DE', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' });
}

export default function Steuerberatung() {
  const [daten, setDaten] = useState(null);
  const [bezeichnung, setBezeichnung] = useState('');
  const [neu, setNeu] = useState(null); // { link, bezeichnung } — nur dieses eine Mal sichtbar
  const [busy, setBusy] = useState(false);

  async function load() {
    try {
      setDaten((await api.get('/api/berater')).data);
    } catch (e) {
      toast.error(apiError(e));
    }
  }
  useEffect(() => {
    load();
  }, []);

  async function einladen(e) {
    e.preventDefault();
    if (!bezeichnung.trim()) return toast.error('Bitte eine Bezeichnung eintragen, z. B. den Namen der Kanzlei.');
    setBusy(true);
    try {
      const res = await api.post('/api/berater/einladungen', { bezeichnung: bezeichnung.trim() });
      setNeu({ link: `${window.location.origin}/einladung/${res.data.token}`, bezeichnung: res.data.bezeichnung });
      setBezeichnung('');
      await load();
    } catch (err) {
      toast.error(apiError(err));
    } finally {
      setBusy(false);
    }
  }

  async function kopieren() {
    try {
      await navigator.clipboard.writeText(neu.link);
      toast.success('Link kopiert.');
    } catch {
      toast.error('Kopieren nicht möglich — bitte den Link markieren und von Hand kopieren.');
    }
  }

  async function aktion(fn, fehler) {
    try {
      await fn();
      await load();
    } catch (e) {
      toast.error(apiError(e, fehler));
    }
  }

  if (!daten) return <PageSpinner />;

  return (
    <div>
      <PageHeader
        title="Steuerberatung"
        sub="Ein eigener Zugang, mit dem deine Steuerberatung nachsehen kann — ohne Export, nur lesend"
      />

      <Hinweis className="mt-5 space-y-1" titel="Was die Steuerberatung sieht">
        <p>
          Auswertung (EÜR-Summenblatt), Buchungen mit Belegen, bereits versendete Rechnungen, Abschreibungen und
          die Downloads (Journal, Summenblatt, Jahresarchiv). <strong>Nicht:</strong> Bank, Einstellungen, Mail-Konto,
          Entwürfe, Backup — und buchen, ändern oder löschen kann sie nie. Das erzwingt der Server bei jeder Anfrage.
        </p>
      </Hinweis>

      <SectionHead label="Einladen" />
      <form onSubmit={einladen} className="flex flex-wrap items-end gap-3">
        <label className="block min-w-[14rem] flex-1">
          <span className="field-label">Bezeichnung (z. B. Kanzlei)</span>
          <input className="input" value={bezeichnung} maxLength={120} onChange={(e) => setBezeichnung(e.target.value)}
            placeholder="Steuerkanzlei Muster" />
        </label>
        <button type="submit" className="btn-primary" disabled={busy}>
          Einladungslink erzeugen
        </button>
      </form>

      {neu && (
        <Hinweis ton="warn" titel={`Einladungslink für ${neu.bezeichnung}`} className="mt-4">
          <p>
            Schicke den Link auf einem sicheren Weg. Er ist <strong>einmal</strong> und {daten.gueltig_stunden} Stunden
            gültig und wird <strong>nur jetzt angezeigt</strong> — wer ihn hat, kann den Zugang anlegen.
          </p>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <input className="input flex-1 font-mono text-xs" readOnly value={neu.link} onFocus={(e) => e.target.select()} />
            <button type="button" className="btn-outline btn-sm" onClick={kopieren}>
              Kopieren
            </button>
            <button type="button" className="btn-ghost btn-sm" onClick={() => setNeu(null)}>
              Schließen
            </button>
          </div>
        </Hinweis>
      )}

      <SectionHead label="Zugänge" count={daten.zugaenge.length} />
      {daten.zugaenge.length === 0 ? (
        <Leer>Noch kein Zugang. Erzeuge oben einen Einladungslink.</Leer>
      ) : (
        daten.zugaenge.map((z) => (
          <Row
            key={z.id}
            kind={z.gesperrt ? 'neg' : 'file'}
            icon={IconUsers}
            title={`${z.name} · ${z.bezeichnung}`}
            wrapTitle
            muted={z.gesperrt}
            sub={
              <>
                <span>{z.email}</span>
                {PUNKT}
                {z.gesperrt ? (
                  <Zustand ton="neg">gesperrt</Zustand>
                ) : (
                  <span>zuletzt angemeldet {z.letzte_anmeldung ? datumZeit(z.letzte_anmeldung) : 'noch nie'}</span>
                )}
              </>
            }
            actions={
              <>
                <IconButton
                  icon={z.gesperrt ? IconUnlock : IconLock}
                  label={z.gesperrt ? 'Freigeben' : 'Sperren — beendet alle Sitzungen sofort'}
                  onClick={() =>
                    aktion(() => api.post(`/api/berater/zugaenge/${z.id}/sperre`, { gesperrt: !z.gesperrt }), 'Aktion fehlgeschlagen.')
                  }
                />
                <IconButton
                  icon={IconTrash}
                  variant="danger"
                  label="Zugang entfernen"
                  onClick={() => {
                    if (window.confirm(`Zugang von ${z.name} (${z.email}) entfernen? Die Anmeldung ist danach nicht mehr möglich.`))
                      aktion(() => api.delete(`/api/berater/zugaenge/${z.id}`), 'Entfernen fehlgeschlagen.');
                  }}
                />
              </>
            }
          />
        ))
      )}

      {daten.einladungen.length > 0 && (
        <>
          <SectionHead label="Offene Einladungen" count={daten.einladungen.length} />
          {daten.einladungen.map((e) => (
            <Row
              key={e.id}
              icon={IconUsers}
              title={e.bezeichnung}
              sub={<span>gültig bis {datumZeit(e.expires_at)}</span>}
              actions={
                <IconButton
                  icon={IconX}
                  label="Einladung zurückziehen"
                  onClick={() => aktion(() => api.delete(`/api/berater/einladungen/${e.id}`), 'Zurückziehen fehlgeschlagen.')}
                />
              }
            />
          ))}
        </>
      )}
    </div>
  );
}
