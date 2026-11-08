import { useEffect, useMemo, useState } from 'react';
import { useOutletContext } from 'react-router-dom';
import toast from 'react-hot-toast';
import { api, apiError } from '../api/client.js';
import BuchungModal from '../components/BuchungModal.jsx';
import { DialogFuss, Schalter } from '../components/DialogParts.jsx';
import Dropdown from '../components/Dropdown.jsx';
import {
  IconBookIn, IconButton, IconPause, IconPencil, IconPlay, IconPlus, IconRepeat, IconTrash, IconX,
} from '../components/Icons.jsx';
import Modal from '../components/Modal.jsx';
import { Hinweis, KeinGewerbe, Leer, PageHeader, PUNKT, Row, SectionHead, Zustand } from '../components/PageParts.jsx';
import { PageSpinner } from '../components/Spinner.jsx';
import { centToInput, formatDateDE, formatEuro, parseEuroToCent, todayISO } from '../lib/format.js';
import { betrieblichCent, bpZuText, privatCent, textZuBp } from '../lib/privat.js';

const INTERVALLE = [
  { value: 'monatlich', label: 'monatlich' },
  { value: 'vierteljaehrlich', label: 'vierteljährlich' },
  { value: 'halbjaehrlich', label: 'halbjährlich' },
  { value: 'jaehrlich', label: 'jährlich' },
];
const INTERVALL_LABEL = Object.fromEntries(INTERVALLE.map((i) => [i.value, i.label]));

