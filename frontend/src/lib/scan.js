// Belegscanner: Bildaufbereitung komplett im Browser, ohne Bibliothek und ohne fremde Server.
// Ablauf je Seite: Foto laden (Drehung aus EXIF übernimmt der Browser) → verkleinern →
// Ecken des Blatts erkennen (Vorschlag, von Hand verschiebbar) → perspektivisch entzerren →
// optional „Dokument“ (Schatten ausgleichen, Graustufen, Kontrast) → JPEG.
// Zusammengefügt zu einer PDF wird auf dem Server (POST /api/belege/scan, PyMuPDF).

export const ARBEIT_MAX = 2000; // längste Kante des Arbeitsbilds und der fertigen Seite (px)
const ERKENNUNG_MAX = 320; // längste Kante für die Kantenerkennung

function canvas(w, h) {
  const c = document.createElement('canvas');
  c.width = Math.max(1, Math.round(w));
  c.height = Math.max(1, Math.round(h));
  return c;
}

// Datei → Canvas (längste Kante ≤ ARBEIT_MAX). <img> wendet die EXIF-Drehung an.
export async function ladeBild(file) {
  const url = URL.createObjectURL(file);
  try {
    const img = new Image();
    img.decoding = 'async';
    img.src = url;
    await img.decode();
    const f = Math.min(1, ARBEIT_MAX / Math.max(img.naturalWidth, img.naturalHeight));
    const c = canvas(img.naturalWidth * f, img.naturalHeight * f);
    const ctx = c.getContext('2d');
    ctx.imageSmoothingQuality = 'high';
    ctx.drawImage(img, 0, 0, c.width, c.height);
    return c;
  } finally {
    URL.revokeObjectURL(url);
  }
}

// Canvas um 90° drehen (richtung 1 = rechts, -1 = links).
export function drehe(src, richtung) {
  const c = canvas(src.height, src.width);
  const ctx = c.getContext('2d');
  ctx.translate(c.width / 2, c.height / 2);
  ctx.rotate((richtung * Math.PI) / 2);
  ctx.drawImage(src, -src.width / 2, -src.height / 2);
  return c;
}

// Ecken (relativ 0..1) mitdrehen: [oben links, oben rechts, unten rechts, unten links].
export function dreheEcken(ecken, richtung) {
  const p = ecken.map(([x, y]) => (richtung === 1 ? [1 - y, x] : [y, 1 - x]));
  return sortiereEcken(p);
}

export const VOLLBILD = [
  [0, 0],
  [1, 0],
  [1, 1],
  [0, 1],
];

function sortiereEcken(pkte) {
  const summe = pkte.map(([x, y]) => x + y);
  const diff = pkte.map(([x, y]) => x - y);
  const idx = (arr, fn) => arr.indexOf(fn(...arr));
  return [
    pkte[idx(summe, Math.min)],
    pkte[idx(diff, Math.max)],
    pkte[idx(summe, Math.max)],
    pkte[idx(diff, Math.min)],
  ];
}

// Graustufen eines Canvas (Uint8Array, Luminanz).
function grau(c) {
  const { data } = c.getContext('2d').getImageData(0, 0, c.width, c.height);
  const g = new Uint8ClampedArray(c.width * c.height);
  for (let i = 0, j = 0; i < data.length; i += 4, j += 1) {
    g[j] = (data[i] * 77 + data[i + 1] * 150 + data[i + 2] * 29) >> 8;
  }
  return g;
}

function otsu(g) {
  const hist = new Array(256).fill(0);
  for (let i = 0; i < g.length; i += 1) hist[g[i]] += 1;
  let sum = 0;
  for (let t = 0; t < 256; t += 1) sum += t * hist[t];
  let sumB = 0;
  let wB = 0;
  let best = 0;
  let schwelle = 128;
  for (let t = 0; t < 256; t += 1) {
    wB += hist[t];
    if (!wB) continue;
    const wF = g.length - wB;
    if (!wF) break;
    sumB += t * hist[t];
    const mB = sumB / wB;
    const mF = (sum - sumB) / wF;
    const v = wB * wF * (mB - mF) ** 2;
    if (v > best) {
      best = v;
      schwelle = t;
    }
  }
  return schwelle;
}

