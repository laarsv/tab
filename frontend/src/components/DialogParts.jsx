import toast from 'react-hot-toast';
import { api, apiError } from '../api/client.js';
import { IconBookmark, IconButton, IconPlus, IconX } from './Icons.jsx';
import { ArtikelWahl, useVorlagen } from './Vorlagen.jsx';
import { centToInput, formatEuro, parseEuroToCent } from '../lib/format.js';
import { SAETZE, positionsSummen } from '../lib/besteuerung.js';
import Dropdown from './Dropdown.jsx';

// Bausteine für Dialoge im Recap-Stil (DESIGN.md §6): Schalter statt Häkchen, Fußzeile mit
// Haarlinie, ruhige Gruppen, Positionen als getönte Flächen statt Rahmen.

// Schalter (Recap: Toggle) — Royal an, Ink-Tint aus, 44 × 26.
export function Schalter({ checked, onChange, disabled = false, label }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={`relative h-[26px] w-11 shrink-0 rounded-full outline-none transition-colors
        focus-visible:ring-2 focus-visible:ring-royal/40 disabled:cursor-not-allowed disabled:opacity-50
        ${checked ? 'bg-royal' : 'bg-ink/20'}`}
    >
      <span
        className={`absolute top-[3px] h-5 w-5 rounded-full bg-paper transition-all ${checked ? 'left-[21px]' : 'left-[3px]'}`}
      />
    </button>
  );
}

// Zeile mit Titel, Erklärsatz und Schalter rechts (die Einstellungs-Zeile von recap).
export function SchalterZeile({ titel, hinweis, checked, onChange, disabled }) {
  return (
    <div className="flex items-center gap-4 border-t border-ink/[0.08] py-3">
      <div className="min-w-0 flex-1">
        <div className="text-[15px] font-bold leading-snug">{titel}</div>
        {hinweis && <div className="text-[13px] leading-snug text-ink/60">{hinweis}</div>}
      </div>
      <Schalter checked={checked} onChange={onChange} disabled={disabled} label={titel} />
    </div>
  );
}

// Gruppe im Dialog: Eyebrow in Royal, darunter der Inhalt.
export function Gruppe({ titel, children, className = '' }) {
  return (
    <section className={`space-y-2 ${className}`}>
      {titel && <div className="eyebrow">{titel}</div>}
      {children}
    </section>
  );
}

// Fußzeile: Haarlinie, Aktionen rechts (am Handy gestapelt, Hauptaktion unten = zuletzt im Code).
// links: z. B. eine Nebenaktion („Vorschau"), steht links.
export function DialogFuss({ links, children }) {
  return (
    <div className="flex flex-col-reverse gap-2 border-t border-ink/[0.08] pt-4 sm:flex-row sm:items-center sm:justify-between">
      <div className="flex flex-col sm:flex-row">{links}</div>
      <div className="flex flex-col-reverse gap-2 sm:flex-row">{children}</div>
    </div>
  );
}

export function leerePosition(regel = false) {
  // satz: Steuersatz in Basispunkten als Text, nur bei Regelbesteuerung (Preise sind dann netto)
  return { beschreibung: '', menge: '1', preisInput: '', satz: regel ? '1900' : '' };
}

// Positionen aus der API (ust_bp) für den Editor
export function positionAusApi(p) {
  return { beschreibung: p.beschreibung, menge: String(p.menge).replace('.', ','), preisInput: centToInput(p.einzelpreis_cent), satz: p.ust_bp ? String(p.ust_bp) : '0' };
}

// Steuersatz einer Editor-Position (Basispunkte): ohne Wahl bei Regelbesteuerung 19 %, sonst 0
export function satzVon(p, regel) {
  if (!regel) return 0;
  return p.satz === '' || p.satz === undefined || p.satz === null ? 1900 : Number(p.satz) || 0;
}

// Editor-Positionen -> {menge, einzelpreis_cent, ust_bp} für Summen und Payload
export function positionenFuerSumme(positionen, regel = true) {
  return positionen.map((p) => ({
    menge: Number(String(p.menge).replace(',', '.')) || 0,
    einzelpreis_cent: parseEuroToCent(p.preisInput) || 0,
    ust_bp: satzVon(p, regel),
  }));
}

