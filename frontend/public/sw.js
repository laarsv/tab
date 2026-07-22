// Service Worker — bewusst minimal: KEIN Caching (die App soll nie stale sein),
// einzig das PWA-Share-Target wird behandelt: vom Handy geteilte Dateien gehen
// an /api/belege/share (Beleg-Eingang), danach Redirect in die App.
self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', (event) => event.waitUntil(self.clients.claim()));

self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);
  if (event.request.method !== 'POST' || url.pathname !== '/share-target') return;

  event.respondWith(
    (async () => {
      let ziel = '/buchungen?geteilt=fehler';
      try {
        const formData = await event.request.formData();
        const files = formData.getAll('belege').filter((f) => f && f.size > 0);
        if (files.length > 0) {
          const upload = new FormData();
          for (const f of files) upload.append('belege', f, f.name);
          const res = await fetch('/api/belege/share', {
            method: 'POST',
            body: upload,
            credentials: 'same-origin',
          });
          if (res.ok) ziel = '/buchungen?geteilt=ok';
          else if (res.status === 401) ziel = '/login';
        }
      } catch (e) {
        // ziel bleibt "fehler"
      }
      return Response.redirect(ziel, 303);
    })(),
  );
});