// Ecken des Blatts erkennen: helles Papier vor dunklerem Hintergrund. Größte helle Fläche
// (Otsu-Schwelle, Zusammenhang), deren äußerste Punkte die vier Ecken sind. Klappt das nicht
// (Blatt auf hellem Tisch, Fläche zu klein/zu groß), kommt das ganze Bild zurück.
export function erkenneEcken(src) {
  const f = Math.min(1, ERKENNUNG_MAX / Math.max(src.width, src.height));
  const klein = canvas(src.width * f, src.height * f);
  const kctx = klein.getContext('2d');
  kctx.filter = 'blur(2px)';
  kctx.drawImage(src, 0, 0, klein.width, klein.height);
  const w = klein.width;
  const h = klein.height;
  const g = grau(klein);
  const t = otsu(g);
  const hell = new Uint8Array(w * h);
  for (let i = 0; i < g.length; i += 1) hell[i] = g[i] > t ? 1 : 0;

  // Größte zusammenhängende helle Fläche (4er-Nachbarschaft, eigener Stapel statt Rekursion).
  const marke = new Int32Array(w * h);
  const stapel = new Int32Array(w * h);
  let besteFlaeche = 0;
  let besteMarke = 0;
  let naechste = 1;
  for (let start = 0; start < hell.length; start += 1) {
    if (!hell[start] || marke[start]) continue;
    let oben = 0;
    stapel[oben++] = start;
    marke[start] = naechste;
    let flaeche = 0;
    while (oben) {
      const p = stapel[--oben];
      flaeche += 1;
      const x = p % w;
      const nachbarn = [x > 0 ? p - 1 : -1, x < w - 1 ? p + 1 : -1, p - w, p + w];
      for (const n of nachbarn) {
        if (n >= 0 && n < hell.length && hell[n] && !marke[n]) {
          marke[n] = naechste;
          stapel[oben++] = n;
        }
      }
    }
    if (flaeche > besteFlaeche) {
      besteFlaeche = flaeche;
      besteMarke = naechste;
    }
    naechste += 1;
  }
  const anteil = besteFlaeche / (w * h);
  if (anteil < 0.12 || anteil > 0.97) return VOLLBILD;

  let tl = [0, 0, Infinity];
  let tr = [0, 0, -Infinity];
  let br = [0, 0, -Infinity];
  let bl = [0, 0, Infinity];
  for (let p = 0; p < marke.length; p += 1) {
    if (marke[p] !== besteMarke) continue;
    const x = p % w;
    const y = (p - x) / w;
    if (x + y < tl[2]) tl = [x, y, x + y];
    if (x - y > tr[2]) tr = [x, y, x - y];
    if (x + y > br[2]) br = [x, y, x + y];
    if (x - y < bl[2]) bl = [x, y, x - y];
  }
  // Etwas nach innen (1 %), damit kein Rand vom Tisch mit auf die Seite kommt.
  const mx = (tl[0] + tr[0] + br[0] + bl[0]) / 4;
  const my = (tl[1] + tr[1] + br[1] + bl[1]) / 4;
  const ecken = [tl, tr, br, bl].map(([x, y]) => [(x + (mx - x) * 0.02) / (w - 1), (y + (my - y) * 0.02) / (h - 1)]);
  // Entartete Vierecke (z. B. Dreieck) verwerfen.
  if (viereckFlaeche(ecken) < 0.1) return VOLLBILD;
  return ecken;
}

function viereckFlaeche(e) {
  let a = 0;
  for (let i = 0; i < 4; i += 1) {
    const [x1, y1] = e[i];
    const [x2, y2] = e[(i + 1) % 4];
    a += x1 * y2 - x2 * y1;
  }
  return Math.abs(a) / 2;
}

