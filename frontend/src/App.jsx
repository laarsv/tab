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
import Rechnungen from './pages/Rechnungen.jsx';

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
        <Route path="/rechnungen" element={<Rechnungen />} />
        <Route path="/export" element={<Export />} />
        <Route path="/gewerbe" element={<Gewerbe />} />
        <Route path="*" element={<Navigate to="/buchungen" replace />} />
      </Route>
    </Routes>
  );
}
