import { useEffect, useState } from 'react';
import { Link, useOutletContext } from 'react-router-dom';
import toast from 'react-hot-toast';
import { api } from '../api/client.js';
import { IconChevronDown } from '../components/Icons.jsx';
import { Fortschritt, KREIS, PageHeader, SectionHead, Zustand } from '../components/PageParts.jsx';

const LS_KEY = 'tab_setup_haken';

function loadHaken() {
  try {
    return new Set(JSON.parse(localStorage.getItem(LS_KEY) || '[]'));
  } catch {
    return new Set();
  }
}

// Zustand eines Schritts als Wort in Zustandsfarbe (kein Chip).
function SchrittZustand({ done, offen = 'Offen' }) {
  return done ? <Zustand ton="royal">Erledigt</Zustand> : <Zustand ton="warn">{offen}</Zustand>;
}

// Aufklappbare Zeile: Nummer im Kreis, Titel, Zustandszeile, Chevron; der Inhalt klappt
// darunter auf (erledigte Schritte sind zu, offene auf).
function Schritt({ nr, titel, done, zustand, children }) {
  const [offen, setOffen] = useState(!done);
  useEffect(() => setOffen(!done), [done]);
  return (
    <div className="border-b border-ink/[0.08]">
      <button
        type="button"
        aria-expanded={offen}
        className="flex w-full items-center gap-3.5 py-2.5 text-left outline-none focus-visible:ring-2 focus-visible:ring-royal/40 rounded-lg"
        onClick={() => setOffen((o) => !o)}
      >
        <span
          className={`inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-full font-mono text-sm font-bold ${done ? KREIS.in : KREIS.warn}`}
        >
          {nr}
        </span>
        <span className="min-w-0 flex-1">
          <span className="block text-[15px] font-bold leading-snug">{titel}</span>
          <span className="block text-[13px] leading-snug">{zustand}</span>
        </span>
        <IconChevronDown className={`h-4 w-4 shrink-0 text-ink/60 transition-transform ${offen ? 'rotate-180' : ''}`} />
      </button>
      {offen && <div className="space-y-2 pb-4 pl-[54px] text-sm leading-snug text-ink/75">{children}</div>}
    </div>
  );
}