// Homographie, die das Einheitsquadrat (0,0)(1,0)(1,1)(0,1) auf das Viereck abbildet.
function quadratAufViereck(q) {
  const [[x0, y0], [x1, y1], [x2, y2], [x3, y3]] = q;
  const dx1 = x1 - x2;
  const dx2 = x3 - x2;
  const dy1 = y1 - y2;
  const dy2 = y3 - y2;
  const sx = x0 - x1 + x2 - x3;
  const sy = y0 - y1 + y2 - y3;
  let g = 0;
  let h = 0;
  if (Math.abs(sx) > 1e-9 || Math.abs(sy) > 1e-9) {
    const det = dx1 * dy2 - dx2 * dy1;
    g = (sx * dy2 - dx2 * sy) / det;
    h = (dx1 * sy - sx * dy1) / det;
  }
  return [x1 - x0 + g * x1, x3 - x0 + h * x3, x0, y1 - y0 + g * y1, y3 - y0 + h * y3, y0, g, h];
}

const abstand = ([ax, ay], [bx, by]) => Math.hypot(ax - bx, ay - by);

// Viereck (Ecken relativ 0..1) aus dem Arbeitsbild ausschneiden und gerade ziehen.
export function entzerre(src, ecken, maxKante = ARBEIT_MAX) {
  const q = ecken.map(([x, y]) => [x * (src.width - 1), y * (src.height - 1)]);
  let w = (abstand(q[0], q[1]) + abstand(q[3], q[2])) / 2;
  let h = (abstand(q[0], q[3]) + abstand(q[1], q[2])) / 2;
  const f = Math.min(1, maxKante / Math.max(w, h));
  w = Math.max(1, Math.round(w * f));
  h = Math.max(1, Math.round(h * f));
  const sw = src.width;
  const sh = src.height;
  const quelle = src.getContext('2d').getImageData(0, 0, sw, sh).data;
  const ziel = canvas(w, h);
  const zctx = ziel.getContext('2d');
  const out = zctx.createImageData(w, h);
  const d = out.data;
  const [a, b, c, dd, e, ff, g, hh] = quadratAufViereck(q);
  for (let y = 0; y < h; y += 1) {
    const v = h > 1 ? y / (h - 1) : 0;
    for (let x = 0; x < w; x += 1) {
      const u = w > 1 ? x / (w - 1) : 0;
      const z = g * u + hh * v + 1;
      let sx = (a * u + b * v + c) / z;
      let sy = (dd * u + e * v + ff) / z;
      if (sx < 0) sx = 0;
      if (sy < 0) sy = 0;
      if (sx > sw - 1) sx = sw - 1;
      if (sy > sh - 1) sy = sh - 1;
      // bilinear
      const x0 = sx | 0;
      const y0 = sy | 0;
      const x1 = x0 + 1 < sw ? x0 + 1 : x0;
      const y1 = y0 + 1 < sh ? y0 + 1 : y0;
      const fx = sx - x0;
      const fy = sy - y0;
      const i00 = (y0 * sw + x0) * 4;
      const i10 = (y0 * sw + x1) * 4;
      const i01 = (y1 * sw + x0) * 4;
      const i11 = (y1 * sw + x1) * 4;
      const o = (y * w + x) * 4;
      for (let k = 0; k < 3; k += 1) {
        const oben = quelle[i00 + k] + (quelle[i10 + k] - quelle[i00 + k]) * fx;
        const unten = quelle[i01 + k] + (quelle[i11 + k] - quelle[i01 + k]) * fx;
        d[o + k] = oben + (unten - oben) * fy;
      }
      d[o + 3] = 255;
    }
  }
  zctx.putImageData(out, 0, 0);
  return ziel;
}

