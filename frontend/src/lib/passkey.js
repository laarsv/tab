import { api } from '../api/client.js';

// Passkeys (WebAuthn) im Browser. Base64url-Umwandlung von Hand statt parse…FromJSON/toJSON, damit es auch in
// älteren Browsern läuft. Der Server (routes/passkeys.py) prüft alles — hier wird nur übersetzt.

export const passkeyVerfuegbar = () =>
  typeof window !== 'undefined' && Boolean(window.PublicKeyCredential) && Boolean(navigator.credentials);

const zuBytes = (b64url) => {
  const s = b64url.replace(/-/g, '+').replace(/_/g, '/');
  const bin = atob(s + '='.repeat((4 - (s.length % 4)) % 4));
  return Uint8Array.from(bin, (c) => c.charCodeAt(0));
};
const zuText = (buf) => {
  const bin = String.fromCharCode(...new Uint8Array(buf));
  return btoa(bin).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
};

// Fehler des Browsers verständlich machen (Abbruch durch die Nutzerin ist kein Fehler).
export function passkeyFehler(e) {
  if (e?.name === 'NotAllowedError' || e?.name === 'AbortError') return null;
  if (e?.name === 'InvalidStateError') return 'Dieses Gerät hat schon einen Passkey für dieses Konto.';
  if (e?.name === 'SecurityError') return 'Passkeys funktionieren nur über die echte Adresse (HTTPS).';
  return undefined; // andere Fehler: Aufrufer zeigt die Server-Meldung
}

export async function passkeyHinzufuegen(name) {
  const { data } = await api.post('/api/passkeys/registrierung/optionen');
  const o = data.options;
  const cred = await navigator.credentials.create({
    publicKey: {
      ...o,
      challenge: zuBytes(o.challenge),
      user: { ...o.user, id: zuBytes(o.user.id) },
      excludeCredentials: (o.excludeCredentials || []).map((c) => ({ ...c, id: zuBytes(c.id) })),
    },
  });
  if (!cred) return null;
  const r = cred.response;
  return api.post('/api/passkeys/registrierung', {
    challenge_id: data.challenge_id,
    name: name || '',
    credential: {
      id: cred.id,
      rawId: zuText(cred.rawId),
      type: cred.type,
      authenticatorAttachment: cred.authenticatorAttachment || undefined,
      clientExtensionResults: cred.getClientExtensionResults?.() || {},
      response: {
        clientDataJSON: zuText(r.clientDataJSON),
        attestationObject: zuText(r.attestationObject),
        transports: r.getTransports?.() || [],
      },
    },
  });
}

export async function passkeyAnmelden() {
  const { data } = await api.post('/api/passkeys/anmeldung/optionen');
  const o = data.options;
  const cred = await navigator.credentials.get({
    publicKey: { ...o, challenge: zuBytes(o.challenge), allowCredentials: [] },
  });
  if (!cred) return null;
  const r = cred.response;
  await api.post('/api/passkeys/anmeldung', {
    challenge_id: data.challenge_id,
    credential: {
      id: cred.id,
      rawId: zuText(cred.rawId),
      type: cred.type,
      authenticatorAttachment: cred.authenticatorAttachment || undefined,
      clientExtensionResults: cred.getClientExtensionResults?.() || {},
      response: {
        clientDataJSON: zuText(r.clientDataJSON),
        authenticatorData: zuText(r.authenticatorData),
        signature: zuText(r.signature),
        userHandle: r.userHandle ? zuText(r.userHandle) : undefined,
      },
    },
  });
  return true;
}
