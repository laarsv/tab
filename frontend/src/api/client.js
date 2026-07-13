import axios from 'axios';

const baseURL = import.meta.env.VITE_API_BASE_URL || '';

// Session läuft über ein HttpOnly-Cookie (Google-OAuth) → withCredentials.
export const api = axios.create({ baseURL, withCredentials: true });

// URL zum Start des Google-Logins (Full-Page-Navigation zum Backend).
export const loginUrl = `${baseURL}/api/auth/login`;

// Bei 401 (außer beim /me-Probe) auf Login leiten — /me handhabt der AuthContext.
api.interceptors.response.use(
  (res) => res,
  (err) => {
    const url = err.config?.url || '';
    if (err.response?.status === 401 && !url.includes('/api/auth/me')) {
      if (!window.location.pathname.startsWith('/login')) {
        window.location.href = '/login';
      }
    }
    return Promise.reject(err);
  },
);

export function apiError(err, fallback = 'Es ist ein Fehler aufgetreten.') {
  const d = err?.response?.data?.detail;
  if (typeof d === 'string') return d;
  if (Array.isArray(d) && d[0]?.msg) return d[0].msg;
  return fallback;
}