// „Dokument“: Hintergrund (Papierhelligkeit) blockweise schätzen und herausrechnen — so
// verschwinden Schatten und Farbstich —, dann Graustufen mit gestrecktem Kontrast.
export function dokument(src) {
  const w = src.width;
  const h = src.height;
  const ctx = src.getContext('2d');
  const bild = ctx.getImageData(0, 0, w, h);
  const g = grau(src);
  const B = 24; // Blockgröße in px
  const bw = Math.ceil(w / B);
  const bh = Math.ceil(h / B);
  const hg = new Float32Array(bw * bh);
  for (let by = 0; by < bh; by += 1) {
    for (let bx = 0; bx < bw; bx += 1) {
      // Hellster Wert im Block, aber robust: 90.-Perzentil über ein grobes Raster.
      const werte = [];
      for (let y = by * B; y < Math.min(h, (by + 1) * B); y += 3) {
        for (let x = bx * B; x < Math.min(w, (bx + 1) * B); x += 3) werte.push(g[y * w + x]);
      }
      werte.sort((p, q) => p - q);
      hg[by * bw + bx] = werte[Math.floor(werte.length * 0.9)] || 255;
    }
  }
  // Hintergrund glätten (3 × 3 Maximum, dann 3 × 3 Mittel), damit Schrift nicht als Hintergrund zählt.
  const glatt = (arr, fn) => {
    const r = new Float32Array(arr.length);
    for (let y = 0; y < bh; y += 1) {
      for (let x = 0; x < bw; x += 1) {
        const n = [];
        for (let dy = -1; dy <= 1; dy += 1) {
          for (let dx = -1; dx <= 1; dx += 1) {
            const xx = x + dx;
            const yy = y + dy;
            if (xx >= 0 && yy >= 0 && xx < bw && yy < bh) n.push(arr[yy * bw + xx]);
          }
        }
        r[y * bw + x] = fn(n);
      }
    }
    return r;
  };
  const hgGlatt = glatt(
    glatt(hg, (n) => Math.max(...n)),
    (n) => n.reduce((s, v) => s + v, 0) / n.length,
  );
  const norm = new Float32Array(w * h);
  for (let y = 0; y < h; y += 1) {
    const fy = Math.min(bh - 1, Math.max(0, y / B - 0.5));
    const y0 = fy | 0;
    const y1 = Math.min(bh - 1, y0 + 1);
    const ty = fy - y0;
    for (let x = 0; x < w; x += 1) {
      const fx = Math.min(bw - 1, Math.max(0, x / B - 0.5));
      const x0 = fx | 0;
      const x1 = Math.min(bw - 1, x0 + 1);
      const tx = fx - x0;
      const oben = hgGlatt[y0 * bw + x0] * (1 - tx) + hgGlatt[y0 * bw + x1] * tx;
      const unten = hgGlatt[y1 * bw + x0] * (1 - tx) + hgGlatt[y1 * bw + x1] * tx;
      const hgw = Math.max(40, oben * (1 - ty) + unten * ty);
      norm[y * w + x] = Math.min(1, g[y * w + x] / hgw);
    }
  }
  // Kontrast: dunkelstes Prozent wird schwarz, Papier weiß, leichte Gamma-Kurve für kräftige Schrift.
  const stichprobe = [];
  for (let i = 0; i < norm.length; i += 37) stichprobe.push(norm[i]);
  stichprobe.sort((p, q) => p - q);
  const schwarz = Math.min(0.6, stichprobe[Math.floor(stichprobe.length * 0.01)] || 0);
  const weiss = 0.92;
  const d = bild.data;
  for (let i = 0, j = 0; j < norm.length; i += 4, j += 1) {
    let v = (norm[j] - schwarz) / (weiss - schwarz);
    v = v <= 0 ? 0 : v >= 1 ? 1 : v ** 1.6;
    const px = v * 255;
    d[i] = px;
    d[i + 1] = px;
    d[i + 2] = px;
    d[i + 3] = 255;
  }
  const ziel = canvas(w, h);
  ziel.getContext('2d').putImageData(bild, 0, 0);
  return ziel;
}

// Fertige Seite: entzerren, optional Dokument-Filter.
export function verarbeite(src, ecken, alsDokument, maxKante = ARBEIT_MAX) {
  const gerade = entzerre(src, ecken, maxKante);
  return alsDokument ? dokument(gerade) : gerade;
}

export function alsJpeg(c, qualitaet = 0.82) {
  return new Promise((resolve, reject) => {
    c.toBlob((b) => (b ? resolve(b) : reject(new Error('Bild konnte nicht erzeugt werden.'))), 'image/jpeg', qualitaet);
  });
}
