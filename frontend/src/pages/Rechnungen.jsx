import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useOutletContext } from 'react-router-dom';
import toast from 'react-hot-toast';
import { api, apiError } from '../api/client.js';
import { useAuth } from '../auth/AuthContext.jsx';
import AboModal from '../components/AboModal.jsx';
import KontakteModal from '../components/KontakteModal.jsx';
import VorlagenModal from '../components/VorlagenModal.jsx';
import { TextbausteinWahl } from '../components/Vorlagen.jsx';
import BuchungModal from '../components/BuchungModal.jsx';
import { DialogFuss, PositionenEditor, SchalterZeile } from '../components/DialogParts.jsx';
import Dropdown from '../components/Dropdown.jsx';
import {
  IconBan,
  IconBell,
  IconBookIn,
  IconBookmark,
  IconButton,
  IconCheck,
  IconCircleCheck,
  IconFileText,
  IconPause,
  IconPencil,
  IconPlay,
  IconPlus,
  IconRepeat,
  IconSend,
  IconTrash,
  IconUsers,
  IconZap,
} from '../components/Icons.jsx';
import Modal from '../components/Modal.jsx';
import {
  Frist,
  Hinweis,
  KeinGewerbe,
  Leer,
  PageHeader,
  PUNKT,
  Row,
  SectionHead,
  Zustand,
} from '../components/PageParts.jsx';
import { dauer } from '../lib/fristWorte.js';
import RechnungenTabs from '../components/RechnungenTabs.jsx';
import { PageSpinner } from '../components/Spinner.jsx';
import { addDays, faelligkeit } from '../lib/fristen.js';
import { formatEuro, formatDateDE, parseEuroToCent, centToInput, todayISO } from '../lib/format.js';
import { INTERVALL_LABELS, naechsterTermin } from '../lib/intervall.js';
import { naechsteStufe, openMahnungPdf, STUFEN } from '../lib/mahnwesen.js';

// Status der Rechnung: Farbe des Kreises + Zustandswort (kein Chip).
const STATUS = {
  entwurf: { label: 'Entwurf', kind: 'out', ton: 'leise' },
  versendet: { label: 'Versendet', kind: 'warn', ton: 'warn' },
  bezahlt: { label: 'Bezahlt', kind: 'pos', ton: 'pos' },
  storniert: { label: 'Storniert', kind: 'neg', ton: 'neg' },
};
const ZAHLUNG_ART = {
  zahlung: 'Zahlung',
  skonto: 'Skonto',
  ausfall: 'Forderungsausfall',
};
const INTERVALL = {
  monatlich: 'monatlich',
  vierteljaehrlich: 'vierteljährlich',
  jaehrlich: 'jährlich',
};

// Warum keine USt auf der Rechnung steht — je Rechnung wählbar.
const STEUERHINWEIS_OPTIONS = [
  { value: 'ku19', label: 'Kleinunternehmer § 19 UStG (Standard)' },
  {
    value: 'vers4nr11',
    label: 'Steuerfrei § 4 Nr. 11 UStG (Versicherungsprovision)',
  },
];

function emptyRPos() {
  return { beschreibung: '', menge: '1', preisInput: '' };
}

async function openPdf(id) {
  try {
    const res = await api.get(`/api/rechnungen/${id}/pdf`, {
      responseType: 'blob',
    });
    const url = URL.createObjectURL(res.data);
    window.open(url, '_blank', 'noopener');
    setTimeout(() => URL.revokeObjectURL(url), 60000);
  } catch (e) {
    toast.error(apiError(e, 'PDF konnte nicht erstellt werden.'));
  }
}

// Ab 1280 px: Liste links, offene Rechnung rechts (Muster aus vrwb_flow). Darunter die gewohnten Zeilen.
const BREIT = '(min-width: 1280px)';
function useBreit() {
  const [breit, setBreit] = useState(() => typeof window !== 'undefined' && window.matchMedia(BREIT).matches);
  useEffect(() => {
    const mq = window.matchMedia(BREIT);
    const on = () => setBreit(mq.matches);
    on();
    mq.addEventListener('change', on);
    return () => mq.removeEventListener('change', on);
  }, []);
  return breit;
}

// Punkt vor dem Listeneintrag: versendet = offener Ring, überfällig = gefüllt (nie nur über Farbe unterscheiden).
const PUNKT_FARBE = {
  out: 'bg-ink/30',
  warn: 'border-2 border-[#b26a00]',
  late: 'bg-[#b26a00]',
  pos: 'bg-[#177245]',
  neg: 'bg-red-700',
};

