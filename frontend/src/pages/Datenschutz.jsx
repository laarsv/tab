import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api/client.js';
import Wordmark from '../components/Wordmark.jsx';

// Datenschutzerklärung von Tab — öffentlich (ohne Anmeldung), auch als Datenschutz-URL bei Enable Banking.
// Name/Anschrift/E-Mail des Verantwortlichen kommen aus der .env (GET /api/rechtliches), weil das Repo öffentlich ist.
// Ändert sich ein Datenfluss (neuer Dienst, neue Speicherung), diesen Text im selben Commit nachziehen und STAND anpassen.

const STAND = '16.11.2026';

function Abschnitt({ nr, titel, children }) {
  return (
    <section className="mt-8">
      <h2 className="text-lg font-black tracking-tight">
        <span className="mr-2 font-mono text-sm text-royal">{nr}</span>
        {titel}
      </h2>
      <div className="mt-2 space-y-2 text-[15px] leading-relaxed text-ink/80">{children}</div>
    </section>
  );
}

export default function Datenschutz() {
  const [r, setR] = useState(null);
  useEffect(() => {
    api
      .get('/api/rechtliches')
      .then((res) => setR(res.data))
      .catch(() => setR({}));
  }, []);

  return (
    <div className="min-h-screen bg-paper text-ink">
      <div className="mx-auto max-w-3xl px-4 py-10 sm:px-8 sm:py-14">
        <Link to="/" className="inline-block rounded-md outline-none focus-visible:ring-2 focus-visible:ring-royal/50">
          <Wordmark className="text-2xl" />
        </Link>
        <h1 className="page-title mt-8">Datenschutz</h1>
        <p className="mt-2 text-sm text-ink/60">Stand: {STAND}</p>

        <Abschnitt nr="1" titel="Verantwortlicher">
          {r?.verantwortlicher ? (
            <p className="whitespace-pre-line">{r.verantwortlicher}</p>
          ) : (
            <p>
              Siehe{' '}
              <a href={r?.impressum_url || 'https://vrwb.de/impressum'} className="text-royal underline">
                Impressum
              </a>
              .
            </p>
          )}
          {r?.email && (
            <p>
              E-Mail:{' '}
              <a href={`mailto:${r.email}`} className="text-royal underline">
                {r.email}
              </a>
            </p>
          )}
        </Abschnitt>

        <Abschnitt nr="2" titel="Kurzfassung">
          <p>
            Tab ist eine Webanwendung für die Buchhaltung (Einnahmen-Überschuss-Rechnung) von Selbstständigen. Was du in Tab
            einträgst und hochlädst, wird nur gespeichert und verarbeitet, damit Tab für dich funktioniert. Es gibt keine
            Werbung, kein Tracking, keine Analyse-Dienste und keine Weitergabe zu eigenen Zwecken. Die Seiten laden keine
            Inhalte von fremden Servern; auch die Schriften liegen auf dem eigenen Server. Dienste anderer Anbieter kommen nur
            ins Spiel, wenn du eine Funktion nutzt, die sie braucht (Abschnitt 6).
          </p>
        </Abschnitt>

        <Abschnitt nr="3" titel="Hosting und Server-Protokolle">
          <p>
            Tab läuft auf einem eigenen Server bei der Hetzner Online GmbH im Rechenzentrum Nürnberg, Deutschland. Mit Hetzner
            besteht ein Vertrag zur Auftragsverarbeitung.
          </p>
          <p>
            Beim Aufruf werden technisch notwendige Angaben protokolliert (IP-Adresse, Zeitpunkt, aufgerufene Adresse,
            Browser). Sie dienen dem sicheren Betrieb und der Fehlersuche und werden nicht mit anderen Daten zusammengeführt.
            Rechtsgrundlage: Art. 6 Abs. 1 lit. f DSGVO (berechtigtes Interesse am sicheren Betrieb).
          </p>
        </Abschnitt>

        <Abschnitt nr="4" titel="Konto und Anmeldung">
          <p>
            Für dein Konto speichert Tab deine E-Mail-Adresse und deinen Namen. Du meldest dich an mit Google (Google übermittelt
            dann Name, E-Mail-Adresse und ob sie bestätigt ist), mit E-Mail und Passwort (gespeichert wird nur ein Hash des
            Passworts; Bestätigungs- und Rücksetzcodes kommen per E-Mail) oder mit einem Passkey (gespeichert wird nur der
            öffentliche Schlüssel).
          </p>
          <p>
            Nach der Anmeldung setzt Tab ein Sitzungs-Cookie, das nur für die Anmeldung da ist (technisch notwendig, keine
            Einwilligung erforderlich). Im Speicher deines Browsers (localStorage) legt Tab Bedienungs-Einstellungen ab, etwa
            das gewählte Gewerbe und Jahr oder den Stand des Jahres-Checks. Diese Daten bleiben auf deinem Gerät.
          </p>
          <p>Rechtsgrundlage: Art. 6 Abs. 1 lit. b DSGVO (Nutzung von Tab).</p>
        </Abschnitt>

        <Abschnitt nr="5" titel="Was du in Tab speicherst">
          <p>
            Buchungen, Belege (Dateien), Rechnungen, Angebote, Mahnungen, Kontakte, Anlagen, Fahrten, Bankumsätze und
            Einstellungen. Hinterlegst du ein E-Mail-Konto zum Versand oder Abholen von Belegen, speichert Tab dessen
            Zugangsdaten verschlüsselt. Die Texterkennung von Belegen (auch von Fotos) läuft auf dem Server von Tab, ohne
            fremden Dienst.
          </p>
          <p>
            Darunter sind oft Daten anderer Menschen, zum Beispiel deiner Kundinnen und Kunden auf Rechnungen. Für diese Daten
            bist du verantwortlich; Tab verarbeitet sie nur, um die Funktionen für dich bereitzustellen.
          </p>
          <p>
            Änderungen an Buchhaltungsdaten schreibt Tab in ein Änderungsprotokoll (wer, wann, was), damit die Buchhaltung
            nachvollziehbar bleibt.
          </p>
        </Abschnitt>

        <Abschnitt nr="6" titel="Andere Anbieter — nur wenn du die Funktion nutzt">
          <ul className="list-disc space-y-2 pl-5">
            <li>
              <strong>Anmeldung mit Google:</strong> Google Ireland Limited / Google LLC. Dabei können Daten in die USA gelangen
              (Angemessenheitsbeschluss, EU-US Data Privacy Framework).
            </li>
            <li>
              <strong>E-Mail-Versand und Mail-Import:</strong> über das E-Mail-Konto, das du selbst hinterlegst (z. B. Gmail
              oder dein eigener Mail-Server). System-Nachrichten (Bestätigungscodes) verschickt Tab über einen Mail-Server der
              Neue Medien Münnich GmbH (All-Inkl.com), Deutschland.
            </li>
            <li>
              <strong>Bankabruf:</strong> Verbindest du ein Bankkonto, ruft Tab Umsätze und IBAN über den
              Kontoinformationsdienst der Enable Banking Oy (Finnland) bei deiner Bank ab — nur mit deiner Freigabe bei der
              Bank, nur lesend. Du kannst die Verbindung jederzeit in Tab trennen; die Freigabe endet außerdem nach höchstens
              180 Tagen.
            </li>
            <li>
              <strong>KI-Assistenten:</strong> Richtest du einen Zugang für einen KI-Assistenten ein (z. B. Claude), liest der
              Assistent die freigegebenen Daten und sie gehen an dessen Anbieter. Zugänge lassen sich jederzeit widerrufen.
            </li>
            <li>
              <strong>Steuerberatung:</strong> Lädst du deine Steuerberatung ein, kann sie deine Buchhaltung lesen, bis du den
              Zugang entfernst.
            </li>
            <li>
              <strong>Basiszinssatz:</strong> Den Zinssatz für Verzugszinsen holt Tab von der Deutschen Bundesbank — ohne
              Daten von dir.
            </li>
          </ul>
        </Abschnitt>

        <Abschnitt nr="7" titel="Speicherdauer und Sicherungen">
          <p>
            Deine Daten bleiben gespeichert, solange dein Konto besteht. Für Buchhaltungsunterlagen gelten gesetzliche
            Aufbewahrungsfristen (in der Regel 8 bis 10 Jahre); darauf zu achten ist deine Sache — über den Export kannst du
            jederzeit alles herunterladen.
          </p>
          <p>
            Der Server wird jede Nacht gesichert. Die Sicherungen liegen bis zu 7 Tage auf dem Server und bis zu 12 Monate
            verschlüsselt übertragen auf einem Speicher des Betreibers in Deutschland. Gelöschte Daten verschwinden daher erst
            mit Ablauf dieser Sicherungen ganz.
          </p>
        </Abschnitt>

        <Abschnitt nr="8" titel="Deine Rechte">
          <p>
            Du hast das Recht auf Auskunft, Berichtigung, Löschung, Einschränkung der Verarbeitung, Datenübertragbarkeit und
            Widerspruch (Art. 15 bis 21 DSGVO). Schreib dafür an die oben genannte Adresse. Du kannst dich außerdem bei einer
            Datenschutz-Aufsichtsbehörde beschweren, zum Beispiel beim Landesbeauftragten für den Datenschutz und die
            Informationsfreiheit Baden-Württemberg.
          </p>
        </Abschnitt>

        <p className="mt-12 text-sm text-ink/60">
          <Link to="/" className="text-royal underline">
            Zurück zu Tab
          </Link>
          {r?.impressum_url && (
            <>
              {' · '}
              <a href={r.impressum_url} className="text-royal underline">
                Impressum
              </a>
            </>
          )}
        </p>
      </div>
    </div>
  );
}
