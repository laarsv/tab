import { useEffect, useRef, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import toast from 'react-hot-toast';
import { api, apiError } from '../api/client.js';
import { Hinweis, PageHeader } from '../components/PageParts.jsx';
import { PageSpinner } from '../components/Spinner.jsx';

// Rückkehr von der Bank-Anmeldung (Enable Banking leitet auf /bank/verbunden?code=…&state=… zurück).
// Schließt die Verbindung ab (Konten zuordnen, erster Abruf) und geht zurück zur Bank-Seite.
export default function BankVerbunden() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const [fehler, setFehler] = useState(null);
  const gestartet = useRef(false);

  useEffect(() => {
    if (gestartet.current) return; // StrictMode: nur einmal einlösen
    gestartet.current = true;
    const code = params.get('code');
    const state = params.get('state');
    if (params.get('error') || !code || !state) {
      setFehler(
        params.get('error_description') ||
          (params.get('error') === 'access_denied' ? 'Die Freigabe wurde bei der Bank abgebrochen.' : 'Die Bank hat keine Freigabe zurückgegeben.'),
      );
      return;
    }
    api
      .post('/api/bank/abruf/abschliessen', { code, state })
      .then((r) => {
        const d = r.data;
        const konten = d.konten?.join(', ') || 'Konto';
        if (d.fehler) toast.error(`${d.bank_name} verbunden (${konten}), der erste Abruf ging schief: ${d.fehler}`, { duration: 10000 });
        else toast.success(`${d.bank_name} verbunden: ${konten} · ${d.neu} neue Umsätze.`, { duration: 6000 });
        localStorage.setItem('tab_gewerbe', String(d.gewerbe_id));
        navigate('/bank', { replace: true });
      })
      .catch((e) => setFehler(apiError(e)));
  }, [params, navigate]);

  if (!fehler) return <PageSpinner />;
  return (
    <div className="space-y-4">
      <PageHeader title="Konto verbinden" />
      <Hinweis ton="neg" titel="Verbinden hat nicht geklappt">
        {fehler}
      </Hinweis>
      <Link to="/bank" className="btn-outline inline-flex">
        Zurück zur Bank
      </Link>
    </div>
  );
}