function RechnungsListe({ items, zustandZeile, aktionen, verlauf, hauptaktion }) {
  const breit = useBreit();
  const [offenId, setOffenId] = useState(null);

  if (!breit) {
    return items.map((r) => (
      <Row
        key={r.id}
        kind={r.ueberfaellig_tage > 0 ? 'late' : STATUS[r.status].kind}
        icon={IconFileText}
        muted={r.status === 'storniert'}
        title={
          <>
            <span className="tabular-nums">{r.nummer}</span> · {r.empfaenger_name}
          </>
        }
        sub={zustandZeile(r)}
        amount={formatEuro(r.summe_cent)}
        amountIn={r.status !== 'storniert'}
        /* feste Breite ab sm: Beträge bleiben bündig, PDF/Senden sitzen immer am selben Platz */
        actionsClass="sm:w-[12.75rem]"
        actions={aktionen(r)}
      >
        {verlauf(r)}
      </Row>
    ));
  }

  const offen = items.find((r) => r.id === offenId) ?? items[0];
  const haupt = hauptaktion(offen);
  const HauptIcon = haupt.icon;
  // Ein Scrollbalken je Seite (Hub, Arbeitsflächen): die Liste scrollt mit der Seite, die offene Rechnung bleibt
  // stehen — aber nur, solange sie sicher auf den Schirm passt.
  const kurz =
    offen.positionen.length + offen.zahlungen.length + offen.mahnungen.length <= 8 && (offen.notiz || '').length < 400;
  return (
    <div className="grid grid-cols-[18rem_minmax(0,1fr)] items-start gap-x-8">
      <ul className="border-t border-ink/[0.08]" aria-label="Rechnungen">
        {items.map((r) => {
          const aktiv = r.id === offen.id;
          const ueber = r.ueberfaellig_tage > 0;
          return (
            <li key={r.id}>
              <button
                type="button"
                onClick={() => setOffenId(r.id)}
                aria-current={aktiv ? 'true' : undefined}
                className={`flex w-full items-center gap-2.5 border-b border-ink/[0.08] px-2.5 py-2 text-left outline-none focus-visible:ring-2 focus-visible:ring-royal/60 ${
                  aktiv ? 'bg-royal/[0.08]' : 'hover:bg-ink/[0.03]'
                } ${r.status === 'storniert' ? 'opacity-60' : ''}`}
              >
                <span
                  className={`h-2 w-2 shrink-0 rounded-full ${PUNKT_FARBE[ueber ? 'late' : STATUS[r.status].kind]}`}
                  aria-hidden="true"
                />
                <span className="min-w-0 flex-1">
                  <span
                    className={`block truncate text-sm leading-snug ${aktiv ? 'font-bold text-royal' : 'font-bold'}`}
                  >
                    {r.empfaenger_name}
                  </span>
                  <span className="block truncate text-xs leading-snug text-ink/60">
                    <span className="tabular-nums">{r.nummer}</span> ·{' '}
                    {ueber
                      ? 'überfällig'
                      : r.status === 'versendet' && r.bezahlt_cent > 0
                        ? 'Teilbezahlt'
                        : STATUS[r.status].label}
                  </span>
                </span>
                <span className="shrink-0 text-sm font-bold tabular-nums">{formatEuro(r.summe_cent)}</span>
              </button>
            </li>
          );
        })}
      </ul>

      <section
        aria-label={`Rechnung ${offen.nummer}`}
        className={`${kurz ? 'sticky top-4' : ''} ${offen.status === 'storniert' ? 'opacity-70' : ''}`}
      >
        <div className="flex items-start gap-4">
          <div className="min-w-0 flex-1">
            <div className="eyebrow tabular-nums">Rechnung {offen.nummer}</div>
            <h2 className="mt-0.5 text-[22px] font-black leading-tight tracking-tight">{offen.empfaenger_name}</h2>
          </div>
          <div className="shrink-0 text-right text-[22px] font-black tabular-nums tracking-tight text-royal">
            {formatEuro(offen.summe_cent)}
          </div>
        </div>
        <div className="mt-1 flex flex-wrap items-center gap-x-1.5 text-[13px] leading-snug text-ink/60">
          {zustandZeile(offen)}
        </div>

        <div className="mt-4 flex items-center gap-1 border-b border-ink/[0.08] pb-4">
          <button type="button" className="btn-primary" onClick={haupt.onClick}>
            <HauptIcon className="mr-1.5 h-4 w-4" /> {haupt.label}
          </button>
          <div className="ml-auto flex items-center gap-0.5 text-ink/60">{aktionen(offen, haupt.key)}</div>
        </div>

        <div className="eyebrow mt-4">Positionen</div>
        <div className="mt-1">
          {offen.positionen.map((p, i) => (
            <div key={i} className="flex items-baseline gap-3 border-b border-ink/[0.08] py-2 text-sm">
              <span className="min-w-0 flex-1 whitespace-pre-line">{p.beschreibung}</span>
              <span className="shrink-0 tabular-nums text-ink/60">
                {String(p.menge).replace('.', ',')} × {formatEuro(p.einzelpreis_cent)}
              </span>
              <span className="w-24 shrink-0 text-right font-bold tabular-nums">
                {formatEuro(Math.round(p.menge * p.einzelpreis_cent))}
              </span>
            </div>
          ))}
        </div>

        {(offen.leistungsdatum || offen.bestellnummer || offen.empfaenger_email) && (
          <dl className="mt-4 grid grid-cols-[auto_minmax(0,1fr)] gap-x-4 gap-y-1 text-sm">
            {offen.leistungsdatum && (
              <>
                <dt className="text-ink/60">Leistung</dt>
                <dd>{offen.leistungsdatum}</dd>
              </>
            )}
            {offen.bestellnummer && (
              <>
                <dt className="text-ink/60">Bestellnummer</dt>
                <dd>{offen.bestellnummer}</dd>
              </>
            )}
            {offen.empfaenger_email && (
              <>
                <dt className="text-ink/60">E-Mail</dt>
                <dd className="truncate">{offen.empfaenger_email}</dd>
              </>
            )}
          </dl>
        )}
        {offen.notiz && (
          <>
            <div className="eyebrow mt-4">Notiz</div>
            <p className="mt-1 whitespace-pre-line text-sm text-ink/80">{offen.notiz}</p>
          </>
        )}

        {(offen.zahlungen.length > 0 || offen.mahnungen.length > 0) && (
          <>
            <div className="eyebrow mt-4">Verlauf</div>
            {verlauf(offen)}
          </>
        )}
      </section>
    </div>
  );
}

