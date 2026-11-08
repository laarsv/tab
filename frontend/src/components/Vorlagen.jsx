import { useCallback, useEffect, useState } from 'react';
import { api } from '../api/client.js';
import Dropdown from './Dropdown.jsx';
import { formatEuro } from '../lib/format.js';

// Artikelkatalog und Textbausteine (siehe routes/vorlagen.py): Listen je Gewerbe laden und als
// Auswahl in Rechnung, Angebot und Positionen anbieten. Reine Bequemlichkeit — Fehler beim Laden
// bleiben still, der Editor funktioniert auch ohne.

export function useVorlagen(pfad, gewerbeId) {
  const [items, setItems] = useState([]);
  const reload = useCallback(() => {
    if (!gewerbeId) return Promise.resolve();
    return api
      .get(pfad, { params: { gewerbe_id: gewerbeId } })
      .then((res) => setItems(res.data))
      .catch(() => {});
  }, [pfad, gewerbeId]);
  useEffect(() => {
    reload();
  }, [reload]);
  return [items, setItems, reload];
}

// Aus dem Katalog einfügen: onWahl bekommt den Artikel.
export function ArtikelWahl({ artikel, onWahl }) {
  if (!artikel.length) return null;
  return (
    <div className="w-56">
      <Dropdown
        value=""
        searchable
        placeholder="Aus dem Katalog einfügen"
        options={artikel.map((a) => ({ value: String(a.id), label: `${a.bezeichnung} · ${formatEuro(a.preis_cent)}` }))}
        onChange={(v) => {
          const a = artikel.find((x) => String(x.id) === String(v));
          if (a) onWahl(a);
        }}
      />
    </div>
  );
}

// Textbaustein einfügen: hängt den Text als neuen Absatz an (oder setzt ihn, wenn das Feld leer ist).
export function TextbausteinWahl({ gewerbeId, aktuell, onText }) {
  const [bausteine] = useVorlagen('/api/textbausteine', gewerbeId);
  if (!bausteine.length) return null;
  return (
    <div className="w-52">
      <Dropdown
        variant="ghost"
        alignRight
        value=""
        placeholder="Textbaustein einfügen"
        options={bausteine.map((b) => ({ value: String(b.id), label: b.name }))}
        onChange={(v) => {
          const b = bausteine.find((x) => String(x.id) === String(v));
          if (b) onText(aktuell.trim() ? `${aktuell.replace(/\s+$/, '')}\n${b.text}` : b.text);
        }}
      />
    </div>
  );
}
