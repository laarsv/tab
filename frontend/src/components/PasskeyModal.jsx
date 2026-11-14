import { useEffect, useState } from 'react';
import toast from 'react-hot-toast';
import { api, apiError } from '../api/client.js';
import { passkeyFehler, passkeyHinzufuegen, passkeyVerfuegbar } from '../lib/passkey.js';
import { DialogFuss } from './DialogParts.jsx';
import { IconButton, IconKey, IconPencil, IconPlus, IconTrash } from './Icons.jsx';
import Modal, { useEingebettet } from './Modal.jsx';
import { Hinweis, Row } from './PageParts.jsx';

function wann(iso) {
  if (!iso) return null;
  return new Date(`${iso}Z`).toLocaleDateString('de-DE', { day: '2-digit', month: '2-digit', year: 'numeric' });
}

// Passkeys des angemeldeten Kontos: ansehen, hinzufügen, umbenennen, entfernen.
export default function PasskeyModal({ onClose }) {
  const [items, setItems] = useState(null);
  const [name, setName] = useState('');
  const [busy, setBusy] = useState(false);
  const verfuegbar = passkeyVerfuegbar();
  const eingebettet = useEingebettet();

  async function load() {
    try {
      setItems((await api.get('/api/passkeys')).data);
    } catch (e) {
      toast.error(apiError(e));
      setItems([]);
    }
  }
  useEffect(() => {
    load();
  }, []);

  async function hinzufuegen() {
    setBusy(true);
    try {
      const res = await passkeyHinzufuegen(name.trim());
      if (res) {
        toast.success('Passkey gespeichert.');
        setName('');
        await load();
      }
    } catch (e) {
      const text = passkeyFehler(e);
      if (text !== null) toast.error(text || apiError(e, 'Passkey konnte nicht angelegt werden.'));
    } finally {
      setBusy(false);
    }
  }

  async function umbenennen(p) {
    const neu = window.prompt('Neuer Name für den Passkey:', p.name);
    if (!neu || !neu.trim() || neu.trim() === p.name) return;
    try {
      await api.patch(`/api/passkeys/${p.id}`, { name: neu.trim() });
      await load();
    } catch (e) {
      toast.error(apiError(e));
    }
  }

  async function entfernen(p) {
    if (!window.confirm(`Passkey „${p.name}“ entfernen? Du kannst dich damit nicht mehr anmelden (Google/Passwort bleiben).`)) return;
    try {
      await api.delete(`/api/passkeys/${p.id}`);
      await load();
    } catch (e) {
      toast.error(apiError(e));
    }
  }

  return (
    <Modal
      title="Passkeys"
      subtitle="Anmelden mit Fingerabdruck, Gesicht oder Geräte-PIN — ohne Passwort. Zusätzlich zu Google oder Passwort."
      onClose={onClose}
      maxWidth="max-w-xl"
    >
      <div className="space-y-4">
        {!verfuegbar && (
          <Hinweis ton="warn">Dieser Browser unterstützt keine Passkeys. Nimm einen aktuellen Browser, am besten auf einem Gerät mit Fingerabdruck oder Gesichtserkennung.</Hinweis>
        )}
        <div className="border-t border-ink/[0.08]">
          {items === null ? (
            <p className="py-8 text-center text-sm text-ink/60">Lädt…</p>
          ) : items.length === 0 ? (
            <p className="py-8 text-center text-sm text-ink/60">Noch kein Passkey. Lege einen an, um dich ohne Passwort anzumelden.</p>
          ) : (
            items.map((p) => (
              <Row
                key={p.id}
                icon={IconKey}
                title={p.name}
                sub={<span>angelegt {wann(p.created_at)} · {p.letzte_nutzung ? `zuletzt genutzt ${wann(p.letzte_nutzung)}` : 'noch nicht genutzt'}</span>}
                actions={
                  <>
                    <IconButton icon={IconPencil} label="Umbenennen" onClick={() => umbenennen(p)} />
                    <IconButton icon={IconTrash} variant="danger" label="Passkey entfernen" onClick={() => entfernen(p)} />
                  </>
                }
              />
            ))
          )}
        </div>
        {verfuegbar && (
          <div className="flex flex-wrap items-end gap-3 rounded-xl bg-surface p-4">
            <label className="block min-w-[12rem] flex-1">
              <span className="field-label">Name (optional)</span>
              <input className="input" value={name} maxLength={60} placeholder="z. B. MacBook oder iPhone"
                onChange={(e) => setName(e.target.value)} />
            </label>
            <button type="button" className="btn-primary" disabled={busy} onClick={hinzufuegen}>
              <IconPlus className="mr-1 h-4 w-4" /> {busy ? 'Wartet auf dein Gerät…' : 'Passkey hinzufügen'}
            </button>
          </div>
        )}
        {!eingebettet && (
          <DialogFuss>
            <button className="btn-primary" onClick={onClose}>Fertig</button>
          </DialogFuss>
        )}
      </div>
    </Modal>
  );
}