// Einrichtung & Hilfe: geführter Wizard — Status kommt wo möglich automatisch
// aus den echten Daten, der Rest per Haken.
export default function Einrichtung() {
  const { gewerbeId, jahr, gewerbe, openMailSetup } = useOutletContext();
  const [mail, setMail] = useState(null);
  const [hatBuchungen, setHatBuchungen] = useState(false);
  const [haken, setHaken] = useState(loadHaken());

  useEffect(() => {
    api.get('/api/einstellungen/mail').then((r) => setMail(r.data)).catch(() => {});
    if (gewerbeId) {
      api
        .get('/api/buchungen', { params: { gewerbe_id: gewerbeId, jahr } })
        .then((r) => setHatBuchungen(r.data.length > 0))
        .catch(() => {});
    }
  }, [gewerbeId, jahr]);

  function toggleHaken(key) {
    const next = new Set(haken);
    if (next.has(key)) next.delete(key);
    else next.add(key);
    setHaken(next);
    localStorage.setItem(LS_KEY, JSON.stringify([...next]));
  }

  const gewerbeRow = gewerbe.find((g) => String(g.id) === String(gewerbeId));
  const s1 = gewerbe.length > 0;
  const s1b = Boolean(gewerbeRow?.anschrift);
  const s2 = Boolean(mail?.konfiguriert);
  const s3 = Boolean(mail?.import_aktiv);
  const s4 = haken.has('pwa');
  const s5 = hatBuchungen;
  const fertig = [s1, s2, s3, s4, s5].filter(Boolean).length;

  function copyPlus() {
    navigator.clipboard?.writeText(mail?.import_ziel || '').then(
      () => toast.success('Adresse kopiert.'),
      () => {},
    );
  }

  return (
    <div className="max-w-3xl">
      <PageHeader
        title="Einrichtung & Hilfe"
        sub="Einmal durchgehen, dann läuft alles — jeder Schritt erklärt sich hier im Detail."
      />

      <Fortschritt text={`${fertig} von 5 Schritten`} value={fertig} max={5} />

      <div className="mt-4">
      <Schritt nr={1} titel="Gewerbe & Rechnungs-Absender" done={s1 && s1b} zustand={<SchrittZustand done={s1 && s1b} offen={s1 ? 'Absender fehlt' : 'Offen'} />}>
        <p>
          Unter <Link to="/gewerbe" className="text-royal font-medium hover:underline">Gewerbe</Link>{' '}
          legst du dein Gewerbe an (eine EÜR pro Gewerbe). Für Rechnungen dort auch{' '}
          <strong>Name & Anschrift</strong> und die <strong>IBAN</strong> eintragen — Pflichtangaben
          auf jeder Rechnung.
        </p>
        <p className="text-xs text-ink/60">
          Mehrere Gewerbe unter einem Login gehen — sie teilen sich aber die Absender-Adresse
          beim Rechnungsversand. Faustregel: <strong>Eigene Mail-Domain pro Firma → eigener
          Login pro Firma.</strong>
        </p>
      </Schritt>

      <Schritt nr={2} titel="E-Mail-Versand einrichten (App-Passwort)" done={s2} zustand={<SchrittZustand done={s2} />}>
        <p>
          Damit Tab Rechnungen <strong>von deiner eigenen Adresse</strong> ({mail?.email}) senden
          kann, braucht es einmalig ein <strong>App-Passwort</strong> deines Google-Kontos — nicht
          dein normales Passwort. Es wird verschlüsselt gespeichert und lässt sich jederzeit
          entfernen.
        </p>
        <ol className="list-decimal ml-5 space-y-1">
          <li>2-Faktor-Authentifizierung im Google-Konto aktivieren (falls noch nicht: Google-Konto → Sicherheit).</li>
          <li>
            <a className="text-royal font-medium hover:underline" href="https://myaccount.google.com/apppasswords" target="_blank" rel="noreferrer">
              myaccount.google.com/apppasswords
            </a>{' '}
            öffnen und ein App-Passwort namens „Tab" erstellen (16 Zeichen).
          </li>
          <li>In Tab hinterlegen: <button className="text-royal font-medium hover:underline" onClick={openMailSetup}>E-Mail-Versand öffnen</button> → einfügen → „Speichern & prüfen" (Tab testet den Login sofort).</li>
          <li>Mit „Test-Mail" eine Probe an dich selbst schicken.</li>
        </ol>
        <p className="text-xs text-ink/50">
          Gilt pro Person: Jeder Login hinterlegt sein eigenes Mail-Konto und versendet von
          seiner eigenen Adresse. Deine Mail liegt nicht bei Google? Im Dialog einfach
          „Eigener Mail-Server" wählen (SMTP/IMAP-Daten deines Anbieters, z. B. All-Inkl).
        </p>
      </Schritt>

      <Schritt nr={3} titel="Belege per E-Mail einschicken" done={s3} zustand={<SchrittZustand done={s3} />}>
        <p>
          Deine persönliche Beleg-Adresse:{' '}
          <code className="font-mono text-royal font-medium break-all">{mail?.import_ziel || '…'}</code>{' '}
          <button className="btn-ghost btn-sm" onClick={copyPlus}>Kopieren</button>
        </p>
        <p>
          Das ist deine normale Adresse mit <strong>+tab</strong> vor dem @ — Google leitet solche
          Mails ganz normal in dein Postfach, Tab erkennt sie am Empfänger. Einfach Rechnungen{' '}
          <strong>weiterleiten</strong> (oder ein Foto per Mail schicken): Tab holt alle
          10 Minuten ab und legt PDF/JPG/PNG/XML-Anhänge in den Beleg-Eingang.
        </p>
        <ul className="list-disc ml-5 space-y-1">
          <li>Aktivieren: <button className="text-royal font-medium hover:underline" onClick={openMailSetup}>E-Mail-Versand öffnen</button> → „Beleg-Eingang per E-Mail" anhaken (braucht Schritt 2).</li>
          <li>Sicherheit: Nur Mails von freigeschalteten Absendern werden importiert — Fremde können nichts einschleusen. Dein Postfach wird nie verändert.</li>
          <li>Praktisch fürs iPhone: Dort ist der Mail-Weg der Teilen-Ersatz (siehe Schritt 4).</li>
        </ul>
      </Schritt>

      <Schritt
        nr={4}
        titel="Tab aufs Handy (App installieren & teilen)"
        done={s4}
        zustand={<SchrittZustand done={s4} />}
      >
        <p><strong>Android (Chrome):</strong></p>
        <ol className="list-decimal ml-5 space-y-1">
          <li>tab.vrwb.de öffnen → Menü (⋮) → <strong>„App installieren"</strong>.</li>
          <li>Danach taucht tab im <strong>Teilen-Menü</strong> auf: Kassenzettel fotografieren oder PDF im Mail-Anhang → Teilen → tab → landet im Beleg-Eingang.</li>
        </ol>
        <p><strong>iPhone (Safari):</strong></p>
        <ol className="list-decimal ml-5 space-y-1">
          <li>tab.vrwb.de öffnen → Teilen-Symbol → <strong>„Zum Home-Bildschirm"</strong> — Tab läuft dann wie eine App.</li>
          <li>iOS erlaubt Web-Apps leider kein Teilen-Ziel. Der Trick: Foto/PDF → Teilen → <strong>Mail</strong> → an deine +tab-Adresse (Schritt 3) — gleicher Effekt.</li>
        </ol>
        <button className="btn-outline btn-sm" onClick={() => toggleHaken('pwa')}>
          {s4 ? '✓ Erledigt — zurücknehmen' : 'Auf dem Handy eingerichtet — abhaken'}
        </button>
      </Schritt>

      <Schritt nr={5} titel="Belege sammeln & verbuchen" done={s5} zustand={<SchrittZustand done={s5} />}>
        <p>
          Alle Belege landen im <strong>Beleg-Eingang</strong> (oben auf{' '}
          <Link to="/buchungen" className="text-royal font-medium hover:underline">Buchungen</Link>) —
          egal ob hochgeladen, gemailt oder geteilt. Unbezahlte Rechnungen bekommen ein
          „fällig am"-Datum als Erinnerung.
        </p>
        <ul className="list-disc ml-5 space-y-1">
          <li><strong>„Jetzt abarbeiten"</strong> führt Beleg für Beleg durch — Tab liest den Beleg und füllt Datum, Betrag und Kategorie vor (immer prüfen!).</li>
          <li>Gebucht wird zum <strong>Zahltag</strong> (EÜR-Prinzip): Beleg erst bezahlen, dann verbuchen.</li>
          <li>Teure Anschaffungen (&gt; 800 € netto) laufen über <Link to="/afa" className="text-royal font-medium hover:underline">Abschreibungen</Link>.</li>
        </ul>
      </Schritt>

      </div>

      <SectionHead label="Und übers Jahr?" />
      <p className="text-sm leading-snug text-ink/75">
        Einmal im Jahr den{' '}
        <Link to="/check" className="font-medium text-royal hover:underline">Jahres-Check</Link>{' '}
        durchgehen (nichts vergessen), dann auf{' '}
        <Link to="/export" className="font-medium text-royal hover:underline">Export</Link> das
        Summenblatt in ELSTER übertragen und das Jahres-Archiv (ZIP) sichern. Abgabefrist ohne
        Steuerberater: 31.07. des Folgejahres. Tab ist die bessere Excel-Liste — keine
        Steuerberatung, im Zweifel prüfen lassen.
      </p>
    </div>
  );
}
