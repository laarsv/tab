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
