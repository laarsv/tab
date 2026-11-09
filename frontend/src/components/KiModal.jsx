import { useEffect, useState } from 'react';
import toast from 'react-hot-toast';
import { api, apiError } from '../api/client.js';
import { DialogFuss } from './DialogParts.jsx';
import { IconButton, IconPlus, IconSparkles, IconTrash } from './Icons.jsx';
import Modal from './Modal.jsx';
import { Hinweis, Row } from './PageParts.jsx';

function wann(iso) {
  if (!iso) return null;
  return new Date(`${iso}Z`).toLocaleDateString('de-DE', { day: '2-digit', month: '2-digit', year: 'numeric' });
}

// KI-Assistenten (MCP, nur lesen): Zugangs-Tokens erzeugen und widerrufen. Das Token steht nur einmal da.
export default function KiModal({ onClose }) {
  const [items, setItems] = useState(null);
  const [name, setName] = useState('');
  const [neu, setNeu] = useState(null); // { name, token }
  const [busy, setBusy] = useState(false);
  const url = `${window.location.origin}/api/mcp`;

  async function load() {
    try {
      setItems((await api.get('/api/ki/tokens')).data);
    } catch (e) {
      toast.error(apiError(e));
      setItems([]);
    }
  }
  useEffect(() => {
    load();
  }, []);

  async function erzeugen(e) {
    e.preventDefault();
    if (!name.trim()) return toast.error('Bitte einen Namen eintragen, z. B. „Claude Code auf dem Mac“.');
    setBusy(true);
    try {
      const res = await api.post('/api/ki/tokens', { name: name.trim() });
      setNeu(res.data);
      setName('');
      await load();
    } catch (err) {
      toast.error(apiError(err));
    } finally {
      setBusy(false);
    }
  }

  async function entfernen(t) {
    if (!window.confirm(`Zugang „${t.name}“ widerrufen? Der Assistent verliert sofort den Zugriff.`)) return;
    try {
      await api.delete(`/api/ki/tokens/${t.id}`);
      if (neu?.id === t.id) setNeu(null);
      await load();
    } catch (e) {
      toast.error(apiError(e));
    }
  }

  async function kopieren(text, was) {
    try {
      await navigator.clipboard.writeText(text);
      toast.success(`${was} kopiert.`);
    } catch {
      toast.error('Kopieren nicht möglich — bitte von Hand markieren.');
    }
  }

  const befehl = neu ? `claude mcp add --transport http vrwb-tab ${url} --header "Authorization: Bearer ${neu.token}"` : '';

  return (
    <Modal
      title="KI-Assistenten"
      subtitle="Lass einen Assistenten wie Claude Code deine Buchhaltung abfragen — nur lesend, nichts wird gebucht oder geändert."
      onClose={onClose}
      maxWidth="max-w-2xl"
    >
      <div className="space-y-4">
        <Hinweis>
          Der Assistent sieht auf Anfrage Kennzahlen, Summenblatt, Buchungen, Rechnungen, Anlagen, Fristen und die Übersicht
          deiner Firmen — <strong>diese Daten gehen an den Anbieter des Assistenten</strong>. Nicht enthalten: Belegdateien, Mail-Zugang,
          Einstellungen, Bank. Schreiben kann er nicht; das erzwingt der Server.
        </Hinweis>

        {neu && (
          <Hinweis ton="warn" titel={`Zugang „${neu.name}“ ist bereit`}>
            <p>Das Token wird <strong>nur jetzt</strong> angezeigt. Für Claude Code im Terminal:</p>
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <input className="input flex-1 font-mono text-xs" readOnly value={befehl} onFocus={(e) => e.target.select()} />
              <button type="button" className="btn-outline btn-sm" onClick={() => kopieren(befehl, 'Befehl')}>Befehl kopieren</button>
              <button type="button" className="btn-ghost btn-sm" onClick={() => kopieren(neu.token, 'Token')}>Nur Token</button>
            </div>
            <p className="mt-2 text-xs text-ink/70">
              Server-Adresse: <code>{url}</code> (Streamable HTTP, Header <code>Authorization: Bearer …</code>). Andere Clients tragen
              beides in ihrer MCP-Konfiguration ein.
            </p>
          </Hinweis>
        )}

        <div className="border-t border-ink/[0.08]">
          {items === null ? (
            <p className="py-8 text-center text-sm text-ink/60">Lädt…</p>
          ) : items.length === 0 ? (
            <p className="py-8 text-center text-sm text-ink/60">Noch kein Zugang.</p>
          ) : (
            items.map((t) => (
              <Row
                key={t.id}
                icon={IconSparkles}
                title={t.name}
                sub={<span>angelegt {wann(t.created_at)} · {t.letzte_nutzung ? `zuletzt genutzt ${wann(t.letzte_nutzung)}` : 'noch nicht genutzt'}</span>}
                actions={<IconButton icon={IconTrash} variant="danger" label="Zugang widerrufen" onClick={() => entfernen(t)} />}
              />
            ))
          )}
        </div>

        <form onSubmit={erzeugen} className="flex flex-wrap items-end gap-3 rounded-xl bg-surface p-4">
          <label className="block min-w-[12rem] flex-1">
            <span className="field-label">Name des Zugangs</span>
            <input className="input" value={name} maxLength={80} placeholder="z. B. Claude Code auf dem Mac"
              onChange={(e) => setName(e.target.value)} />
          </label>
          <button type="submit" className="btn-primary" disabled={busy}>
            <IconPlus className="mr-1 h-4 w-4" /> Zugang erzeugen
          </button>
        </form>

        <DialogFuss>
          <button className="btn-primary" onClick={onClose}>Fertig</button>
        </DialogFuss>
      </div>
    </Modal>
  );
}
