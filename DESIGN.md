# Sync — Design system

A small, self-consistent design system in **royal blue**. Roboto, self-hosted
via `@fontsource/roboto` (no Google Fonts CDN).

## 1. Tokens (`frontend/tailwind.config.js`)

```js
colors: {
  royal: { DEFAULT: '#2947c9', soft: '#aeb9ee' },
  ink:  '#161a24',
  paper:'#ffffff',
}
```

`<meta name="theme-color" content="#2947c9">`.

## 1b. Wortmarke & Bildmarke — VRWB CI v1.0 (verbindlich)

Quelle: „VRWB Corporate Identity.dc.html" (Synology-Ablage `_Ablage/Technisch/Vrwb/VRWB
Markenidentität/`; auch als claude.ai-Design). Konvention für alle vrwb-Tools:

- **Wortmarke = gesetzter Text, immer klein**: `tab` in Roboto **900**,
  Laufweite **−4,5 %** (`tracking-wordmark`). Der Terminal-**Cursor `_` ist das einzige
  grafische Element** und das einzige Royal-Element pro Logo-Anwendung.
- Farbvarianten: auf Paper → Ink + Cursor Royal; **auf Ink → Weiß + Cursor Royal**
  (Login-Hero); auf Royal-Fläche → Weiß + Cursor Royal-Soft.
- **Blink** (`.wordmark-cursor-blink`, 1.2s steps) nur im Hero/Login — nie in der App-Nav.
- **Bildmarke/Favicon**: Anfangsbuchstabe + Cursor (`t_`) weiß/royal-soft auf Royal,
  abgerundetes Quadrat mit Radius ≈ 23 % der Kante (`frontend/public/favicon.svg`).
  Wortmarke und Bildmarke nie nebeneinander doppeln.
- Nie „Tab"/„TAB" setzen, nicht sperren/stauchen, keine Schatten/Verläufe/Outlines.
- Zuordnung zur Dachmarke: Footer/Login „ein Werkzeug von `vrwb_`" (Link auf vrwb.de).

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

- **No native `<select>`** — use the custom `Select` (`components/ui/Select.jsx`),
  keyboard-operable.
- Icons: inline SVG, `stroke-2`, `currentColor` (`components/ui/Icons.jsx`).
  No icon package.
- Modals: `role="dialog"`, `aria-modal`, ESC closes (`components/ui/Modal.jsx`).
- Headings: Roboto **900**, `tracking-tight`; an `.eyebrow` kicker above the H1.
- Responsive: card layout on mobile; nothing scrolls horizontally.