// Dauerbelege (Aufbau wie Haben): Miete, Versicherung, Leasing, Abos einmal anlegen. Jeder Termin wird
// fällig und mit einem Klick zur Buchung — Tab bucht nie von selbst, damit nichts doppelt oder falsch
// im Jahr landet. Änderungen an der Vorlage gelten für künftige Termine.
export default function Dauerbelege() {
  const { gewerbeId, jahr, reloadBadges } = useOutletContext();
  const [items, setItems] = useState([]);
  const [kategorien, setKategorien] = useState([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(null); // {} = neu, Dauerbeleg = bearbeiten
  const [buchen, setBuchen] = useState(null); // { d, termin }
  const [bulkBusy, setBulkBusy] = useState(false);

  async function load() {
    if (!gewerbeId) {
      setLoading(false);
      return;
    }
    try {
      const [d, k] = await Promise.all([
        api.get('/api/dauerbelege', { params: { gewerbe_id: gewerbeId } }),
        api.get('/api/kategorien', { params: { jahr } }),
      ]);
      setItems(d.data);
      setKategorien(k.data);
    } catch (e) {
      toast.error(apiError(e));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    setLoading(true);
    load();
  }, [gewerbeId, jahr]); // eslint-disable-line react-hooks/exhaustive-deps

  const faellig = useMemo(() => items.filter((d) => d.faellige_termine.length > 0), [items]);
  const faelligGesamt = faellig.reduce((s, d) => s + d.faellige_termine.length, 0);

  async function danach() {
    await load();
    reloadBadges?.();
  }

  async function alleBuchen() {
    if (!window.confirm(`${faelligGesamt} fällige ${faelligGesamt === 1 ? 'Termin' : 'Termine'} jetzt buchen? Jede Buchung bekommt das Datum ihres Termins.`)) return;
    setBulkBusy(true);
    try {
      const res = await api.post('/api/dauerbelege/faellige-buchen', { gewerbe_id: Number(gewerbeId) });
      const { gebucht, fehler } = res.data;
      if (gebucht > 0) toast.success(`${gebucht} ${gebucht === 1 ? 'Buchung' : 'Buchungen'} angelegt.`);
      for (const f of fehler)
        toast.error(`${f.bezeichnung}, Termin ${formatDateDE(f.termin)}: ${f.meldung}`, { duration: 9000 });
      await danach();
    } catch (e) {
      toast.error(apiError(e));
    } finally {
      setBulkBusy(false);
    }
  }

  async function ueberspringen(d) {
    const termin = d.faellige_termine[0];
    if (!window.confirm(`Termin ${formatDateDE(termin)} von „${d.bezeichnung}" ohne Buchung überspringen (z. B. mietfreier Monat)?`)) return;
    try {
      await api.post(`/api/dauerbelege/${d.id}/ueberspringen`);
      await danach();
    } catch (e) {
      toast.error(apiError(e));
    }
  }

  async function umschalten(d) {
    try {
      await api.patch(`/api/dauerbelege/${d.id}`, { aktiv: !d.aktiv });
      toast.success(d.aktiv ? 'Pausiert.' : 'Fortgesetzt ab dem nächsten Termin.');
      await danach();
    } catch (e) {
      toast.error(apiError(e));
    }
  }

  async function loeschen(d) {
    if (!window.confirm(`Dauerbeleg „${d.bezeichnung}" löschen?`)) return;
    try {
      await api.delete(`/api/dauerbelege/${d.id}`);
      toast.success('Gelöscht.');
      await danach();
    } catch (e) {
      toast.error(apiError(e), { duration: 7000 });
    }
  }

  if (!gewerbeId) return <KeinGewerbe />;
  if (loading) return <PageSpinner />;

  return (
    <div>
      <PageHeader title="Dauerbelege" sub="Miete, Versicherung, Leasing, Abos — einmal anlegen, jeden Termin mit einem Klick buchen">
        <button className="btn-primary" onClick={() => setEditing({})}>
          <IconPlus className="mr-1 h-4 w-4" /> Dauerbeleg
        </button>
      </PageHeader>

      {faellig.length > 0 && (
        <>
          <SectionHead label="Fällig" count={faelligGesamt}>
            <button className="btn-outline btn-sm" onClick={alleBuchen} disabled={bulkBusy}>
              {bulkBusy ? 'Bucht…' : `Alle ${faelligGesamt} buchen`}
            </button>
          </SectionHead>
          {faellig.map((d) => {
            const termin = d.faellige_termine[0];
            const mehr = d.faellige_termine.length - 1;
            return (
              <Row
                key={d.id}
                kind="warn"
                icon={IconRepeat}
                title={d.bezeichnung}
                sub={
                  <>
                    <Zustand ton="warn">Fällig</Zustand>
                    {PUNKT}
                    <span className="tabular-nums">Termin {formatDateDE(termin)}</span>
                    {mehr > 0 && (
                      <>
                        {PUNKT}
                        <span>
                          + {mehr} weitere{mehr === 1 ? 'r' : ''} fällig
                        </span>
                      </>
                    )}
                    {PUNKT}
                    <span>{d.kategorie_name}</span>
                  </>
                }
                amount={`−${formatEuro(d.betrag_cent)}`}
                actions={
                  <>
                    <IconButton
                      icon={IconBookIn}
                      variant="primary"
                      label={`Termin ${formatDateDE(termin)} buchen…`}
                      onClick={() => setBuchen({ d, termin })}
                    />
                    <IconButton icon={IconX} label="Termin überspringen (ohne Buchung)" onClick={() => ueberspringen(d)} />
                  </>
                }
              />
            );
          })}
        </>
      )}

      <SectionHead label="Alle Dauerbelege" count={items.length} />
      {items.length === 0 ? (
        <Leer>
          Noch keine Dauerbelege. Lege Miete, Versicherung, Leasing oder ein Abo einmal an — Tab zeigt dir jeden
          Termin als fällig, und du buchst ihn mit einem Klick (oder ordnest die Abbuchung im Bank-Import zu).
        </Leer>
      ) : (
        items.map((d) => (
          <Row
            key={d.id}
            kind="out"
            icon={IconRepeat}
            muted={!d.aktiv || d.beendet}
            title={d.bezeichnung}
            sub={
              <>
                <Zustand ton="leise">{d.beendet ? 'Beendet' : !d.aktiv ? 'Pausiert' : 'Aktiv'}</Zustand>
                {PUNKT}
                <span>{INTERVALL_LABEL[d.intervall]}</span>
                {!d.beendet && (
                  <>
                    {PUNKT}
                    <span className="tabular-nums">nächster Termin {formatDateDE(d.naechste_am)}</span>
                  </>
                )}
                {d.endet_am && (
                  <>
                    {PUNKT}
                    <span className="tabular-nums">endet {formatDateDE(d.endet_am)}</span>
                  </>
                )}
                {PUNKT}
                <span>{d.kategorie_name}</span>
                {d.privat_bp > 0 && (
                  <>
                    {PUNKT}
                    <span className="tabular-nums">
                      {bpZuText(d.privat_bp)} % privat · betrieblich {formatEuro(d.betrieblich_cent)}
                    </span>
                  </>
                )}
                {d.buchungen_anzahl > 0 && (
                  <>
                    {PUNKT}
                    <span className="tabular-nums">{d.buchungen_anzahl} gebucht</span>
                  </>
                )}
              </>
            }
            amount={`−${formatEuro(d.betrag_cent)}`}
            actions={
              <>
                <IconButton icon={IconPencil} label="Bearbeiten" onClick={() => setEditing(d)} />
                {!d.beendet && (
                  <IconButton
                    icon={d.aktiv ? IconPause : IconPlay}
                    label={d.aktiv ? 'Pausieren' : 'Fortsetzen'}
                    onClick={() => umschalten(d)}
                  />
                )}
                {d.buchungen_anzahl === 0 && (
                  <IconButton icon={IconTrash} variant="danger" label="Löschen" onClick={() => loeschen(d)} />
                )}
              </>
            }
          >
            {d.notiz && <p className="mt-1 text-[13px] text-ink/60">{d.notiz}</p>}
          </Row>
        ))
      )}

      {editing && (
        <DauerbelegModal
          editing={editing}
          gewerbeId={gewerbeId}
          kategorien={kategorien}
          onClose={() => setEditing(null)}
          onSaved={danach}
        />
      )}

      {buchen && (
        <BuchungModal
          gewerbeId={gewerbeId}
          jahr={jahr}
          kategorien={kategorien}
          presetKategorieId={buchen.d.kategorie_id}
          presetBetragCent={buchen.d.betrag_cent}
          presetBeschreibung={buchen.d.bezeichnung}
          presetDatum={buchen.termin}
          presetRichtung="ausgabe"
          presetPrivatBp={buchen.d.privat_bp}
          dauerbeleg={{ id: buchen.d.id, termin: buchen.termin }}
          onClose={() => setBuchen(null)}
          onSaved={danach}
        />
      )}
    </div>
  );
}

function DauerbelegModal({ editing, gewerbeId, kategorien, onClose, onSaved }) {
  const isEdit = Boolean(editing.id);
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState(() => ({
    bezeichnung: editing.bezeichnung || '',
    notiz: editing.notiz || '',
    kategorie_id: editing.kategorie_id ? String(editing.kategorie_id) : '',
    betragInput: editing.betrag_cent ? centToInput(editing.betrag_cent) : '',
    privatAn: (editing.privat_bp || 0) > 0,
    privatInput: bpZuText(editing.privat_bp || 0),
    intervall: editing.intervall || 'monatlich',
    naechste_am: editing.naechste_am || todayISO(),
    endet_am: editing.endet_am || '',
  }));

  // nur, was ein Dauerbeleg sein kann: Ausgabe ohne AfA und ohne Pflicht-Details (Bewirtung, Geschenke)
  const options = useMemo(
    () =>
      kategorien
        .filter((k) => k.typ === 'ausgabe' && !k.ist_afa && !k.belegpflicht_extra)
        .map((k) => ({ value: String(k.id), label: k.name })),
    [kategorien],
  );

  const betrag = parseEuroToCent(form.betragInput);
  const bp = form.privatAn ? textZuBp(form.privatInput) : 0;

  async function save(e) {
    e.preventDefault();
    if (!form.bezeichnung.trim()) return toast.error('Bitte eine Bezeichnung angeben, z. B. „Miete Büro".');
    if (!form.kategorie_id) return toast.error('Bitte eine Kategorie wählen.');
    if (!betrag || betrag <= 0) return toast.error('Bitte einen gültigen Betrag angeben.');
    if (form.privatAn && bp === null) return toast.error('Privatanteil: bitte eine Zahl größer 0 bis 100 (%) angeben.');
    if (form.endet_am && form.endet_am < form.naechste_am) return toast.error('„Endet nach dem" liegt vor dem Termin.');
    const body = {
      bezeichnung: form.bezeichnung.trim(),
      notiz: form.notiz.trim() || null,
      kategorie_id: Number(form.kategorie_id),
      betrag_cent: betrag,
      privat_bp: bp || 0,
      intervall: form.intervall,
      naechste_am: form.naechste_am,
      endet_am: form.endet_am || null,
    };
    setBusy(true);
    try {
      if (isEdit) {
        await api.patch(`/api/dauerbelege/${editing.id}`, body);
        toast.success('Gespeichert — gilt für die künftigen Termine.');
      } else {
        await api.post('/api/dauerbelege', { gewerbe_id: Number(gewerbeId), ...body });
        toast.success('Dauerbeleg angelegt.');
      }
      onClose();
      await onSaved();
    } catch (err) {
      toast.error(apiError(err));
      setBusy(false);
    }
  }

  return (
    <Modal
      title={isEdit ? 'Dauerbeleg bearbeiten' : 'Neuer Dauerbeleg'}
      subtitle={isEdit ? 'Änderungen gelten für künftige Termine, gebuchte Termine bleiben.' : undefined}
      onClose={onClose}
      maxWidth="max-w-xl"
    >
      <form onSubmit={save} className="space-y-4">
        <label className="block">
          <span className="field-label">Bezeichnung</span>
          <input
            className="input"
            autoFocus
            value={form.bezeichnung}
            placeholder="z. B. Miete Büro, Haftpflicht, Handyvertrag"
            onChange={(e) => setForm({ ...form, bezeichnung: e.target.value })}
          />
        </label>
        <div className="block">
          <span className="field-label">Kategorie</span>
          <Dropdown
            value={form.kategorie_id}
            onChange={(v) => setForm({ ...form, kategorie_id: String(v) })}
            options={options}
            placeholder="Ausgabe-Kategorie suchen…"
            searchable
          />
        </div>
        <div className="grid grid-cols-1 gap-x-5 gap-y-2 sm:grid-cols-2">
          <label className="block">
            <span className="field-label">Betrag brutto je Termin (€)</span>
            <input
              className="input tabular-nums"
              inputMode="decimal"
              value={form.betragInput}
              placeholder="0,00"
              onChange={(e) => setForm({ ...form, betragInput: e.target.value })}
            />
          </label>
          <div className="block">
            <span className="field-label">Rhythmus</span>
            <Dropdown value={form.intervall} onChange={(v) => setForm({ ...form, intervall: String(v) })} options={INTERVALLE} />
          </div>
        </div>

        <div className="space-y-2">
          <div className="flex items-center gap-3">
            <Schalter checked={form.privatAn} onChange={(an) => setForm({ ...form, privatAn: an })} label="Auch privat genutzt" />
            <div className="min-w-0 flex-1">
              <div className="text-[15px] font-bold leading-snug">Auch privat genutzt</div>
              <div className="text-[13px] leading-snug text-ink/60">z. B. Handy oder Internet — nur der betriebliche Teil zählt.</div>
            </div>
          </div>
          {form.privatAn && (
            <div className="grid grid-cols-2 items-end gap-3">
              <label className="block">
                <span className="field-label">Privatanteil (%)</span>
                <input
                  className="input tabular-nums"
                  inputMode="decimal"
                  value={form.privatInput}
                  placeholder="z. B. 20"
                  onChange={(e) => setForm({ ...form, privatInput: e.target.value })}
                />
              </label>
              <p className="pb-2 text-[13px] tabular-nums leading-snug text-ink/70">
                {bp && betrag > 0
                  ? `betrieblich ${formatEuro(betrieblichCent(betrag, bp))} · privat ${formatEuro(privatCent(betrag, bp))}`
                  : 'Betrieblicher Teil folgt'}
              </p>
            </div>
          )}
        </div>

        <div className="grid grid-cols-1 gap-x-5 gap-y-2 sm:grid-cols-2">
          <label className="block">
            <span className="field-label">{isEdit ? 'Nächster Termin' : 'Erster Termin'}</span>
            <input type="date" className="input" value={form.naechste_am}
              onChange={(e) => setForm({ ...form, naechste_am: e.target.value })} />
          </label>
          <label className="block">
            <span className="field-label">Endet nach dem (optional)</span>
            <input type="date" className="input" value={form.endet_am} min={form.naechste_am}
              onChange={(e) => setForm({ ...form, endet_am: e.target.value })} />
          </label>
        </div>
        <label className="block">
          <span className="field-label">Notiz (optional)</span>
          <input className="input" value={form.notiz} placeholder="z. B. Vertragsnummer, Kündigungsfrist"
            onChange={(e) => setForm({ ...form, notiz: e.target.value })} />
        </label>

        <Hinweis className="text-xs">
          Ein Termin ist <strong>fällig</strong>, sobald sein Datum erreicht ist. Du buchst ihn mit einem Klick —
          oder ordnest die Abbuchung im Bank-Import zu. Tab bucht nie von selbst. Liegt der erste Termin in der
          Vergangenheit, holst du die verpassten Termine mit „Alle buchen" nach.
          {isEdit && ' Setzt du den nächsten Termin zurück, bleibt der Tag im Monat erhalten (der 31. fällt in kurzen Monaten auf den Monatsletzten).'}
        </Hinweis>

        <DialogFuss>
          <button type="button" className="btn-ghost" onClick={onClose}>
            Abbrechen
          </button>
          <button type="submit" className="btn-primary" disabled={busy}>
            Speichern
          </button>
        </DialogFuss>
      </form>
    </Modal>
  );
}