// Positionen einer Rechnung/eines Abos: je Position eine getönte Fläche (Beschreibung, Menge,
// Einzelpreis) + Summe. Gemeinsam für RechnungModal und AboModal.
// mitOptional (Angebote): je Position ein Schalter „Optional“ — optionale Positionen zählen nicht zur Summe
// (optionalCent zeigt sie getrennt).
export function PositionenEditor({
  positionen,
  onChange,
  summeCent,
  platzhalter,
  mitOptional = false,
  optionalCent = 0,
  gewerbeId = null, // mit Gewerbe: Artikelkatalog (Auswahl, Lesezeichen, Preis aus der Bezeichnung)
  regel = false, // Regelbesteuerung: Netto-Preise + Steuersatz je Position, Summe netto/USt/brutto
}) {
  const [artikel, setArtikel] = useVorlagen('/api/artikel', gewerbeId);
  const artikelZu = (text) => artikel.find((a) => a.bezeichnung.toLowerCase() === text.trim().toLowerCase());

  function setPos(i, patch) {
    onChange(positionen.map((p, idx) => (idx === i ? { ...p, ...patch } : p)));
  }

  // Beschreibung getippt: passt sie genau zu einem Artikel und der Preis ist noch leer, kommt der Preis dazu.
  function beschreibungAendern(i, text) {
    const a = !positionen[i].preisInput?.trim() ? artikelZu(text) : null;
    setPos(i, a ? { beschreibung: text, preisInput: centToInput(a.preis_cent) } : { beschreibung: text });
  }

  function artikelEinfuegen(a) {
    const neu = { beschreibung: a.bezeichnung, menge: '1', preisInput: centToInput(a.preis_cent), satz: regel ? '1900' : '' };
    const nurLeer = positionen.length === 1 && !positionen[0].beschreibung.trim() && !positionen[0].preisInput?.trim();
    onChange(nurLeer ? [neu] : [...positionen, neu]);
  }

  async function alsArtikelSpeichern(p) {
    const preis = parseEuroToCent(p.preisInput);
    try {
      const res = await api.post('/api/artikel', {
        gewerbe_id: Number(gewerbeId),
        bezeichnung: p.beschreibung.trim(),
        preis_cent: preis,
      });
      setArtikel((alt) => [...alt.filter((x) => x.id !== res.data.id), res.data]
        .sort((x, y) => x.bezeichnung.localeCompare(y.bezeichnung, 'de')));
      toast.success(res.status === 200 ? 'Artikel aktualisiert.' : 'Als Artikel gespeichert.');
    } catch (e) {
      toast.error(apiError(e, 'Artikel konnte nicht gespeichert werden.'));
    }
  }
  return (
    <Gruppe titel="Positionen">
      {positionen.map((p, i) => (
        <div key={i} className="space-y-2 rounded-xl bg-surface p-3">
          <div className="flex items-start gap-1">
            <input
              className="input flex-1"
              value={p.beschreibung}
              placeholder={platzhalter}
              onChange={(e) => beschreibungAendern(i, e.target.value)}
            />
            {gewerbeId && (() => {
              const preis = parseEuroToCent(p.preisInput);
              const bekannt = artikelZu(p.beschreibung);
              const gleich = bekannt && bekannt.preis_cent === preis;
              return (
                <IconButton
                  icon={IconBookmark}
                  label={gleich ? 'Steht schon im Katalog' : bekannt ? 'Artikelpreis im Katalog aktualisieren' : 'Als Artikel speichern'}
                  disabled={!p.beschreibung.trim() || !preis || preis <= 0 || Boolean(gleich)}
                  onClick={() => alsArtikelSpeichern(p)}
                />
              );
            })()}
            {positionen.length > 1 && (
              <IconButton
                icon={IconX}
                label="Position entfernen"
                onClick={() => onChange(positionen.filter((_, idx) => idx !== i))}
              />
            )}
          </div>
          <div className={regel ? 'grid grid-cols-3 gap-3' : 'grid grid-cols-2 gap-3'}>
            <label className="block">
              <span className="field-label">Menge</span>
              <input
                className="input tabular-nums"
                inputMode="decimal"
                value={p.menge}
                onChange={(e) => setPos(i, { menge: e.target.value })}
              />
            </label>
            <label className="block">
              <span className="field-label">{regel ? 'Einzelpreis netto (€)' : 'Einzelpreis (€)'}</span>
              <input
                className="input tabular-nums"
                inputMode="decimal"
                value={p.preisInput}
                placeholder="0,00"
                onChange={(e) => setPos(i, { preisInput: e.target.value })}
              />
            </label>
            {regel && (
              <div className="block">
                <span className="field-label">USt</span>
                <Dropdown value={String(satzVon(p, true))} onChange={(v) => setPos(i, { satz: String(v) })} options={SAETZE} />
              </div>
            )}
          </div>
          {mitOptional && (
            <div className="flex items-center gap-3 pt-0.5">
              <Schalter
                checked={Boolean(p.optional)}
                onChange={(an) => setPos(i, { optional: an })}
                label="Optionale Position"
              />
              <span className="text-[13px] leading-snug text-ink/70">
                Optional — Zusatzleistung, zählt nicht zur Angebotssumme
              </span>
            </div>
          )}
        </div>
      ))}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <button type="button" className="btn-ghost btn-sm" onClick={() => onChange([...positionen, leerePosition(regel)])}>
            <IconPlus className="mr-1 h-3.5 w-3.5" /> Position
          </button>
          {gewerbeId && <ArtikelWahl artikel={artikel} onWahl={artikelEinfuegen} />}
        </div>
        <span className="text-sm tabular-nums text-ink/60 text-right">
          {regel && (() => {
            const s = positionsSummen(positionenFuerSumme(positionen.filter((p) => !mitOptional || !p.optional)));
            return `netto ${formatEuro(s.netto_cent)} · USt ${formatEuro(s.ust_cent)} · `;
          })()}
          {mitOptional ? 'Angebotssumme' : 'Summe'}{' '}
          {formatEuro(regel ? positionsSummen(positionenFuerSumme(positionen.filter((p) => !mitOptional || !p.optional))).brutto_cent : summeCent)}
          {mitOptional && optionalCent > 0 && ` · optional ${formatEuro(optionalCent)}`}
        </span>
      </div>
    </Gruppe>
  );
}
