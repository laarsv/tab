import { Navigate, Route, Routes } from 'react-router-dom';
import { useAuth } from './auth/AuthContext.jsx';
import { PageSpinner } from './components/Spinner.jsx';
import Layout from './components/Layout.jsx';
import Login from './pages/Login.jsx';
import Buchungen from './pages/Buchungen.jsx';
import Afa from './pages/Afa.jsx';
import Export from './pages/Export.jsx';
import Gewerbe from './pages/Gewerbe.jsx';
import JahresCheck from './pages/JahresCheck.jsx';
import Fahrten from './pages/Fahrten.jsx';
import Fristen from './pages/Fristen.jsx';
import Abschluss from './pages/Abschluss.jsx';
import Bank from './pages/Bank.jsx';
import Rechnungen from './pages/Rechnungen.jsx';
import Angebote from './pages/Angebote.jsx';
import Dauerbelege from './pages/Dauerbelege.jsx';
import Mahnwesen from './pages/Mahnwesen.jsx';
import MahnungNeu from './pages/MahnungNeu.jsx';
import Einrichtung from './pages/Einrichtung.jsx';

function Protected({ children }) {
  const { user, loading } = useAuth();
  if (loading) return <PageSpinner />;
  if (!user) return <Navigate to="/login" replace />;
  return children;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route
        element={
          <Protected>
            <Layout />
          </Protected>
        }
      >
        <Route path="/buchungen" element={<Buchungen />} />
        <Route path="/eingang" element={<Navigate to="/buchungen" replace />} />
        <Route path="/afa" element={<Afa />} />
        <Route path="/check" element={<JahresCheck />} />
        <Route path="/fahrten" element={<Fahrten />} />
        <Route path="/fristen" element={<Fristen />} />
        <Route path="/abschluss" element={<Abschluss />} />
        <Route path="/bank" element={<Bank />} />
        <Route path="/rechnungen" element={<Rechnungen />} />
        <Route path="/dauerbelege" element={<Dauerbelege />} />
        <Route path="/rechnungen/angebote" element={<Angebote />} />
        <Route path="/rechnungen/wiederkehrend" element={<Rechnungen tab="wiederkehrend" />} />
        <Route path="/rechnungen/mahnwesen" element={<Mahnwesen />} />
        <Route path="/rechnungen/mahnwesen/:id" element={<MahnungNeu />} />
        <Route path="/einrichtung" element={<Einrichtung />} />
        <Route path="/export" element={<Export />} />
        <Route path="/gewerbe" element={<Gewerbe />} />
        <Route path="*" element={<Navigate to="/buchungen" replace />} />
      </Route>
    </Routes>
  );
}
