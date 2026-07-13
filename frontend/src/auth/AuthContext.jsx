import { createContext, useContext, useEffect, useState } from 'react';
import { api } from '../api/client.js';

const AuthCtx = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    api
      .get('/api/auth/me')
      .then((res) => active && setUser(res.data))
      .catch(() => active && setUser(null))
      .finally(() => active && setLoading(false));
    return () => {
      active = false;
    };
  }, []);

  async function logout() {
    try {
      await api.post('/api/auth/logout');
    } catch {
      /* egal — Cookie wird serverseitig gelöscht, Client leitet trotzdem um */
    }
    setUser(null);
    window.location.href = '/login';
  }

  return <AuthCtx.Provider value={{ user, loading, logout }}>{children}</AuthCtx.Provider>;
}

export function useAuth() {
  return useContext(AuthCtx);
}
