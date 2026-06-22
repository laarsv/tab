import axios from 'axios';

const baseURL = import.meta.env.VITE_API_BASE_URL || '';

export const TOKEN_KEY = 'tab_token';

export const api = axios.create({ baseURL });

// Bearer-Token aus localStorage an jeden Request hängen.
api.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_KEY);
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// Bei 401 Token verwerfen und auf Login leiten.
api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem(TOKEN_KEY);
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
