import { useEffect, useState } from 'react';
import { Link, useOutletContext } from 'react-router-dom';
import toast from 'react-hot-toast';
import { api } from '../api/client.js';

const LS_KEY = 'tab_setup_haken';

function loadHaken() {
  try {
    return new Set(JSON.parse(localStorage.getItem(LS_KEY) || '[]'));
  } catch {
    return new Set();
  }
}

function StatusChip({ done, offen = 'Offen' }) {
  return done ? (
    <span className="inline-flex items-center px-2 py-0.5 rounded-full bg-royal text-paper text-[11px] font-bold shrink-0">
      ✓ Erledigt
    </span>
  ) : (
    <span className="inline-flex items-center px-2 py-0.5 rounded-full bg-yellow-100 text-yellow-900 text-[11px] font-bold shrink-0">
      {offen}
    </span>
  );
}

function Schritt({ nr, titel, done, chip, children }) {
  const [offen, setOffen] = useState(!done);
  useEffect(() => setOffen(!done), [done]);
  return (
    <div className="card p-4 space-y-2">
      <button type="button" className="w-full flex items-center justify-between gap-3 text-left" onClick={() => setOffen((o) => !o)}>
        <div className="font-bold flex items-center gap-2 min-w-0">
          <span className={`inline-flex items-center justify-center h-6 w-6 rounded-full text-xs font-black shrink-0 ${done ? 'bg-royal text-paper' : 'bg-ink/10 text-ink/60'}`}>
            {nr}
          </span>
          <span className="truncate">{titel}</span>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {chip}
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
            className={`h-4 w-4 text-ink/50 transition-transform ${offen ? 'rotate-180' : ''}`}>
            <path d="M6 9l6 6 6-6" />
          </svg>
        </div>
      </button>
      {offen && <div className="pl-8 space-y-2 text-sm text-ink/75">{children}</div>}
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
    navigator.clipboard?.writeText(mail?.plus_adresse || '').then(
      () => toast.success('Adresse kopiert.'),
      () => {},
    );
  }

  return (
    <div className="space-y-6 max-w-3xl">
      <div>
        <h1 className="text-2xl sm:text-3xl font-black tracking-tight">Einrichtung & Hilfe</h1>
        <p className="text-xs text-ink/60 mt-0.5">
          Einmal durchgehen, dann läuft alles — jeder Schritt erklärt sich hier im Detail.
        </p>
      </div>

      <div className="card p-4">
        <div className="flex items-baseline justify-between gap-3">
          <div className="text-[11px] font-bold tracking-wider text-ink/60 uppercase">Fortschritt</div>
          <div className="text-sm tabular-nums text-ink/70">{fertig} von 5 Schritten</div>
        </div>
        <div className="h-2 rounded-full bg-ink/5 mt-2">
          <div className="h-2 rounded-full bg-royal transition-all" style={{ width: `${(fertig / 5) * 100}%` }} />
        </div>
      </div>

      <Schritt nr={1} titel="Gewerbe & Rechnungs-Absender" done={s1 && s1b} chip={<StatusChip done={s1 && s1b} offen={s1 ? 'Absender fehlt' : 'Offen'} />}>
        <p>
          Unter <Link to="/gewerbe" className="text-royal font-medium hover:underline">Gewerbe</Link>{' '}
          legst du dein Gewerbe an (eine EÜR pro Gewerbe). Für Rechnungen dort auch{' '}
          <strong>Name & Anschrift</strong> und die <strong>IBAN</strong> eintragen — Pflichtangaben
          auf jeder Rechnung.
        </p>
      </Schritt>

      <Schritt nr={2} titel="E-Mail-Versand einrichten (App-Passwort)" done={s2} chip={<StatusChip done={s2} />}>
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
          Gilt pro Person: Jeder Login hinterlegt sein eigenes App-Passwort und versendet von
          seiner eigenen Adresse.
        </p>
      </Schritt>

      <Schritt nr={3} titel="Belege per E-Mail einschicken" done={s3} chip={<StatusChip done={s3} />}>
        <p>
          Deine persönliche Beleg-Adresse:{' '}
          <code className="font-mono text-royal font-medium break-all">{mail?.plus_adresse || '…'}</code>{' '}
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
        chip={<StatusChip done={s4} />}
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

      <Schritt nr={5} titel="Belege sammeln & verbuchen" done={s5} chip={<StatusChip done={s5} />}>
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

      <div className="card p-4 space-y-2">
        <div className="font-bold">Und übers Jahr?</div>
        <p className="text-sm text-ink/75">
          Einmal im Jahr den{' '}
          <Link to="/check" className="text-royal font-medium hover:underline">Jahres-Check</Link>{' '}
          durchgehen (nichts vergessen), dann auf{' '}
          <Link to="/export" className="text-royal font-medium hover:underline">Export</Link> das
          Summenblatt in ELSTER übertragen und das Jahres-Archiv (ZIP) sichern. Abgabefrist ohne
          Steuerberater: 31.07. des Folgejahres. Tab ist die bessere Excel-Liste — keine
          Steuerberatung, im Zweifel prüfen lassen.
        </p>
      </div>
    </div>
  );
}
