# vrwb_tab — Design-System (Royal-Blau, VRWB CI v1.0)

Verbindliche Marken- und Farbnorm von **Tab**: Wortmarke **`vrwb_tab`**, Favicon
**`t_`**, Palette **Royal** auf Ink und Paper. Roboto + Roboto Mono, selbst gehostet
über `@fontsource` (kein Google-Fonts-CDN).

## 0. Stand und Bezug zu den anderen Design-Dokumenten

- **Referenz der VRWB-CI** ist `DESIGN.md` im Repo `Suite` (vrwb_suite, Stand
  04.10.2026, Design v3). Tab setzt die Marke nach CI v1.0 und die Dichte-Norm v2
  um (§1–§4). Der v3-Tokensatz der Suite (Canvas-Fläche, `--pos`/`--neg`/`--warn`,
  Schatten- und Radien-Tokens, `--control-height`) ist in Tab **nicht** umgesetzt.
  Abweichungen vom Stand v3, ehrlich gezählt: 7 native `window.confirm`-Dialoge;
  30 Schriftgrößen unter 12 px (`text-[8px]`–`text-[11px]`, u. a. `.eyebrow` mit
  11 px); Überschriften mit −0,01 em statt −0,035 em; Signal- und Grautöne als
  Tailwind-Klassen (`bg-red-600`, `ink/NN`) statt als Tokens. Die Angleichung an
  v3 steht aus.
- **`DESIGN.shared.md`** ist das Fin.Co-Design-System (Mint, Dichte v2) und nur
  als Vorlage übernommen. In Tab gilt es **ausschließlich für Dichte und
  Komponentenmaße** (44 px Touch mobil, kompakt ab `sm:`, `.btn`, `.input`,
  `.field-label`, `.eyebrow`, Dropdown, Modal, Formular-Raster). **Palette,
  Kontrastregel und Marke gelten daraus nicht**: Mint, das Fin.Co-Schwarz und die
  Fin.Co-Wortmarke sind in Tab durch Royal, Ink `#161a24` und `vrwb_tab`
  ersetzt. Bei Widerspruch gewinnt dieses Dokument (Farbe, Kontrast, Marke).

## 1. Tokens (`frontend/tailwind.config.js`)

```js
colors: {
  royal: { DEFAULT: '#2947c9', soft: '#aeb9ee' },
  ink:  '#161a24',
  paper:'#ffffff',
}
```

`<meta name="theme-color" content="#2947c9">`.

## 1b. Wortmarke, Produkt-Lockup & Bildmarke — VRWB CI v1.0 (verbindlich)

Quelle (Source of Truth) der Konvention: claude.ai-Design-Projekt **„VRWB
Markenidentität"** (`VRWB Corporate Identity.dc.html`; das Design-Projekt
gewinnt). Den umgesetzten Stand der CI beschreibt `Suite/DESIGN.md`. Konvention:

- **Wortmarke** `vrwb` = gesetzter Text, **immer klein**, Roboto **900**, Laufweite
  **−4,5 %** (`tracking-wordmark`). Cursor `_` in Royal = einziges grafisches Element.
- **Signatur-Lockup — präferierte Marke im App-Header** (CI-Update; `SignaturLockup`
  in `components/Wordmark.jsx`): handschriftliche **Signatur in Royal** (Pfad aus
  `logo-clean.svg` des Design-Projekts, als **Inline-SVG in `currentColor`** — kein
  CSS-Mask, das rendert nicht überall) + **Haarlinie** (`ink/15`) + rechts der
  **Standalone-Lockup `vrwb_tab`** (keine Subline-Variante im Header).
- **Produkt-Lockup „Standalone"** (`Wordmark`, default): **`vrwb_tab`** — Unterstrich =
  Trenner in Royal, Toolname in **Roboto Mono 500 Royal**, ~0,83× Größe, Laufweite −1 %
  (`tracking-toolname`). Toolnamen immer klein, ein Wort. Einsatz: Login-Hero, Footer,
  Browser-Titel. Auf Ink: `vrwb` weiß, `_tab` in **Royal Soft**.
- **Blink** (`.wordmark-cursor-blink`, 1.2 s steps) nur für den Cursor der puren
  Dachmarken-Wortmarke im Hero (Login-Fußzeile `vrwb_`) — nie im Standalone-Lockup
  (dort ist `_` Trenner, kein Cursor) und nie in der App-Nav.
- **Bildmarke/Favicon**: Anfangsbuchstabe + Cursor (`t_`) weiß/royal-soft auf Royal,
  abgerundetes Quadrat mit Radius ≈ 23 % der Kante (`frontend/public/favicon.svg`).
  Wortmarke und Bildmarke nie nebeneinander doppeln.
- Nie „Tab"/„TAB"/„VRWB" setzen, nicht sperren/stauchen, keine Schatten/Verläufe/Outlines.
- Roboto Mono self-hosted via `@fontsource/roboto-mono` (500), Tailwind `font-mono`.

## 2. Contrast rule (royal blue is a *dark* accent)

- **Foreground on an accent fill = white (`paper`).** White on `#2947c9` ≈ 7.4:1;
  ink on blue ≈ 2.4:1 (fails).
- **Blue is allowed as a text color** (active nav, eyebrow, links, icons) —
  blue on white ≈ 7.4:1.

So: blue buttons/fills use white text, and blue may be used as a text color.

## 3. Building blocks (`frontend/src/index.css`)

- `.btn` + `.btn-primary` (`bg-royal text-paper`), `.btn-outline`, `.btn-danger`,
  `.btn-ghost`, `.btn-sm`.
- `.card` = `rounded-2xl border border-ink/10 bg-paper shadow-sm`.
- `.input`, `.field-label` (`text-xs font-medium text-ink/60`), `.eyebrow`
  (`text-royal`, uppercase).
- Focus ring everywhere: `ring-royal/40`.

## 4. Rules

- **No native `<select>`** — use the custom `Dropdown` (`components/Dropdown.jsx`,
  `variant="ghost"` für Inline-Werte), keyboard-operable.
- Icons: inline SVG, `stroke-2`, `currentColor`, je Komponente inline (keine
  gemeinsame Icon-Datei). No icon package.
- Modals: `role="dialog"`, `aria-modal`, ESC closes (`components/Modal.jsx`).
- Headings: Roboto **900**, `tracking-tight`; an `.eyebrow` kicker above the H1.
- Responsive: card layout on mobile; nothing scrolls horizontally.