// tab: 'alle' (Rechnungsliste) | 'wiederkehrend' (Abos); der Mahnwesen-Reiter ist eine eigene Seite.
export default function Rechnungen({ tab = 'alle' }) {
  const { gewerbeId, jahr, gewerbe, reloadBadges } = useOutletContext();
  const { user } = useAuth();
  const navigate = useNavigate();
  const [items, setItems] = useState([]);
  const [ueberfaellig, setUeberfaellig] = useState(0);
  const [sendenMahnung, setSendenMahnung] = useState(null); // { rechnung, mahnung }
  const [abos, setAbos] = useState([]);
  const [kategorien, setKategorien] = useState([]);
  const [mail, setMail] = useState(null); // { email, konfiguriert }
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(null);
  const [senden, setSenden] = useState(null); // rechnung
  const [einnahme, setEinnahme] = useState(null); // { rechnung, zahlung } -> BuchungModal
  const [zahlungFuer, setZahlungFuer] = useState(null); // rechnung -> ZahlungModal
  const [aboModal, setAboModal] = useState(null); // { abo? , prefill? }
  const [kontakte, setKontakte] = useState([]);
  const [kontakteModal, setKontakteModal] = useState(false);
  const [vorlagenModal, setVorlagenModal] = useState(false);

  const gewerbeRow = gewerbe.find((g) => String(g.id) === String(gewerbeId));

  async function load() {
    if (!gewerbeId) {
      setLoading(false);
      return;
    }
    setLoading(true);
    try {
      const [r, kat, m, a, ko, ue] = await Promise.all([
        api.get('/api/rechnungen', { params: { gewerbe_id: gewerbeId, jahr } }),
        api.get('/api/kategorien', { params: { jahr } }),
        api.get('/api/einstellungen/mail'),
        api.get('/api/rechnungsabos', { params: { gewerbe_id: gewerbeId } }),
        api.get('/api/kontakte', { params: { gewerbe_id: gewerbeId } }),
        api.get('/api/mahnwesen/ueberfaellig', {
          params: { gewerbe_id: gewerbeId },
        }),
      ]);
      setItems(r.data);
      setUeberfaellig(ue.data.items.length);
      setKategorien(kat.data);
      setMail(m.data);
      setAbos(a.data);
      setKontakte(ko.data);
    } catch (e) {
      toast.error(apiError(e));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, [gewerbeId, jahr]); // eslint-disable-line react-hooks/exhaustive-deps

  async function setStatus(r, status) {
    try {
      await api.post(`/api/rechnungen/${r.id}/status`, { status });
      toast.success(status === 'bezahlt' ? 'Als bezahlt markiert.' : 'Status geändert.');
      await load();
      reloadBadges?.();
    } catch (e) {
      toast.error(apiError(e));
    }
  }

  async function remove(r) {
    if (!window.confirm(`Entwurf ${r.nummer} wirklich löschen?`)) return;
    try {
      await api.delete(`/api/rechnungen/${r.id}`);
      toast.success('Gelöscht.');
      await load();
    } catch (e) {
      toast.error(apiError(e));
    }
  }

  async function removeZahlung(r, z) {
    if (
      !window.confirm(`${ZAHLUNG_ART[z.art]} vom ${formatDateDE(z.datum)} über ${formatEuro(z.betrag_cent)} löschen?`)
    )
      return;
    try {
      await api.delete(`/api/rechnungen/${r.id}/zahlungen/${z.id}`);
      toast.success('Gelöscht.');
      await load();
      reloadBadges?.();
    } catch (e) {
      toast.error(apiError(e));
    }
  }

  async function removeMahnung(m) {
    if (!window.confirm(`${STUFEN[m.stufe]} vom ${formatDateDE(m.datum)} löschen?`)) return;
    try {
      await api.delete(`/api/mahnwesen/${m.id}`);
      toast.success('Mahnung gelöscht.');
      await load();
    } catch (e) {
      toast.error(apiError(e));
    }
  }

  // ── Abos (wiederkehrende Rechnungen) ──────────────────────────────────────
  async function runAbo(a) {
    try {
      const res = await api.post(`/api/rechnungsabos/${a.id}/run`);
      const d = res.data;
      toast.success(
        d.versendet
          ? `Rechnung ${d.nummer} erstellt und versendet.`
          : `Rechnung ${d.nummer} als Entwurf erstellt.${d.fehler ? ` (${d.fehler})` : ''}`,
        { duration: 7000 },
      );
      await load();
    } catch (e) {
      toast.error(apiError(e));
    }
  }

  async function toggleAbo(a) {
    try {
      await api.patch(`/api/rechnungsabos/${a.id}`, { aktiv: !a.aktiv });
      await load();
    } catch (e) {
      toast.error(apiError(e));
    }
  }

  async function removeAbo(a) {
    if (!window.confirm(`Abo für „${a.empfaenger_name}" löschen? Bestehende Rechnungen bleiben.`)) return;
    try {
      await api.delete(`/api/rechnungsabos/${a.id}`);
      await load();
    } catch (e) {
      toast.error(apiError(e));
    }
  }

  const einnahmeKat = kategorien.find((k) => k.key === 'einnahme_ku');
  const courtageKat = kategorien.find((k) => k.key === 'einnahme_steuerfrei');
  // §4-Nr.11-Rechnungen (Courtage) landen als Einnahme in Zeile 16, sonst Zeile 12.
  const einnahmeKatFuer = (r) => (r.steuerhinweis === 'vers4nr11' && courtageKat) || einnahmeKat;

  function bearbeiten(r) {
    setEditing({
      id: r.id,
      datum: r.datum,
      leistungsdatum: r.leistungsdatum || '',
      empfaenger_name: r.empfaenger_name,
      empfaenger_anschrift: r.empfaenger_anschrift || '',
      empfaenger_email: r.empfaenger_email || '',
      notiz: r.notiz || '',
      bestellnummer: r.bestellnummer || '',
      steuerhinweis: r.steuerhinweis || 'ku19',
      zahlungsziel_tage: r.zahlungsziel_tage,
      skonto_prozent: r.skonto_prozent,
      skonto_tage: r.skonto_tage,
      positionen: r.positionen.map((p) => ({
        beschreibung: p.beschreibung,
        menge: String(p.menge).replace('.', ','),
        preisInput: centToInput(p.einzelpreis_cent),
      })),
    });
  }

  // Die eine Hauptaktion der offenen Rechnung (breite Ansicht); der Rest bleibt Icon.
  function hauptaktion(r) {
    if (r.status === 'storniert' || r.status === 'bezahlt')
      return {
        key: 'pdf',
        label: 'PDF ansehen',
        icon: IconFileText,
        onClick: () => openPdf(r.id),
      };
    if (r.ueberfaellig_tage > 0)
      return {
        key: 'mahnen',
        label: `${STUFEN[naechsteStufe(r.mahnungen[0])]} erstellen`,
        icon: IconBell,
        onClick: () => navigate(`/rechnungen/mahnwesen/${r.id}`),
      };
    if (r.status === 'versendet')
      return {
        key: 'zahlung',
        label: 'Zahlung erfassen',
        icon: IconCircleCheck,
        onClick: () => setZahlungFuer(r),
      };
    if (mail?.konfiguriert)
      return {
        key: 'senden',
        label: 'Per E-Mail senden',
        icon: IconSend,
        onClick: () => setSenden(r),
      };
    return {
      key: 'bearbeiten',
      label: 'Bearbeiten',
      icon: IconPencil,
      onClick: () => bearbeiten(r),
    };
  }

  // Bausteine einer Rechnung — in der Zeile (schmal) und in der offenen Rechnung rechts (breit) dieselben.
  function zustandZeile(r) {
    const st = STATUS[r.status];
    const istUeberfaellig = r.ueberfaellig_tage > 0;
    return (
      <>
        {istUeberfaellig ? (
          <Zustand ton="late">{dauer(r.ueberfaellig_tage)} überfällig</Zustand>
        ) : (
          <Zustand ton={st.ton}>{r.status === 'versendet' && r.bezahlt_cent > 0 ? 'Teilbezahlt' : st.label}</Zustand>
        )}
        {PUNKT}
        <span className="tabular-nums">{formatDateDE(r.datum)}</span>
        {r.faellig_am && !istUeberfaellig && (r.status === 'entwurf' || r.status === 'versendet') && (
          <>
            {PUNKT}
            <Frist datum={r.faellig_am} />
          </>
        )}
        {r.versendet_am && (
          <>
            {PUNKT}
            <span>versendet {formatDateDE(r.versendet_am)}</span>
          </>
        )}
        {r.bezahlt_am && (
          <>
            {PUNKT}
            <span>bezahlt {formatDateDE(r.bezahlt_am)}</span>
          </>
        )}
        {r.steuerhinweis === 'vers4nr11' && (
          <>
            {PUNKT}
            <span>§4 Nr. 11</span>
          </>
        )}
        {r.status === 'versendet' && r.bezahlt_cent > 0 && (
          <>
            {PUNKT}
            <span className="tabular-nums">
              bezahlt {formatEuro(r.bezahlt_cent)}, offen {formatEuro(r.offen_cent)}
            </span>
          </>
        )}
        {r.bezahlt_cent > 0 && r.ungebucht_cent === 0 && r.gebucht_cent > 0 && (
          <>
            {PUNKT}
            <Zustand ton="royal" icon={IconCheck}>
              Gebucht
            </Zustand>
          </>
        )}
      </>
    );
  }

  function aktionen(r, ohne) {
    const istUeberfaellig = r.ueberfaellig_tage > 0;
    return (
      <>
        {ohne !== 'pdf' && <IconButton icon={IconFileText} label="PDF ansehen" onClick={() => openPdf(r.id)} />}
        {r.status !== 'storniert' && ohne !== 'senden' && (
          <IconButton
            icon={IconSend}
            label={
              !mail?.konfiguriert
                ? 'Erst E-Mail-Versand im Profilmenü einrichten'
                : r.status === 'versendet' || r.versendet_am
                  ? 'Erneut senden'
                  : 'Per E-Mail senden'
            }
            onClick={() => setSenden(r)}
            disabled={!mail?.konfiguriert}
          />
        )}
        {r.status === 'entwurf' && ohne !== 'bearbeiten' && (
          <IconButton icon={IconPencil} label="Bearbeiten" onClick={() => bearbeiten(r)} />
        )}
        {istUeberfaellig && ohne !== 'mahnen' && (
          <IconButton
            icon={IconBell}
            variant="primary"
            label={`${STUFEN[naechsteStufe(r.mahnungen[0])]} erstellen`}
            onClick={() => navigate(`/rechnungen/mahnwesen/${r.id}`)}
          />
        )}
        {r.status === 'entwurf' && (
          <IconButton icon={IconCircleCheck} label="Als bezahlt markieren" onClick={() => setStatus(r, 'bezahlt')} />
        )}
        {r.status === 'versendet' && ohne !== 'zahlung' && (
          <IconButton icon={IconCircleCheck} label="Zahlung erfassen…" onClick={() => setZahlungFuer(r)} />
        )}
        {r.status !== 'storniert' && (
          <IconButton
            icon={IconRepeat}
            label="Als wiederkehrendes Abo anlegen…"
            onClick={() => setAboModal({ prefill: r })}
          />
        )}
        {r.status !== 'entwurf' && r.status !== 'storniert' && (
          <IconButton icon={IconBan} variant="danger" label="Stornieren" onClick={() => setStatus(r, 'storniert')} />
        )}
        {r.status === 'entwurf' && (
          <IconButton icon={IconTrash} variant="danger" label="Löschen" onClick={() => remove(r)} />
        )}
      </>
    );
  }

  function verlauf(r) {
    return (
      <>
        {r.zahlungen.length > 0 && (
          <div className="mt-1.5 space-y-0.5">
            {r.zahlungen.map((z) => (
              <div key={z.id} className="flex items-center gap-1 text-[13px] text-ink/70">
                <span className="min-w-0 flex-1">
                  {ZAHLUNG_ART[z.art]} {formatDateDE(z.datum)}
                  <span className="mx-1.5 text-ink/45">·</span>
                  <span className="tabular-nums">{formatEuro(z.betrag_cent)}</span>
                  {z.art === 'zahlung' && (
                    <>
                      <span className="mx-1.5 text-ink/45">·</span>
                      {z.buchung_id ? 'als Einnahme gebucht' : 'noch nicht gebucht'}
                    </>
                  )}
                  {z.art !== 'zahlung' && <span className="text-ink/60"> ausgebucht</span>}
                </span>
                {z.art === 'zahlung' && !z.buchung_id && einnahmeKat && (
                  <IconButton
                    icon={IconBookIn}
                    variant="primary"
                    label="Als Einnahme buchen"
                    onClick={() => setEinnahme({ rechnung: r, zahlung: z })}
                  />
                )}
                {!z.buchung_id && (
                  <IconButton icon={IconTrash} variant="danger" label="Löschen" onClick={() => removeZahlung(r, z)} />
                )}
              </div>
            ))}
          </div>
        )}
        {r.mahnungen.length > 0 && (
          <div className="mt-1.5 space-y-0.5">
            {r.mahnungen.map((m) => (
              <div key={m.id} className="flex items-center gap-1 text-[13px] text-ink/70">
                <span className="min-w-0 flex-1">
                  {STUFEN[m.stufe]} vom {formatDateDE(m.datum)}
                  <span className="mx-1.5 text-ink/45">·</span>
                  Frist {formatDateDE(m.frist_am)}
                  <span className="mx-1.5 text-ink/45">·</span>
                  <span className="tabular-nums">{formatEuro(m.gesamt_cent)}</span>
                  {m.gesendet_am && (
                    <>
                      <span className="mx-1.5 text-ink/45">·</span>
                      versendet {formatDateDE(m.gesendet_am)}
                    </>
                  )}
                </span>
                <IconButton icon={IconFileText} label="Mahnung ansehen" onClick={() => openMahnungPdf(m.id)} />
                <IconButton
                  icon={IconSend}
                  label={
                    mail?.konfiguriert ? 'Mahnung per E-Mail senden' : 'Erst E-Mail-Versand im Profilmenü einrichten'
                  }
                  onClick={() => setSendenMahnung({ rechnung: r, mahnung: m })}
                  disabled={!mail?.konfiguriert}
                />
                {!m.gesendet_am && (
                  <IconButton
                    icon={IconTrash}
                    variant="danger"
                    label="Mahnung löschen"
                    onClick={() => removeMahnung(m)}
                  />
                )}
              </div>
            ))}
          </div>
        )}
      </>
    );
  }

  if (!gewerbeId) return <KeinGewerbe />;
  if (loading) return <PageSpinner />;

  return (
    <div>
      <PageHeader
        title="Rechnungen"
        accent={jahr}
        sub={`Fortlaufende Nummern, §19-Hinweis und Fälligkeit automatisch drauf · Versand von ${mail?.email || '…'}`}
      >
        <IconButton
          icon={IconUsers}
          label={`Kontakte${kontakte.length > 0 ? ` (${kontakte.length})` : ''}`}
          onClick={() => setKontakteModal(true)}
        />
        <IconButton icon={IconBookmark} label="Artikel & Texte" onClick={() => setVorlagenModal(true)} />
        <button className="btn-primary" onClick={() => setEditing({ positionen: [emptyRPos()] })}>
          <IconPlus className="mr-1 h-4 w-4" /> Rechnung
        </button>
      </PageHeader>
      <RechnungenTabs ueberfaellig={ueberfaellig} />

      {(!gewerbeRow?.anschrift || (mail && !mail.konfiguriert)) && (
        <div className="mt-5 space-y-3">
          {!gewerbeRow?.anschrift && (
            <Hinweis ton="warn" titel="Absender fehlt">
              Hinterlege unter{' '}
              <Link to="/gewerbe" className="font-bold underline">
                Gewerbe
              </Link>{' '}
              deine Anschrift (und IBAN) — Pflichtangaben auf jeder Rechnung.
            </Hinweis>
          )}
          {mail && !mail.konfiguriert && (
            <Hinweis>
              Zum Versenden aus Tab einmalig den <strong>E-Mail-Versand einrichten</strong> (Profil unten links →
              Einstellungen) — App-Passwort deines Google-Kontos, Versand dann von {mail.email}. PDF-Download geht auch
              ohne.
            </Hinweis>
          )}
        </div>
      )}

      {tab === 'wiederkehrend' && abos.length === 0 && (
        <Leer>
          Noch keine wiederkehrenden Rechnungen. Beim Anlegen einer Rechnung den Schalter „Rechnung wiederholt sich“
          einschalten, oder an einer bestehenden Rechnung „Als wiederkehrendes Abo anlegen“ wählen.
        </Leer>
      )}
      {tab === 'wiederkehrend' && abos.length > 0 && (
        <>
          <SectionHead label="Wiederkehrende Rechnungen" count={abos.length} />
          {abos.map((a) => (
            <Row
              key={a.id}
              icon={IconRepeat}
              muted={!a.aktiv}
              title={a.empfaenger_name}
              sub={
                <>
                  <span>{INTERVALL[a.intervall]}</span>
                  {PUNKT}
                  <span>nächste am {formatDateDE(a.naechste_am)}</span>
                  {PUNKT}
                  {!a.aktiv ? (
                    <Zustand>Pausiert</Zustand>
                  ) : a.auto_senden ? (
                    <Zustand ton="royal">Auto-Versand</Zustand>
                  ) : (
                    <span>Entwurf</span>
                  )}
                </>
              }
              amount={formatEuro(a.summe_cent)}
              actions={
                <>
                  <IconButton icon={IconZap} label="Jetzt ausführen" onClick={() => runAbo(a)} />
                  <IconButton icon={IconPencil} label="Bearbeiten" onClick={() => setAboModal({ abo: a })} />
                  <IconButton
                    icon={a.aktiv ? IconPause : IconPlay}
                    label={a.aktiv ? 'Pausieren' : 'Fortsetzen'}
                    onClick={() => toggleAbo(a)}
                  />
                  <IconButton icon={IconTrash} variant="danger" label="Löschen" onClick={() => removeAbo(a)} />
                </>
              }
            >
              {Boolean(a.auto_senden) && !a.absender_konfiguriert && (
                <Hinweis ton="warn" className="mt-1.5 !py-2 text-xs">
                  Absender {a.absender_email} hat kein App-Passwort hinterlegt — Rechnungen bleiben als Entwurf liegen.
                </Hinweis>
              )}
            </Row>
          ))}
        </>
      )}

      {tab === 'alle' && (
        <>
          <SectionHead label={`Rechnungen ${jahr}`} count={items.length} />
          {items.length === 0 ? (
            <Leer>
              Noch keine Rechnungen für {jahr}. Tipp: Nach der ersten Rechnung kannst du sie mit „Wiederholen…" als
              monatliches Abo anlegen.
            </Leer>
          ) : (
            <RechnungsListe
              items={items}
              zustandZeile={zustandZeile}
              aktionen={aktionen}
              verlauf={verlauf}
              hauptaktion={hauptaktion}
            />
          )}
        </>
      )}

      {editing && (
        <RechnungModal
          editing={editing}
          setEditing={setEditing}
          gewerbeId={gewerbeId}
          jahr={jahr}
          kontakte={kontakte}
          standardZiel={gewerbeRow?.zahlungsziel_tage ?? 14}
          mailKonfiguriert={Boolean(mail?.konfiguriert)}
          onSaved={load}
        />
      )}

      {vorlagenModal && <VorlagenModal gewerbeId={gewerbeId} onClose={() => setVorlagenModal(false)} />}
      {kontakteModal && (
        <KontakteModal gewerbeId={gewerbeId} onClose={() => setKontakteModal(false)} onChanged={load} />
      )}

      {senden && <SendenModal rechnung={senden} user={user} onClose={() => setSenden(null)} onSent={load} />}
      {sendenMahnung && (
        <SendenModal
          rechnung={sendenMahnung.rechnung}
          mahnung={sendenMahnung.mahnung}
          user={user}
          onClose={() => setSendenMahnung(null)}
          onSent={load}
        />
      )}

      {aboModal && (
        <AboModal
          abo={aboModal.abo}
          prefill={aboModal.prefill}
          gewerbeId={gewerbeId}
          kontakte={kontakte}
          mailKonfiguriert={Boolean(mail?.konfiguriert)}
          onClose={() => setAboModal(null)}
          onSaved={load}
        />
      )}

      {zahlungFuer && (
        <ZahlungModal
          rechnung={zahlungFuer}
          onClose={() => setZahlungFuer(null)}
          onSaved={async () => {
            await load();
            reloadBadges?.();
          }}
        />
      )}

      {einnahme && (
        <BuchungModal
          gewerbeId={gewerbeId}
          jahr={jahr}
          kategorien={kategorien}
          presetKategorieId={einnahmeKatFuer(einnahme.rechnung)?.id}
          presetBetragCent={einnahme.zahlung.betrag_cent}
          presetBeschreibung={`Rechnung ${einnahme.rechnung.nummer} – ${einnahme.rechnung.empfaenger_name}`}
          presetDatum={einnahme.zahlung.datum}
          presetRichtung="einnahme"
          rechnungId={einnahme.rechnung.id}
          zahlungId={einnahme.zahlung.id}
          onClose={() => setEinnahme(null)}
          onSaved={async () => {
            await load();
            reloadBadges?.();
          }}
        />
      )}
    </div>
  );
}

function RechnungModal({
  editing,
  setEditing,
  gewerbeId,
  jahr,
  kontakte = [],
  standardZiel = 14,
  mailKonfiguriert,
  onSaved,
}) {
  const [busy, setBusy] = useState(false);
  const isEdit = Boolean(editing.id);
  const [form, setForm] = useState(() => ({
    datum: editing.datum || todayISO(),
    leistungsdatum: editing.leistungsdatum || '',
    empfaenger_name: editing.empfaenger_name || '',
    empfaenger_anschrift: editing.empfaenger_anschrift || '',
    empfaenger_email: editing.empfaenger_email || '',
    notiz: editing.notiz || '',
    bestellnummer: editing.bestellnummer || '',
    steuerhinweis: editing.steuerhinweis || 'ku19',
    zahlungsziel: String(editing.zahlungsziel_tage ?? standardZiel),
    skontoProzent: editing.skonto_prozent ? String(editing.skonto_prozent).replace('.', ',') : '',
    skontoTage: editing.skonto_tage ? String(editing.skonto_tage) : '',
    positionen: editing.positionen?.length ? editing.positionen : [emptyRPos()],
    wiederholen: false,
    intervall: 'monatlich',
    auto_senden: false,
  }));

  const total = useMemo(
    () =>
      form.positionen.reduce((s, p) => {
        const preis = parseEuroToCent(p.preisInput);
        const menge = Number(String(p.menge).replace(',', '.'));
        return s + (preis > 0 && menge > 0 ? Math.round(menge * preis) : 0);
      }, 0),
    [form.positionen],
  );

  // Zahlungsziel in Tagen; Fälligkeit = Rechnungsdatum + Ziel, auf einen Werktag verschoben (§ 193 BGB).
  const ziel = Number(form.zahlungsziel);
  const zielGueltig = form.zahlungsziel.trim() !== '' && Number.isInteger(ziel) && ziel >= 0 && ziel <= 120;
  const faelligAm = zielGueltig && form.datum ? faelligkeit(form.datum, ziel) : null;
  // Skonto (optional): Prozent + Frist in Tagen, beides oder nichts; Frist höchstens das Zahlungsziel
  const skontoP = form.skontoProzent.trim() ? Number(form.skontoProzent.replace(',', '.')) : null;
  const skontoT = form.skontoTage.trim() ? Number(form.skontoTage) : null;
  const skontoLeer = skontoP === null && skontoT === null;
  const skontoFehler = skontoLeer
    ? null
    : skontoP === null || skontoT === null
      ? 'Prozent und Tage angeben'
      : !(skontoP > 0 && skontoP <= 10) || !Number.isInteger(skontoT) || skontoT < 1
        ? 'Prozent 0,1–10, Tage ab 1'
        : zielGueltig && skontoT > ziel
          ? 'Frist länger als das Zahlungsziel'
          : null;
  const skontoBetrag = (() => {
    const summe = form.positionen.reduce((s, p) => {
      const preis = parseEuroToCent(p.preisInput);
      const menge = Number(String(p.menge).replace(',', '.'));
      return s + (preis > 0 && menge > 0 ? Math.round(menge * preis) : 0);
    }, 0);
    return skontoP && !skontoFehler ? Math.floor((summe * Math.round(skontoP * 100) + 5000) / 10000) : 0;
  })();

  // Gemeinsamer Payload für Speichern + Vorschau; null = Validierungsfehler (getoastet).
  function baueBody() {
    if (!form.empfaenger_name.trim()) {
      toast.error('Empfänger ist Pflicht.');
      return null;
    }
    if (!zielGueltig) {
      toast.error('Zahlungsziel: ganze Tage von 0 bis 120.');
      return null;
    }
    if (skontoFehler) {
      toast.error(`Skonto: ${skontoFehler}.`);
      return null;
    }
    const payloadPos = [];
    for (const p of form.positionen) {
      const preis = parseEuroToCent(p.preisInput);
      const menge = Number(String(p.menge).replace(',', '.'));
      if (!p.beschreibung.trim()) {
        toast.error('Jede Position braucht eine Beschreibung.');
        return null;
      }
      if (!preis || preis <= 0) {
        toast.error(`Bitte gültigen Preis für „${p.beschreibung}" angeben.`);
        return null;
      }
      if (!Number.isFinite(menge) || menge <= 0) {
        toast.error('Bitte gültige Menge angeben.');
        return null;
      }
      payloadPos.push({
        beschreibung: p.beschreibung.trim(),
        menge,
        einzelpreis_cent: preis,
      });
    }
    return {
      datum: form.datum,
      leistungsdatum: form.leistungsdatum.trim() || null,
      empfaenger_name: form.empfaenger_name.trim(),
      empfaenger_anschrift: form.empfaenger_anschrift.trim() || null,
      empfaenger_email: form.empfaenger_email.trim() || null,
      notiz: form.notiz.trim() || null,
      bestellnummer: form.bestellnummer.trim(),
      steuerhinweis: form.steuerhinweis,
      zahlungsziel_tage: ziel,
      skonto_prozent: skontoP,
      skonto_tage: skontoT,
      positionen: payloadPos,
    };
  }

  async function vorschau() {
    const body = baueBody();
    if (!body) return;
    setBusy(true);
    try {
      const res = await api.post(
        '/api/rechnungen/vorschau',
        { gewerbe_id: Number(gewerbeId), ...body },
        { responseType: 'blob' },
      );
      const url = URL.createObjectURL(res.data);
      window.open(url, '_blank', 'noopener');
      setTimeout(() => URL.revokeObjectURL(url), 60000);
    } catch (err) {
      toast.error(apiError(err, 'Vorschau konnte nicht erstellt werden.'));
    } finally {
      setBusy(false);
    }
  }

  async function save(e) {
    e.preventDefault();
    const body = baueBody();
    if (!body) return;
    if (!isEdit && form.wiederholen && form.auto_senden && !body.empfaenger_email)
      return toast.error('Auto-Versand braucht eine Empfänger-E-Mail.');
    setBusy(true);
    try {
      if (isEdit) {
        // Beim Ändern bedeutet null „unverändert“ — leere Texte gehen als "" raus, damit sie sich löschen lassen.
        await api.patch(`/api/rechnungen/${editing.id}`, {
          ...body,
          notiz: form.notiz.trim(),
        });
        toast.success('Gespeichert.');
      } else {
        const res = await api.post('/api/rechnungen', {
          gewerbe_id: Number(gewerbeId),
          ...body,
        });
        if (form.wiederholen) {
          // Diese Rechnung ist die erste — das Abo übernimmt ab der nächsten Periode.
          const start = naechsterTermin(body.datum, form.intervall);
          try {
            await api.post('/api/rechnungsabos', {
              gewerbe_id: Number(gewerbeId),
              empfaenger_name: body.empfaenger_name,
              empfaenger_anschrift: body.empfaenger_anschrift,
              empfaenger_email: body.empfaenger_email,
              notiz: body.notiz,
              steuerhinweis: body.steuerhinweis,
              intervall: form.intervall,
              naechste_am: start,
              auto_senden: form.auto_senden,
              positionen: body.positionen,
            });
            toast.success(
              `Rechnung ${res.data.nummer} angelegt — wiederholt sich ${INTERVALL_LABELS[form.intervall]}, nächste am ${formatDateDE(start)}.`,
              { duration: 7000 },
            );
          } catch (aboErr) {
            toast.error(
              `Rechnung ${res.data.nummer} angelegt, aber das Abo konnte nicht erstellt werden: ${apiError(aboErr)}`,
              { duration: 10000 },
            );
          }
        } else {
          toast.success(`Rechnung ${res.data.nummer} angelegt.`);
        }
      }
      setEditing(null);
      await onSaved();
    } catch (err) {
      toast.error(apiError(err));
    } finally {
      setBusy(false);
    }
  }

  const jahrMismatch = form.datum && String(form.datum).slice(0, 4) !== String(jahr);

  return (
    <Modal
      title={isEdit ? 'Rechnung bearbeiten' : 'Neue Rechnung'}
      onClose={() => setEditing(null)}
      maxWidth="max-w-2xl"
    >
      <form onSubmit={save} className="space-y-4">
        {kontakte.length > 0 && (
          <div className="block">
            <span className="field-label">Aus Kontakten übernehmen</span>
            <Dropdown
              value=""
              placeholder="Kontakt wählen…"
              searchable
              options={kontakte.map((k) => ({
                value: String(k.id),
                label: k.name,
              }))}
              onChange={(v) => {
                const k = kontakte.find((x) => String(x.id) === String(v));
                if (k)
                  setForm((f) => ({
                    ...f,
                    empfaenger_name: k.name,
                    empfaenger_anschrift: k.anschrift || '',
                    empfaenger_email: k.email || '',
                  }));
              }}
            />
          </div>
        )}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-5 gap-y-2">
          <label className="block">
            <span className="field-label">Empfänger (Name/Firma)</span>
            <input
              className="input"
              value={form.empfaenger_name}
              autoFocus
              onChange={(e) => setForm({ ...form, empfaenger_name: e.target.value })}
            />
          </label>
          <label className="block">
            <span className="field-label">E-Mail (für den Versand)</span>
            <input
              className="input"
              value={form.empfaenger_email}
              onChange={(e) => setForm({ ...form, empfaenger_email: e.target.value })}
              placeholder="kunde@firma.de"
            />
          </label>
        </div>
        <label className="block">
          <span className="field-label">Anschrift Empfänger</span>
          <textarea
            className="input min-h-[64px]"
            value={form.empfaenger_anschrift}
            onChange={(e) => setForm({ ...form, empfaenger_anschrift: e.target.value })}
            placeholder={'Musterstraße 1\n20095 Hamburg'}
          />
        </label>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-x-5 gap-y-2">
          <label className="block">
            <span className="field-label">Rechnungsdatum</span>
            <input
              type="date"
              className="input"
              value={form.datum}
              onChange={(e) => setForm({ ...form, datum: e.target.value })}
              disabled={isEdit}
            />
          </label>
          <label className="block">
            <span className="field-label">Leistungsdatum/-zeitraum (optional)</span>
            <input
              className="input"
              value={form.leistungsdatum}
              onChange={(e) => setForm({ ...form, leistungsdatum: e.target.value })}
              placeholder="leer = Rechnungsdatum"
            />
          </label>
          <label className="block">
            <span className="field-label">Zahlungsziel in Tagen</span>
            <input
              className="input"
              inputMode="numeric"
              value={form.zahlungsziel}
              onChange={(e) => setForm({ ...form, zahlungsziel: e.target.value })}
              aria-invalid={!zielGueltig}
            />
            <span className="mt-1 block text-xs text-ink/60">
              {faelligAm ? `fällig ${formatDateDE(faelligAm)}` : 'ganze Tage von 0 bis 120'}
            </span>
          </label>
        </div>
        <div className="grid grid-cols-2 items-start gap-x-5 gap-y-2 sm:grid-cols-3">
          <label className="block">
            <span className="field-label">Skonto in % (optional)</span>
            <input
              className="input"
              inputMode="decimal"
              placeholder="z. B. 2"
              value={form.skontoProzent}
              onChange={(e) => setForm({ ...form, skontoProzent: e.target.value })}
              aria-invalid={Boolean(skontoFehler)}
            />
          </label>
          <label className="block">
            <span className="field-label">… bei Zahlung binnen (Tage)</span>
            <input
              className="input"
              inputMode="numeric"
              placeholder="z. B. 10"
              value={form.skontoTage}
              onChange={(e) => setForm({ ...form, skontoTage: e.target.value })}
              aria-invalid={Boolean(skontoFehler)}
            />
          </label>
          <p className="col-span-2 text-xs text-ink/60 sm:col-span-1 sm:pt-5">
            {skontoFehler
              ? skontoFehler
              : skontoLeer
                ? 'Kein Skonto.'
                : `bis ${formatDateDE(addDays(form.datum, skontoT))}: ${formatEuro(skontoBetrag)} Abzug`}
          </p>
        </div>
        {jahrMismatch && !isEdit && (
          <Hinweis ton="warn" className="!py-2 text-xs">
            Das Datum liegt nicht im gewählten Jahr {jahr} — die Rechnung bekommt eine Nummer des Jahres{' '}
            {String(form.datum).slice(0, 4)} und erscheint dort.
          </Hinweis>
        )}

        <PositionenEditor
          positionen={form.positionen}
          onChange={(positionen) => setForm((f) => ({ ...f, positionen }))}
          summeCent={total}
          platzhalter="Leistung, z. B. Beratung März 2026"
          gewerbeId={gewerbeId}
        />

        <div className="block">
          <span className="field-label">Steuer-Hinweis (warum keine USt)</span>
          <Dropdown
            value={form.steuerhinweis}
            onChange={(v) => setForm({ ...form, steuerhinweis: String(v) })}
            options={STEUERHINWEIS_OPTIONS}
          />
        </div>

        <label className="block sm:max-w-xs">
          <span className="field-label">Ihre Bestellnummer (optional)</span>
          <input
            className="input"
            value={form.bestellnummer}
            maxLength={80}
            onChange={(e) => setForm({ ...form, bestellnummer: e.target.value })}
            placeholder="steht auch in der E-Rechnung"
          />
        </label>

        <div className="block">
          <div className="flex items-center justify-between gap-3">
            <span className="field-label">Notiz auf der Rechnung (optional)</span>
            <TextbausteinWahl
              gewerbeId={gewerbeId}
              aktuell={form.notiz}
              onText={(t) => setForm({ ...form, notiz: t })}
            />
          </div>
          <textarea
            className="input min-h-[64px]"
            value={form.notiz}
            maxLength={2000}
            onChange={(e) => setForm({ ...form, notiz: e.target.value })}
            placeholder="z. B. Vielen Dank für den Auftrag."
          />
        </div>

        {!isEdit && (
          <div>
            <SchalterZeile
              titel="Rechnung wiederholt sich"
              hinweis="Diese Rechnung ist die erste — Tab erstellt die folgenden automatisch als Abo."
              checked={form.wiederholen}
              onChange={(an) => setForm({ ...form, wiederholen: an })}
            />
            {form.wiederholen && (
              <div className="space-y-1 pt-3">
                <div className="flex flex-wrap items-center gap-3">
                  <Dropdown
                    value={form.intervall}
                    onChange={(v) => setForm({ ...form, intervall: String(v) })}
                    options={Object.entries(INTERVALL_LABELS).map(([value, label]) => ({
                      value,
                      label,
                    }))}
                    variant="ghost"
                  />
                  <span className="text-[13px] tabular-nums text-ink/60">
                    nächste Rechnung am {formatDateDE(naechsterTermin(form.datum, form.intervall))}
                  </span>
                </div>
                <SchalterZeile
                  titel="Folge-Rechnungen automatisch senden"
                  hinweis={`Sonst entstehen sie als Entwurf. Braucht die Empfänger-E-Mail oben${!mailKonfiguriert ? ' und dein Mail-Konto (Einstellungen → E-Mail-Versand)' : ''}. Tipp: {monat} in der Positions-Beschreibung wird zum Abrechnungsmonat.`}
                  checked={form.auto_senden}
                  onChange={(an) => setForm({ ...form, auto_senden: an })}
                />
              </div>
            )}
          </div>
        )}

        <Hinweis className="text-xs">
          Der gewählte Steuer-Hinweis und Absender/IBAN aus den Gewerbe-Stammdaten kommen automatisch aufs PDF — samt{' '}
          <strong>GiroCode</strong> zum Bezahlen per QR-Scan —, das zugleich eine <strong>E-Rechnung</strong> ist
          (ZUGFeRD-XML eingebettet). §4-Nr.-11-Rechnungen werden bei „Als Einnahme buchen" der Kategorie
          „Umsatzsteuerfreie Einnahme (Courtage)" zugeordnet (Zeile 16).
        </Hinweis>

        <DialogFuss
          links={
            <button
              type="button"
              className="btn-outline"
              onClick={vorschau}
              disabled={busy}
              title="PDF aus den aktuellen Eingaben ansehen — speichert nichts, verbraucht keine Nummer"
            >
              Vorschau (PDF)
            </button>
          }
        >
          <button type="button" className="btn-ghost" onClick={() => setEditing(null)}>
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

// Rechnung oder (mit `mahnung`) eine Mahnung zu dieser Rechnung per Mail senden.
function SendenModal({ rechnung, mahnung, user, onClose, onSent }) {
  const [busy, setBusy] = useState(false);
  const name = mahnung ? `${STUFEN[mahnung.stufe]} zu Rechnung ${rechnung.nummer}` : `Rechnung ${rechnung.nummer}`;
  const [an, setAn] = useState(rechnung.empfaenger_email || '');
  const [betreff, setBetreff] = useState(name);
  const [text, setText] = useState(
    mahnung
      ? `Guten Tag,\n\nzur Rechnung ${rechnung.nummer} erhalten Sie im Anhang eine ${STUFEN[mahnung.stufe]}. Bitte überweisen Sie ${formatEuro(mahnung.gesamt_cent)} bis zum ${formatDateDE(mahnung.frist_am)}.\n\nMit freundlichen Grüßen\n${user?.name || ''}`
      : `Guten Tag,\n\nanbei erhalten Sie die Rechnung ${rechnung.nummer} über ${formatEuro(rechnung.summe_cent)}.\n\nMit freundlichen Grüßen\n${user?.name || ''}`,
  );

  async function send(e) {
    e.preventDefault();
    if (!an.trim()) return toast.error('Bitte Empfänger-Adresse angeben.');
    setBusy(true);
    try {
      await api.post(mahnung ? `/api/mahnwesen/${mahnung.id}/senden` : `/api/rechnungen/${rechnung.id}/senden`, {
        an: an.trim(),
        betreff,
        text,
      });
      toast.success(`${name} versendet.`);
      onClose();
      await onSent();
    } catch (err) {
      toast.error(apiError(err), { duration: 8000 });
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal title={`${name} senden`} onClose={onClose}>
      <form onSubmit={send} className="space-y-4">
        <label className="block">
          <span className="field-label">An</span>
          <input
            className="input"
            value={an}
            onChange={(e) => setAn(e.target.value)}
            placeholder="kunde@firma.de"
            autoFocus
          />
        </label>
        <label className="block">
          <span className="field-label">Betreff</span>
          <input className="input" value={betreff} onChange={(e) => setBetreff(e.target.value)} />
        </label>
        <label className="block">
          <span className="field-label">Nachricht</span>
          <textarea className="input min-h-[140px]" value={text} onChange={(e) => setText(e.target.value)} />
        </label>
        <p className="text-[13px] leading-snug text-ink/60">
          {mahnung ? 'Die Mahnung als PDF' : 'PDF (E-Rechnung, ZUGFeRD)'} hängt automatisch an · Absender: {user?.email}{' '}
          (landet in deinem „Gesendet"-Ordner)
        </p>
        <DialogFuss>
          <button type="button" className="btn-ghost" onClick={onClose}>
            Abbrechen
          </button>
          <button type="submit" className="btn-primary" disabled={busy}>
            {busy ? 'Sendet…' : 'Senden'}
          </button>
        </DialogFuss>
      </form>
    </Modal>
  );
}

// Zahlung auf eine versendete Rechnung: Teilzahlung oder Rest, optional gleich als Einnahme gebucht
// und mit Ausbuchen des Rests (Skonto bzw. Forderungsausfall). Bezahlt ist die Rechnung, sobald nichts
// mehr offen ist. Skonto und Ausfall sind kein Einkommen — gebucht wird nur, was zufließt.
function ZahlungModal({ rechnung: r, onClose, onSaved }) {
  const heute = todayISO();
  const skontoMoeglich = r.skonto_cent > 0 && r.bezahlt_cent === 0 && r.skonto_bis && heute <= r.skonto_bis;
  const [datum, setDatum] = useState(heute);
  const [betrag, setBetrag] = useState(centToInput(r.offen_cent));
  const [rest, setRest] = useState('');
  const [buchen, setBuchen] = useState(true);
  const [busy, setBusy] = useState(false);

  const cent = parseEuroToCent(betrag);
  const gueltig = cent !== null && cent > 0 && cent <= r.offen_cent && datum >= r.datum && datum <= heute;
  const restCent = gueltig ? r.offen_cent - cent : 0;

  function mitSkonto() {
    setBetrag(centToInput(r.offen_cent - r.skonto_cent));
    setRest('skonto');
  }

  async function speichern(e) {
    e.preventDefault();
    if (!gueltig) return;
    setBusy(true);
    try {
      await api.post(`/api/rechnungen/${r.id}/zahlungen`, {
        datum,
        betrag_cent: cent,
        buchen,
        rest_ausbuchen: restCent > 0 && rest ? rest : null,
      });
      toast.success(restCent > 0 && !rest ? 'Teilzahlung erfasst.' : 'Zahlung erfasst.');
      onClose();
      await onSaved();
    } catch (err) {
      toast.error(apiError(err));
      setBusy(false);
    }
  }

  return (
    <Modal title="Zahlung erfassen" subtitle={`Rechnung ${r.nummer} · ${r.empfaenger_name}`} onClose={onClose}>
      <form onSubmit={speichern} className="space-y-4">
        <p className="text-[13px] leading-snug text-ink/70">
          Rechnungsbetrag {formatEuro(r.summe_cent)}
          {r.bezahlt_cent > 0 && ` · schon bezahlt ${formatEuro(r.bezahlt_cent)}`} ·{' '}
          <strong>offen {formatEuro(r.offen_cent)}</strong>
        </p>
        {skontoMoeglich && (
          <Hinweis className="!py-2 text-xs">
            Skonto möglich bis {formatDateDE(r.skonto_bis)}: {r.skonto_prozent} % = {formatEuro(r.skonto_cent)}, der
            Kunde zahlt dann {formatEuro(r.offen_cent - r.skonto_cent)}.{' '}
            <button type="button" className="font-bold underline" onClick={mitSkonto}>
              So eintragen
            </button>
          </Hinweis>
        )}
        <div className="grid grid-cols-1 gap-x-5 gap-y-2 sm:grid-cols-2">
          <label className="block">
            <span className="field-label">Zahlungsdatum</span>
            <input
              type="date"
              className="input"
              value={datum}
              min={r.datum}
              max={heute}
              onChange={(e) => setDatum(e.target.value)}
            />
          </label>
          <label className="block">
            <span className="field-label">Betrag (€)</span>
            <input
              className="input"
              inputMode="decimal"
              value={betrag}
              autoFocus
              onChange={(e) => setBetrag(e.target.value)}
              aria-invalid={!gueltig}
            />
          </label>
        </div>
        {restCent > 0 && (
          <div className="block">
            <span className="field-label">Der Rest von {formatEuro(restCent)}</span>
            <Dropdown
              value={rest}
              onChange={(v) => setRest(String(v))}
              options={[
                { value: '', label: 'bleibt offen (Teilzahlung)' },
                { value: 'skonto', label: 'als Skonto ausbuchen' },
                { value: 'ausfall', label: 'ausbuchen (Forderungsausfall)' },
              ]}
            />
            <span className="mt-1 block text-xs text-ink/60">
              Ausgebucht heißt: Der Kunde schuldet ihn nicht mehr. Es ist kein Einkommen und wird nicht gebucht.
            </span>
          </div>
        )}
        <SchalterZeile
          titel="Als Einnahme buchen"
          hinweis="Bucht den Zahlungseingang am Zahlungsdatum als Einnahme. Sonst später an der Zahlung buchen."
          checked={buchen}
          onChange={setBuchen}
        />
        <DialogFuss>
          <button type="button" className="btn-ghost" onClick={onClose}>
            Abbrechen
          </button>
          <button type="submit" className="btn-primary" disabled={busy || !gueltig}>
            Speichern
          </button>
        </DialogFuss>
      </form>
    </Modal>
  );
}
