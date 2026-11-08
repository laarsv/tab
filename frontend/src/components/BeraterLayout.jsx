import { useEffect, useState } from 'react';
import { Outlet } from 'react-router-dom';
import toast from 'react-hot-toast';
import { api, apiError } from '../api/client.js';
import { useAuth } from '../auth/AuthContext.jsx';
import Dropdown from './Dropdown.jsx';
import { IconLogOut } from './Icons.jsx';
import { PageSpinner } from './Spinner.jsx';
import Wordmark from './Wordmark.jsx';

// Rahmen für die Steuerberatung: schlanke Royal-Leiste oben, Firma + Jahr, Abmelden. Keine Navigation in die
// Bereiche des Inhabers — der Server ließe sie ohnehin nicht zu.
export default function BeraterLayout() {
  const { user, logout } = useAuth();
  const [gewerbe, setGewerbe] = useState([]);
  const [jahre, setJahre] = useState([]);
  const [loading, setLoading] = useState(true);
  const [gewerbeId, setGewerbeId] = useState('');
  const [jahr, setJahr] = useState(String(new Date().getFullYear()));

  useEffect(() => {
    Promise.all([api.get('/api/gewerbe'), api.get('/api/meta/jahre')])
      .then(([g, j]) => {
        setGewerbe(g.data);
        setJahre(j.data);
        if (g.data[0]) setGewerbeId(String(g.data[0].id));
      })
      .catch((e) => toast.error(apiError(e, 'Laden fehlgeschlagen.')))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="min-h-full">
      <header className="bg-royal text-paper">
        <div className="mx-auto flex max-w-5xl flex-wrap items-center gap-x-4 gap-y-2 px-4 py-3 sm:px-6">
          <Wordmark onRoyal className="text-xl leading-none" />
          <span className="rounded-full bg-paper/[0.18] px-2.5 py-0.5 text-xs font-bold">Steuerberatung · nur lesen</span>
          <div className="flex-1" />
          <div className="w-44">
            <Dropdown variant="onRoyal" value={gewerbeId} onChange={(v) => setGewerbeId(String(v))}
              options={gewerbe.map((g) => ({ value: String(g.id), label: g.name }))} />
          </div>
          <div className="w-24">
            <Dropdown variant="onRoyal" value={jahr} onChange={(v) => setJahr(String(v))}
              options={jahre.map((j) => ({ value: String(j.jahr), label: String(j.jahr) }))} />
          </div>
          <button type="button" onClick={logout} title={`Abmelden (${user?.name || ''})`} aria-label="Abmelden"
            className="inline-flex h-10 items-center gap-1.5 rounded-xl px-3 text-sm font-bold outline-none hover:bg-paper/10 focus-visible:ring-2 focus-visible:ring-paper/70">
            <IconLogOut className="h-[18px] w-[18px]" /> Abmelden
          </button>
        </div>
      </header>
      <main className="px-4 pb-16 pt-6 sm:px-6 sm:pt-8">
        <div className="mx-auto max-w-5xl">
          {loading ? <PageSpinner /> : <Outlet context={{ gewerbeId, jahr: Number(jahr), gewerbe }} />}
          <p className="mt-12 text-xs text-ink/60">
            Zugang für die Steuerberatung{user?.bezeichnung ? ` (${user.bezeichnung})` : ''} — nur lesend. Tab ist keine
            Steuerberatung; Zahlen vor der Abgabe prüfen.
          </p>
        </div>
      </main>
    </div>
  );
}
