# Fin.Co Design System (portable, Dichte v2)

> **Status:** Verbindliche Quelle der Wahrheit für alle Fin.Co-Tools (Portal, Termin, Marketing, Cockpit, KW-Relay, Tab, künftige Subdomains). Stand **Dichte v2 (Juli 2026)**, verifiziert gegen produktiven Code. Als `DESIGN.md` in jedes Repo legen und in der `CLAUDE.md` referenzieren („UI strikt gemäß DESIGN.md").

---

## Migration von v1 (alte Dichte) — Checkliste

Bestehende Tools auf v1-Stand („44 px überall", bold Labels) kommen so auf diese Norm. Reihenfolge einhalten — Schritt 1 wirkt zentral und sofort überall:

1. **Zentrale Klassen ersetzen** (`index.css`, siehe §7 — 1:1 übernehmen):
   - `.btn`: `px-5 py-2.5` → **`px-3 py-2.5 sm:py-1.5`** (Desktop kompakt, mobil 44 px).
   - `.input`: `px-3 py-2.5 text-base` → **`+ sm:py-1.5 sm:text-sm`** (mobil unverändert — iOS-Zoom-Schutz).
   - **Neu anlegen:** `.btn-sm`, `.btn-ghost` (falls fehlend), `.field-label`, `.eyebrow`.
2. **Select-Komponente**: Standard-Trigger responsive wie `.input`; **`variant="ghost"`** ergänzen (§5.8) inkl. unsichtbarer `before:`-Hitbox und Panel-Mindestbreite 176 px.
3. **Feld-Labels**: alle `block font-bold text-ink/80 mb-1[…]` → **`field-label`** (exakte String-Ersetzung pro Datei, mit Zählung).
4. **Eyebrows**: `text-xs font-bold tracking-tagline text-mint uppercase` → **`eyebrow`**.
5. **Formular-Grids**: `gap-3` / `gap-4` / `gap-x-8 gap-y-3` in Formular-Kontexten → **`gap-x-5 gap-y-2`**.
6. **Karten-Titel**: `text-base sm:text-lg font-black` → **`text-[15px] sm:text-base font-black`** (Titel immer ≥ Control-Größe).
7. **Toggle-Pills**: `py-2.5` → **`py-2.5 sm:py-1.5`**.
8. **Ghost-Select einsetzen**, wo ein Dropdown ein änderbarer Inline-Wert in einer Listen-/Karten-Zeile ist (nicht in Formularen).
9. **Gegenprüfen (Mobile):** Tipp-Felder behalten Base `text-base py-2.5` — der iOS-Zoom-Schutz darf nicht verloren gehen; kompakte Klick-Controls brauchen die 44-px-Hitbox.

Tipp aus der Cockpit-Migration: Schritte 3–7 als kontrollierte exakte String-Ersetzungen pro Datei (Vorher/Nachher-Zählung + Build-Check je Block), kein blindes Repo-sed. Card-Padding-Vereinheitlichung lohnt den Churn nicht — nur opportunistisch angleichen.

---

## 0. Grundhaltung

Dieses System gilt für **alle** Fin.Co-Oberflächen - interne Werkzeuge ebenso wie **kundenseitige** (Termin-Buchung, Marketing). Der Ton folgt der Marke: **warm, transparent, professionell und nahbar** („bei gutem Kaffee, in entspannter Atmosphäre") - ruhig und präzise umgesetzt, ohne laute Effekte. Bei internen Werkzeugen liegt der Schwerpunkt auf Funktion und Dichte, bei kundenseitigen Flächen darf die Markenwärme etwas mehr Raum bekommen - beide nutzen dieselben Tokens und Komponenten. Das Design lebt von wenigen Mint-Akzenten auf Papier-Weiß, klaren Hierarchien (Roboto Black 900 für Headings, Regular 400 für Text) und großzügigen Radien (`rounded-2xl` an Cards). Mobile ist gleichberechtigt: alle Listen haben ein Karten-Fallback, **44 px Touch-Fläche mobil** (Desktop bewusst kompakt - Dichte v2, siehe §3).

Leitprinzipien:
- **Mint sparsam.** Mint ist Akzent, kein Hintergrund. Flächen sind Paper, Linien sind `ink/10` oder `mint-soft/30`.
- **Brutto vor Schmuck.** Buttons haben eine sichtbare Hover-Reaktion, aber keinen Schimmer/Verlauf.
- **Roboto everywhere.** Headings sind Black 900 mit leicht negativer Laufweite, niemals Light.
- **Card als Atom.** Jede in sich abgeschlossene Sektion ist eine `card` (rounded-2xl, ink/10-Border, weißer Hintergrund, Schatten-XS).
- **Inkonsistenz im Code → dominantes Muster gewinnt.** Wo ein Tool historisch zwei Varianten hat, gilt die hier als **Standard** markierte.

---

## 1. Farben

Vier Marken-Tokens + ein kleiner Status-Satz. **Keine** zusätzlichen Grautöne - nutze `ink` mit Alpha (`ink/60`, `ink/10`, …). **Text und Vordergrund auf einer Mint-Fläche sind immer `ink`** (Kontrast/AA), nie weiß - Weiß auf Mint erreicht nur ~3:1.

### Tokens (Tailwind)

| Token | Hex | Brand Manual | Verwendung |
|---|---|---|---|
| `mint` (DEFAULT) | `#00a984` | ✓ Mint | Primär. CTAs, aktive Nav-Items, „.CO" der Wortmarke, Eyebrows, Fokus-Ringe, Erfolg. |
| `mint-soft` | `#86c8af` | ✓ Soft Mint | Sekundär. Card-Tönungen (`bg-mint-soft/10`-`/40`), Header-Border (`/30`), Soft-Pills, Login-Hero-Ovals. |
| `ink` | `#1d1d1b` | ✓ Brand-Schwarz | Text und harte Linien. Nutze **niemals** reines `#000`. Skala über Alpha: `ink/90` Headings, `ink/80` starke Texte, `ink/70` Sub-Text, `ink/60` Hint/Meta, `ink/15` Borders, `ink/10` Trenner, `ink/5` Tabellen-Zeilen. |
| `paper` | `#ffffff` | ✓ Weiß | App-Hintergrund, Card-Fläche. |

### Status / Funktionsfarben

Tailwind-Default-Palette wird minimal hinzugezogen:

| Funktion | Klassen | Beispiel |
|---|---|---|
| **Gefahr / Destruktiv** | `bg-red-600 text-paper` (Buttons), `bg-red-50 border-red-500 text-red-900` (Alerts), `bg-red-100 text-red-800` (sanfte Hinweise) | „Löschen"-Button, abgelehnte Dokumente |
| **Warnung** | `bg-yellow-100 text-yellow-900` | „wartet auf Aktion"-Hinweise |
| **Achtung (Sub-Text)** | `text-amber-700 font-bold` | Inline-Status „wartet auf Rechnungsdaten" |
| **Notification-Dot** | `bg-red-600` (mit `ring-2 ring-paper`) | Header-Badges |

**Brand-Abgleich:** Tokens entsprechen exakt dem Fin.Co Brand Manual 2023 (Mint #00a984, Soft Mint #86c8af, Schwarz #1d1d1b, Weiß #ffffff). Keine Abweichungen.

---

## 2. Typografie

### Font

**Roboto** in fünf Gewichten: 300, 400, 500, 700, 900.

**Standard für alle Tools: Roboto self-hosted** (z. B. via `@fontsource/roboto`). Kein Google-Fonts-CDN - das überträgt die User-IP an Google und widerspricht unserem DSGVO-Anspruch.

> ⚠️ **DSGVO:** Self-Hosting ist verbindlich. Falls ein Bestands-Tool Roboto noch über das Google-Fonts-CDN lädt: umstellen (kleiner Eingriff, siehe §7). Neue Tools starten direkt self-hosted.

Tailwind setzt Roboto als `font-sans`-Default, eine zusätzliche Font-Family-Klasse ist nicht nötig.

### Gewicht-Mapping

| Gewicht | Tailwind | Verwendung |
|---|---|---|
| 300 Light | `font-light` | Tool-Name neben dem Logo im Header. Nur dort. |
| 400 Regular | `font-normal` | Fließtext (Default). |
| 500 Medium | `font-medium` | Feld-Labels (`.field-label`), Tabellenzellen mit leichter Hervorhebung, Ghost-Select-Trigger. |
| 700 Bold | `font-bold` | Sub-Headings, Nav-Items, Eyebrows, Button-Text, Pills. **Das Workhorse-Gewicht.** |
| 900 Black | `font-black` | H1-H4, Wortmarke, Kennzahlen, Modal-Titles. |

### Type-Skala

| Rolle | Klassen |
|---|---|
| Page-Title (H1) | `text-2xl sm:text-3xl font-black tracking-tight` (kompakte Variante) bzw. `text-3xl sm:text-4xl font-black tracking-tight` (Hub/Hero) |
| Section-Title (H2) | `text-lg sm:text-xl font-black` (kompakt) bzw. `text-xl sm:text-2xl font-black tracking-tight` (Hub) |
| Card-Title | `text-[15px] sm:text-base font-black` (Dichte v2 - immer ≥ Control-Größe, nie invertiert) |
| Eyebrow / Kicker | `.eyebrow` = `text-[11px] font-bold tracking-tagline text-mint uppercase` |
| Feld-Label | `.field-label` = `text-xs font-medium text-ink/60 mb-0.5` |
| Body | `text-sm` (Default in App); Formular-Inputs mobil `text-base` (verhindert iOS-Auto-Zoom), ab `sm:` `text-sm` |
| Sub-/Meta-Text | `text-xs text-ink/60 leading-relaxed` |
| Mini-Label (Tabellen-Header, Mini-Eyebrow) | `text-[11px] font-bold tracking-wider text-ink/60 uppercase` bzw. `text-xs uppercase tracking-wider` |
| Wortmarke „FIN.CO" | `font-black tracking-wordmark` (`-0.02em`) |
| Tagline „FINANCE & COFFEE" | `font-bold tracking-tagline` (`0.18em`), kleiner |

Globale Defaults (in `index.css`):
- `html`: `font-family: Roboto, system-ui, sans-serif`, `color: ink`, `background: paper`
- `h1`-`h4`: `font-weight: 900`, `letter-spacing: -0.01em`
- `body`: `antialiased`

---

## 3. Layout

### Container

Alle Seiten leben in einem **zentrierten 1152 px-Container** mit horizontalem Padding:

```html
<div class="mx-auto max-w-6xl px-4 sm:px-6 py-6 sm:py-10">…</div>
```

- `max-w-6xl` = 72 rem = 1152 px
- Header und Footer nutzen denselben Container - der Outer-Background bleibt Paper-weiß über die volle Breite.

### Breakpoints (Tailwind-Default)

| Name | Min-Width | Verwendung |
|---|---|---|
| (Base) | 0 | Mobile-first |
| `sm` | 640 px | Kleinere Tablets, große Phones im Querformat. **Dichte-Cut:** Controls werden kompakt. |
| `md` | 768 px | **Wichtigster Layout-Cut.** Desktop-Nav erscheint, Tabellen werden zu echten Tabellen statt Karten, Modal-Footer wird `sm:flex-row`. |
| `lg` | 1024 px | Mehrspaltige Grids (z. B. 3 Spalten Hub-Kacheln). |

**Mobile-first:** schreibe die Mobile-Variante ohne Präfix, lege Desktop drauf mit `sm:` / `md:` / `lg:`.

### Spacing-Skala (Tailwind-Default)

Standard-Abstände nach Element-Typ:

| Kontext | Abstand |
|---|---|
| Sektion zu Sektion (Page) | `space-y-6` (kompakt) bis `space-y-10` (Hub mit Bereichsblöcken) |
| Inner-Sektion (innerhalb Card) | `space-y-3` bis `space-y-5` |
| Form-Felder zueinander | Formular-Grids `gap-x-5 gap-y-2` (Dichte v2, siehe §5.7); `space-y-3` in einspaltigen Modal-Forms |
| Inline-Items horizontal | `gap-2` (eng) bis `gap-3` (Standard) |
| Tabellen-Spalten-Padding | `px-4 py-3` |
| Card-Padding | **Standard: `p-4`.** Großzügiger (`p-4 sm:p-5`, `p-5 sm:p-6`) nur wo inhaltlich begründet. |

### Dichte-Stufen + Touch-Targets (v2)

**Prinzip: 44 px Touch-FLÄCHE mobil, Desktop kompakt (~32-36 px).** Die frühere Einheitsgröße („44 px überall") ist ersetzt - Desktop-Oberflächen sind dicht, Mobile bleibt tippfreundlich.

| Control | Base (Mobile) | ab `sm:` (Desktop) |
|---|---|---|
| Tipp-Felder (Text/Number/Date/Textarea, `.input`) | `py-2.5 text-base` (≥ 44 px, 16 px verhindert iOS-Zoom) | `sm:py-1.5 sm:text-sm` (~36 px) |
| Select-Trigger (Standard) | wie `.input` | wie `.input` |
| Buttons `md` (`.btn`) | `px-3 py-2.5 text-sm` + `w-full sm:w-auto` | `sm:py-1.5` (~32-36 px) |
| Buttons `sm` (`.btn-sm`) | `px-2.5 py-1 text-xs` (Klick-Control → Hitbox beachten) | dito |
| Ghost-Select (Inline, §5.8) | `px-2 py-1 text-[13px]` + unsichtbare `before:`-Hitbox auf ~44 px | dito |

- **Reine Klick-Controls** (Buttons, Dropdown-Trigger ohne Texteingabe, Toggles, Pills) dürfen auch mobil kompakt sein - die 44-px-Touch-Fläche kommt über eine **unsichtbare Hitbox** (`relative before:absolute before:-inset-y-2 before:inset-x-0` oder `min-h-[44px]`-Wrapper bzw. `w-full` auf Mobile), **nicht** über Riesenoptik.
- **Tipp-Felder** dagegen NIE unter `text-base` auf Base-Breakpoint (iOS-Zoom-Schutz).
- **Icon-Buttons:** `p-2` Mindest-Padding um SVG `h-5 w-5` oder `h-6 w-6`.
- **Modal-Footer auf Mobile:** `flex flex-col-reverse sm:flex-row sm:justify-end gap-2` - Primary erscheint unten/rechts auf Mobile (Daumenreichweite) und oben/rechts auf Desktop.

---

## 4. Radius / Borders / Schatten

### Border-Radius

| Klasse | Wert | Verwendung |
|---|---|---|
| `rounded` | 4 px | Checkbox-Box, Alerts. |
| `rounded-md` | 6 px | Tab-Pills, Nav-Items, Logout-Items im Drawer, Toggle-Buttons in Forms. |
| `rounded-lg` | 8 px | **Standard für Buttons und Inputs.** |
| `rounded-2xl` | 16 px | **Alle Cards.** Großzügig, ruhig. |
| `rounded-full` | ∞ | Pills, Badges, Avatars, Status-Dots, Progress-Track. |

### Borders

- **Card-Outline:** `border border-ink/10` (Standard, neutral).
- **Card-Hover-Outline:** `hover:border-mint/50` (Hub-Tiles).
- **Header-Trenner:** `border-b border-mint-soft/30` (markenfarbig, ruhig).
- **Tabelle-Header-Trenner:** `border-b border-ink/10`.
- **Tabelle-Zeilen-Trenner:** `border-b border-ink/5 last:border-b-0` (extrem subtil).
- **Input-Border:** `border border-ink/20` (Standard, ein Hauch dunkler als Card-Border, damit das Feld sichtbar als Feld erkennbar ist).
- **Tab-Underline:** `border-b-2 border-mint` (aktiv) / `border-transparent` (inaktiv).

### Schatten

Drei Stufen, sparsam:

| Klasse | Verwendung |
|---|---|
| `shadow-sm` | Standard für Cards und Primary-Buttons (kaum sichtbar, schwebt nur dezent). |
| `shadow-lg` | Login-Haupt-CTA. |
| `shadow-xl` | Mobile-Drawer (klare Trennung von der unterliegenden Seite). |

Keine farbigen Schatten, keine inneren Schatten.

---

## 5. Komponenten

### 5.1 Header / Navigation

Sticky-fähiger Header, ein Container, drei Bereiche: Logo (links), Nav (Desktop) bzw. Burger (Mobile, rechts), User-Menü ganz rechts (Desktop).

```html
<header class="bg-paper border-b border-mint-soft/30">
  <div class="mx-auto max-w-6xl px-4 sm:px-6 h-16 flex items-center justify-between gap-3">
    <a href="/" class="flex items-center min-w-0">
      <img src="/logo_icon.svg" alt="Fin.Co" class="h-10 sm:h-12 w-auto shrink-0" />
      <span class="ml-2 sm:ml-3 text-base sm:text-xl font-light text-ink/60 truncate">
        Toolname <!-- Tool-Name in font-light -->
      </span>
    </a>

    <!-- Desktop-Nav ab md -->
    <nav class="hidden md:flex items-center gap-2">
      <!-- NavLink-Pattern -->
      <a class="px-3 py-1.5 rounded-md text-sm font-bold transition text-ink/70 hover:text-ink">Start</a>
      <a class="px-3 py-1.5 rounded-md text-sm font-bold transition text-mint">Aktiv</a>
    </nav>

    <!-- Burger ab unter md -->
    <button class="md:hidden p-2 -mr-2 rounded-md hover:bg-mint/10 text-ink/80">
      <!-- SVG Burger (3 Linien) -->
    </button>
  </div>
</header>
```

**Aktiv-State:** `text-mint` (kein Background, kein Underline). Hover: `text-ink/70 → text-ink`.

**Tool-Name neben Logo:** `font-light text-ink/60` - bewusst leise, damit das Logo dominiert.

**Zweistufige Nav (optional, bei > ~6 gleichrangigen Items):** Ebene 1 kurz halten; eine Gruppe von Detail-Modulen wandert in eine **dezente zweite Underline-Tab-Leiste** direkt unter dem Header (`border-t border-mint-soft/20`, Tabs `py-2.5 text-sm font-bold`, aktiv `text-mint border-b-2 border-mint`, inaktiv `text-ink/60 border-transparent hover:text-ink`, `overflow-x-auto`). Die Unterleiste rendert **nur**, wenn die aktuelle Route zur Gruppe gehört - sonst bleibt der Header einzeilig. Das Gruppen-Item in Ebene 1 verlinkt aufs erste Modul der Gruppe und ist aktiv-markiert, sobald irgendein Gruppen-Modul offen ist.

### 5.2 Mobile-Drawer

Slide-in von rechts mit Body-Scroll-Lock. Wird unter `md:` ausgelöst.

```html
<div role="dialog" aria-modal="true" class="fixed inset-0 z-50 md:hidden">
  <!-- Overlay -->
  <button class="absolute inset-0 bg-ink/60 backdrop-blur-sm transition-opacity duration-200" />
  <!-- Drawer -->
  <aside class="absolute top-0 right-0 h-full w-[85%] max-w-xs bg-paper shadow-xl flex flex-col
                transform transition-transform duration-200 translate-x-0">
    <!-- Header (Avatar + Schließen-Button) -->
    <div class="flex items-center justify-between px-4 py-3 border-b border-ink/10">…</div>
    <!-- Nav (scrollbar) -->
    <nav class="flex-1 overflow-y-auto py-2">
      <a class="flex items-center justify-between px-4 py-3 text-sm font-bold transition
                text-ink hover:bg-mint/10">Item</a>
      <a class="flex items-center justify-between px-4 py-3 text-sm font-bold transition
                text-mint bg-mint-soft/10">Aktiv</a>
    </nav>
    <!-- Footer (Logout) -->
    <div class="border-t border-ink/10 p-2">…</div>
  </aside>
</div>
```

Verhalten:
- Schließt bei ESC, Overlay-Klick und Route-Wechsel.
- Slide-Transition über `translate-x-full → translate-x-0`, getriggert via `requestAnimationFrame` nach Mount.
- `document.body.style.overflow = 'hidden'` während offen.
- Nav-Gruppen (falls zweistufige Nav): eingerückte Sektion mit Mini-Label (`px-4 pt-3 pb-1 text-[11px] font-black uppercase tracking-wider text-ink/40`) + Unterpunkte `pl-8`.

### 5.3 Cards

```html
<section class="card p-4 flex flex-col gap-3 h-full">
  <div>
    <h2 class="text-[15px] sm:text-base font-black">Titel</h2>
    <p class="text-xs text-ink/60 mt-0.5">Optionaler Hint.</p>
  </div>
  <div class="flex-1"><!-- Content --></div>
  <div><!-- Footer mit CTA(s) --></div>
</section>
```

`.card`-Utility (in `index.css`):
```css
.card { @apply rounded-2xl border border-ink/10 bg-paper shadow-sm; }
```

**Card-Variante getönt:** `bg-mint-soft/10 rounded-2xl p-8` - für ruhige Hinweis-Sektionen, kein Border.

**Card im Grid:** Für gleichmäßige Höhen `h-full flex flex-col` plus `flex-1` auf dem Content, dann sitzt der Footer in jeder Grid-Zeile gleich.

### 5.4 Hub-Kacheln

Dichte Klick-Kacheln für „Hub"-Seiten (Verwaltung, Tool-Übersicht, Dashboard-Schnellzugriff).

```html
<a class="card group p-4 border border-mint-soft/30
          hover:border-mint/50 hover:bg-mint-soft/10
          transition flex flex-col gap-1 relative">
  <div class="flex items-start justify-between gap-2">
    <div class="eyebrow">Eyebrow</div>
    <!-- Optional: Badge (Notification-Count) oder Externer-Link-Pfeil ↗ -->
  </div>
  <div class="text-[15px] sm:text-base font-black text-ink group-hover:text-mint transition">
    Titel
  </div>
  <div class="text-xs text-ink/60 leading-relaxed">Beschreibung in einer Zeile.</div>
</a>
```

Grid: `grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3`.

### 5.5 Buttons

**Standard-Komponente** mit Variante + Size. Basis-Klassen:

```
inline-flex items-center justify-center rounded-lg font-bold transition
focus:outline-none focus:ring-2 focus:ring-mint/40
disabled:opacity-50 disabled:cursor-not-allowed
```

#### Varianten

| Variante | Klassen |
|---|---|
| `primary` (Standard) | `bg-mint text-ink hover:bg-mint/90 shadow-sm` |
| `secondary` / `outline` | `border border-ink/20 text-ink hover:bg-ink/5 bg-paper` |
| `danger` | `bg-red-600 text-paper hover:bg-red-700 shadow-sm` |
| `ghost` | `text-ink hover:bg-ink/5` |

#### Größen (Dichte v2)

| Size | Klassen |
|---|---|
| `sm` (`.btn-sm`) | `px-2.5 py-1 text-xs` |
| `md` (Standard, `.btn`) | `px-3 py-2.5 sm:py-1.5 text-sm` (mobil 44-px-tauglich, Desktop ~32-36 px) |
| `lg` (sparsam, Hero-CTAs) | `px-6 py-3 text-base` |

Auf Mobile: `className="w-full sm:w-auto"` ergänzen, damit der Button volle Breite hat. Modal-Footer-Pattern: `flex flex-col-reverse sm:flex-row sm:justify-end gap-2`.

**Buttons mit Icon (sekundäre „+"-Aktionen):** inline-SVG (Stroke-2) `h-3.5 w-3.5` + kurzer Text `text-[13px]`, Padding `py-1.5 px-3`:
```html
<button class="btn-outline gap-1.5 text-[13px]">
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
       class="h-3.5 w-3.5"><path d="M12 5v14M5 12h14"/></svg>
  Hinzufügen
</button>
```

### 5.6 Chips / Pills / Badges

Drei Größen, ein Pattern.

**Status-Pill (Standard, mit Dot):**
```html
<span class="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-bold
             bg-mint text-ink">
  <span class="h-1.5 w-1.5 rounded-full bg-ink"></span>
  Läuft
</span>
```
Inaktiver Status: `bg-mint-soft/40 text-ink` mit Dot `bg-ink/50`.

**Sanfte Pill (ohne Dot):**
```html
<span class="inline-flex items-center px-3 py-1 rounded-full bg-mint-soft/40 text-ink
             text-sm font-bold tabular-nums">
  12 Stück
</span>
```

**Mini-Pill / Badge (Dichte v2 - Standard in Listen/Karten):**
```html
<span class="inline-flex items-center rounded-full bg-mint px-2 py-0.5
             text-[10px] font-bold uppercase tracking-wider text-ink">
  Aktiv
</span>
```

**Notification-Count-Badge:**
```html
<span class="ml-2 inline-flex items-center justify-center min-w-[20px] h-5 px-1.5
             rounded-full bg-red-600 text-paper text-[11px] font-black tabular-nums">
  3
</span>
```

**Notification-Dot (ohne Zahl, z. B. an Header-Icon):**
```html
<span class="absolute -top-0.5 -right-0.5 h-2 w-2 rounded-full bg-red-600 ring-2 ring-paper"></span>
```

### 5.7 Inputs (Text, Number, Date)

**Standard (Dichte v2, responsive):**
```html
<label class="block text-sm">
  <span class="field-label">Label</span>
  <input
    type="text"
    class="w-full border border-ink/20 rounded-lg px-3 py-2.5 text-base bg-paper
           sm:py-1.5 sm:text-sm
           focus:border-mint focus:ring-2 focus:ring-mint/30 outline-none"
  />
  <span class="block text-xs text-ink/60 mt-1">Optionaler Hilfetext.</span>
</label>
```

- **Feld-Label** = `.field-label` (`text-xs font-medium text-ink/60 mb-0.5`) - dezent, nicht bold. Die alte `font-bold text-ink/80`-Variante ist abgelöst.
- Mobil `text-base` (16 px, verhindert iOS-Auto-Zoom) + `py-2.5` (≥ 44 px Touch). Ab `sm:` kompakt (`py-1.5 text-sm`, ~36 px) - Desktop ist dicht.
- Fehler-State: `border-red-400` ersetzen - kein zusätzliches Icon nötig.

#### Formular-Dichte (Grids, Karten, Sektionen)

- **Formular-Grid:** `grid grid-cols-1 md:grid-cols-2 gap-y-2 gap-x-5` (eng; zusammengehörige Felder nebeneinander, Textareas `md:col-span-2`).
- **Card-Padding Standard:** `p-4` (großzügiger nur wo inhaltlich begründet).
- **Karten-Titel:** `text-[15px] sm:text-base font-black` - Titel ist immer ≥ Control-Größe, nie invertiert.
- **Sektions-Header:** Inline-SVG-Icon 14 px (`h-3.5 w-3.5`, Stroke-2) + `.eyebrow` (`text-[11px] font-bold tracking-tagline text-mint uppercase`) + Trenner `border-b border-ink/10` darunter. Trenner statt Leerraum zwischen Karten-Sektionen.
- **Zahlen:** immer `tabular-nums`; Einheiten (€/%/„/M") gedämpft `text-ink/50`.
- **Badges/Mini-Pills:** `text-[10px] font-bold tracking-wide px-2 py-0.5 rounded-full`.

### 5.8 Selects / Dropdowns

**Kein natives `<select>`.** Selects werden als **Custom-Dropdown** gebaut - Trigger und aufgeklappte Liste sind beide gestylt, damit nichts „old school" wirkt. Zwei Trigger-Varianten:

**Standard (Feld-Optik, Formular-Kontext):** Trigger sieht aus wie ein Input (gleiche Border/Radien/Höhe, responsive Dichte wie §5.7).
```html
<button type="button" aria-haspopup="listbox" aria-expanded="false"
        class="w-full flex items-center justify-between gap-2 border border-ink/20 rounded-lg
               px-3 py-2.5 text-base sm:py-1.5 sm:text-sm bg-paper text-left
               focus:border-mint focus:ring-2 focus:ring-mint/30 outline-none">
  <span class="truncate">Gewählte Option</span>
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
       class="h-4 w-4 shrink-0 text-ink/60"><path d="M6 9l6 6 6-6"/></svg>
</button>
```

**Ghost-Select (Inline-Wert-Variante):** für Dropdowns **in Listen-/Karten-Zeilen** (z. B. ein änderbarer Status oder eine Zuordnung direkt in einer Zeile). Regel: **Ghost = änderbarer Wert in einer Zeile; volle Feld-Optik nur in Formular-Kontexten** (Stammdaten-Formulare, Modals, Eingabe-Cards).
```html
<button type="button" aria-haspopup="listbox" aria-expanded="false"
        class="relative flex items-center justify-between gap-1.5 border border-transparent rounded-lg
               px-2 py-1 text-[13px] font-medium bg-ink/[0.04] hover:bg-ink/[0.07] text-left
               before:absolute before:-inset-y-2 before:inset-x-0 before:content-['']
               focus:border-mint focus:ring-2 focus:ring-mint/30 outline-none">
  <span class="truncate">Behalten</span>
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
       class="h-3.5 w-3.5 shrink-0 text-ink/60"><path d="M6 9l6 6 6-6"/></svg>
</button>
```
Die unsichtbare `before:`-Hitbox hebt die Touch-Fläche auf ~44 px, ohne die Optik aufzublasen. Ghost-Trigger sind content-breit (kein `w-full`).

**Options-Panel (beide Varianten identisch):**
```html
<ul role="listbox"
    class="absolute z-50 mt-1 w-full max-h-64 overflow-auto rounded-lg border border-ink/10
           bg-paper shadow-lg py-1">
  <li role="option" aria-selected="true"
      class="px-3 py-2 text-sm cursor-pointer flex items-center justify-between
             bg-mint-soft/20 text-ink">
    Option A
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
         class="h-4 w-4 text-mint"><path d="M20 6L9 17l-5-5"/></svg>
  </li>
  <li role="option" class="px-3 py-2 text-sm cursor-pointer text-ink hover:bg-mint/10">Option B</li>
</ul>
```

Panel-Breite = Trigger-Breite; beim Ghost-Select (content-breiter Trigger) mindestens **176 px**, damit Options-Labels nicht truncaten.

Verhalten/A11y: per Tastatur bedienbar (↑/↓ navigiert, Enter wählt, Esc schließt), `aria-haspopup="listbox"` + `aria-expanded`, aktive Option `aria-selected`, Klick außerhalb schließt. Gilt **für alle** Auswahlfelder (Formulare ebenso wie User-/Action-Menüs); Action-/Kontext-Menüs nutzen denselben Panel-Stil mit Items als `block px-4 py-2 text-sm hover:bg-mint/10 text-ink`.

### 5.9 Checkboxen

```html
<label class="flex items-center gap-2 text-sm">
  <input type="checkbox" class="rounded border-ink/30 text-mint focus:ring-mint" />
  <span>Beschriftung</span>
</label>
```

Tailwind-Forms-Plugin wird **nicht** verwendet - die native Checkbox bekommt nur `text-mint` für die Akzentfarbe und `focus:ring-mint`.

### 5.10 Toggle-Pills (statt Radio-Group)

Für „eine aus N"-Auswahl mit visueller Präsenz (z. B. Kategorie, Wochentage):

```html
<div class="grid grid-cols-1 sm:grid-cols-3 gap-2">
  <button type="button"
          class="rounded-md px-4 py-2.5 sm:py-1.5 text-sm font-bold border transition text-left
                 bg-mint-soft/30 border-mint"><!-- aktiv -->
    Externe
  </button>
  <button type="button"
          class="rounded-md px-4 py-2.5 sm:py-1.5 text-sm font-bold border transition text-left
                 bg-paper border-ink/15 hover:border-mint"><!-- inaktiv -->
    Kunden / Freunde
  </button>
</div>
```

Dichte v2: mobil `py-2.5` (Touch), ab `sm:` kompakt `py-1.5`.

### 5.11 Tabs

Underline-Tabs, kein Background-Wechsel.

```html
<div class="border-b border-ink/10 mb-6">
  <nav class="flex gap-6 -mb-px">
    <button class="pb-3 px-1 text-sm font-bold transition border-b-2
                   text-mint border-mint"><!-- aktiv -->
      Vorgänge
      <span class="ml-2 inline-flex items-center justify-center min-w-[1.25rem] px-1.5
                   rounded-full bg-ink/10 text-ink/70 text-xs font-bold">12</span>
    </button>
    <button class="pb-3 px-1 text-sm font-bold transition border-b-2
                   text-ink/60 border-transparent hover:text-ink">
      Preise &amp; Settings
    </button>
  </nav>
</div>
```

### 5.12 Tabellen / Listen

**Standard für Desktop:** Tabelle in einer Card-Hülle mit horizontalem Scroll-Schutz.

```html
<div class="hidden md:block overflow-x-auto card">
  <table class="w-full text-sm">
    <thead class="text-left text-ink/60 text-xs uppercase tracking-wider">
      <tr class="border-b border-ink/10">
        <th class="px-4 py-3">Spalte</th>
        <th class="px-4 py-3 text-right">Betrag</th>
      </tr>
    </thead>
    <tbody>
      <tr class="border-b border-ink/5 last:border-b-0">
        <td class="px-4 py-3 font-medium">Wert</td>
        <td class="px-4 py-3 text-right tabular-nums">12,34&nbsp;€</td>
      </tr>
    </tbody>
  </table>
</div>
```

**Mobile-Pendant:** Tabelle wird zu einer Karten-Liste. **Standard-Pattern** für jede neue Tabelle:

```html
<!-- Mobile -->
<div class="md:hidden space-y-3">
  <div class="card p-4 space-y-3">
    <!-- Eine "Zeile" als Card mit Sub-Items -->
  </div>
</div>

<!-- Desktop -->
<div class="hidden md:block overflow-x-auto card">
  <table class="w-full text-sm">…</table>
</div>
```

Zahlen immer mit `tabular-nums`. Datums-/Meta-Spalten in `text-ink/70 text-xs`.

### 5.13 Empty States

Innerhalb einer Card, zentriert, ruhig:

```html
<div class="card p-12 text-center text-ink/60">
  Keine Einträge für den aktuellen Filter.
</div>
```

Inline-Empty (im Card-Body): getönter Block mit Link-CTA:
```html
<div class="rounded-lg bg-mint-soft/10 p-3 text-sm text-ink/70">
  Aktuell läuft keine Aktion.
  <a class="text-mint font-bold hover:underline">Zur Übersicht →</a>
</div>
```

### 5.14 Modals

Vollflächiges Overlay + zentrierte Card mit Mount-Transition (Opacity + Scale).

```html
<div role="dialog" aria-modal="true"
     class="fixed inset-0 z-50 backdrop-blur-sm flex items-center justify-center p-4
            bg-ink/60 transition-opacity duration-200 opacity-100">
  <form class="card max-w-lg w-full p-6 space-y-4
               transform transition-all duration-200 opacity-100 scale-100">
    <h2 class="text-xl font-black">Titel</h2>
    <!-- Eyebrow-Pattern für Edit-Modals: -->
    <!-- <p class="eyebrow">Eintrag bearbeiten</p>
         <h2 class="mt-1 text-xl font-black">Name</h2> -->

    <div class="grid grid-cols-1 sm:grid-cols-2 gap-x-5 gap-y-2"><!-- Felder --></div>

    <div class="flex flex-col-reverse sm:flex-row sm:justify-end gap-2 pt-2">
      <button class="btn-ghost">Abbrechen</button>
      <button class="btn-primary">Speichern</button>
    </div>
  </form>
</div>
```

- Mount-Transition: starte mit `opacity-0 scale-95`, setze nach `requestAnimationFrame` auf `opacity-100 scale-100`.
- Schließbar via ESC + Backdrop-Klick (kein Mock-X - der Cancel-Button im Footer ist die primäre Aktion).
- Mobile: Footer dreht sich um (`flex-col-reverse`) - Primary unten/groß.

### 5.15 Toasts

`react-hot-toast` mit globalem Theme. **Position:** `top-right`. **Duration:** 4000 ms.

```js
<Toaster
  position="top-right"
  toastOptions={{
    duration: 4000,
    style: {
      background: '#1d1d1b',
      color: '#ffffff',
      fontFamily: 'Roboto, sans-serif',
      borderRadius: '12px',
      padding: '12px 16px',
      fontSize: '14px',
    },
    success: { iconTheme: { primary: '#00a984', secondary: '#1d1d1b' } },
    error: {
      style: {
        background: '#dc2626',
        color: '#ffffff',
        fontFamily: 'Roboto, sans-serif',
        borderRadius: '12px',
        padding: '12px 16px',
        fontSize: '14px',
      },
    },
  }}
/>
```

### 5.16 Alerts (Inline-Hinweisbalken auf Seiten)

Drei Varianten mit Left-Border-Akzent. Schließbar.

```html
<!-- error -->
<div class="p-4 rounded flex items-start justify-between gap-4
            bg-red-50 border-l-4 border-red-500 text-red-900">…</div>

<!-- success -->
<div class="p-4 rounded flex items-start justify-between gap-4
            bg-mint/10 border-l-4 border-mint text-ink">…</div>

<!-- info -->
<div class="p-4 rounded flex items-start justify-between gap-4
            bg-mint-soft/15 border-l-4 border-mint-soft text-ink">…</div>
```

### 5.17 Avatar

```html
<!-- Mit Bild -->
<img class="w-10 h-10 text-sm rounded-full object-cover ring-2 ring-mint/30"
     referrerpolicy="no-referrer" />

<!-- Fallback (Initialen) -->
<div class="w-10 h-10 text-sm rounded-full bg-mint text-ink font-bold
            flex items-center justify-center ring-2 ring-mint/30">LV</div>
```

Größen: `sm = w-8 h-8 text-xs`, `md = w-10 h-10 text-sm`, `lg = w-16 h-16 text-lg`.

### 5.18 Spinner / Loading

```html
<span role="status" aria-label="Lädt…"
      class="inline-block animate-spin rounded-full
             border-2 border-mint/30 border-t-mint h-6 w-6"></span>
```

Größen: `sm = h-4 w-4 border-2`, `md = h-6 w-6 border-2`, `lg = h-10 w-10 border-[3px]`.

### 5.19 Skeleton

```html
<div class="animate-pulse bg-mint-soft/20 rounded h-4 w-3/4"></div>
```

Drei Aspekte: `bg-mint-soft/20`, `rounded`, `animate-pulse`. Maße nach Inhalt anpassen. Für Tabellen: gleiche `<table>`-Struktur mit Skeleton-Cells.

### 5.20 Progress-Bar

```html
<div class="space-y-1">
  <div class="flex justify-between text-xs text-ink/60 font-bold tracking-wider uppercase">
    <span>Fortschritt</span>
    <span class="tabular-nums">3 / 5</span>
  </div>
  <div class="h-2 rounded-full bg-mint-soft/30 overflow-hidden">
    <div class="h-full bg-mint transition-all" style="width: 60%"
         role="progressbar" aria-valuenow="3" aria-valuemin="0" aria-valuemax="5"></div>
  </div>
</div>
```

### 5.21 Icon-Set

**Keine Icon-Library.** Icons sind inline-SVGs mit:

```html
<svg viewBox="0 0 24 24" fill="none" stroke="currentColor"
     stroke-width="2" stroke-linecap="round" stroke-linejoin="round"
     class="h-5 w-5" aria-hidden="true">
  <!-- minimaler Pfad / Linien -->
</svg>
```

Konventionen:
- `viewBox="0 0 24 24"`, `fill="none"`, `stroke="currentColor"`, `stroke-width="2"`.
- Runde Linien-Enden.
- Größen: `h-3.5 w-3.5` (Sektions-Header, Icon-Buttons, Ghost-Chevron), `h-4 w-4` (Standard-Select-Chevron, kleine Aktions-Icons), `h-5 w-5` (in Buttons / neben Text), `h-6 w-6` (Header-Burger), `h-10 w-10` (Hero-Akzent - selten).
- Farbe immer per `currentColor` aus dem Parent-Text.
- Pfeile in Text: einfaches Unicode `→` / `↗` statt SVG.

### 5.22 Login-Hero (Marken-Akzent)

Dunkler Hintergrund mit zwei Soft-Mint-Ovals als Background-Glow:

```html
<div class="relative min-h-screen bg-ink overflow-hidden flex items-center justify-center">
  <div class="pointer-events-none absolute -top-32 -left-32 h-[520px] w-[820px]
              rounded-[50%] bg-mint-soft/25 blur-2xl"
       style="transform: rotate(-40deg)"></div>
  <div class="pointer-events-none absolute -bottom-40 -right-40 h-[420px] w-[680px]
              rounded-[50%] bg-mint/15 blur-3xl"
       style="transform: rotate(-40deg)"></div>
  <div class="relative z-10 w-full max-w-md px-4 sm:px-8 py-12 text-center">
    <!-- Wordmark + CTA -->
    <button class="mt-8 inline-flex w-full items-center justify-center
                   rounded-lg bg-mint px-6 py-3 text-base font-bold text-ink
                   shadow-lg transition hover:bg-mint/90">…</button>
  </div>
</div>
```

Nur für die Login-Seite. Alle anderen Seiten sind Paper-weiß.

---

## 6. Do / Don't

### Do

- ✅ Cards mit `rounded-2xl` + `border-ink/10` + `shadow-sm`. Inhalte mit `p-4` (Standard).
- ✅ Mint **nur** als Akzent (CTA, aktive Nav, Eyebrow, Status). Flächen bleiben Paper.
- ✅ **Text/Vordergrund auf Mint = `ink`** (schwarz), nie weiß - Kontrast/AA.
- ✅ Selects als **Custom-Dropdown** (Trigger + gestylte Options-Liste, tastaturbedienbar) - kein natives `<select>`. Ghost-Variante für Inline-Werte in Zeilen.
- ✅ Roboto Black 900 für H1-H4, Bold 700 für Buttons/Pills/Nav, Medium 500 für Feld-Labels, Regular 400 für Body.
- ✅ **44 px Touch-FLÄCHE mobil, Desktop kompakt** (Dichte v2): Tipp-Felder mobil `py-2.5 text-base`, ab `sm:` `py-1.5 text-sm`; Buttons `.btn` mit `w-full sm:w-auto` auf Mobile; kompakte Klick-Controls (Ghost-Select, `.btn-sm`) mit unsichtbarer `before:`-Hitbox.
- ✅ Feld-Labels `.field-label` (`text-xs font-medium text-ink/60 mb-0.5`) - nicht mehr bold/ink-80.
- ✅ Form-Inputs einheitlich: `border-ink/20`, `rounded-lg`, Fokus `border-mint + ring-mint/30`.
- ✅ Tabellen haben **immer** ein Mobile-Karten-Pendant.
- ✅ Modal-Footer auf Mobile `flex-col-reverse` - Primary unten/groß.
- ✅ Notification-Badges in `bg-red-600 text-paper text-[11px] font-black tabular-nums`.
- ✅ Pills immer `rounded-full`, Größenstaffel `text-[10px]` < `text-xs` < `text-sm`.
- ✅ Zahlen `tabular-nums`, Einheiten (€/%) gedämpft `text-ink/50`.
- ✅ Mint-Soft-Tönungen mit Alpha: `bg-mint-soft/10` (sehr ruhig) → `/30` (Borders) → `/40` (sanfte Pills).

### Don't

- ❌ Kein weißer Text auf Mint - Text auf Mint ist immer `ink`.
- ❌ Kein natives `<select>` - immer Custom-Dropdown (auch die offene Liste gestylt).
- ❌ Kein reines `#000` - immer `ink` (`#1d1d1b`).
- ❌ Keine Grau-Skala aus Tailwind-Defaults - nutze `ink/N`-Alphas.
- ❌ Keine Riesenoptik als Touch-Ersatz - 44 px kommen mobil aus Basis-Padding bzw. unsichtbarer Hitbox, nicht aus aufgeblasenen Desktop-Controls.
- ❌ Tipp-Felder nie unter `text-base` auf dem Base-Breakpoint (iOS-Zoom).
- ❌ Kein Karten-Titel kleiner als die Controls daneben (invertierte Hierarchie).
- ❌ Keine inneren oder farbigen Schatten. Nur `shadow-sm`, `shadow-lg`, `shadow-xl`.
- ❌ Keine zweite Schriftart. Keine Serifs, kein Mono (außer für Code-Blöcke in MD-Renderern).
- ❌ Keine Light-Schrift im Body - Light 300 ausschließlich für den Tool-Namen neben dem Logo.
- ❌ Keine Icons aus Heroicons / Lucide / FontAwesome - inline-SVG mit Stroke-2.
- ❌ Keine bunten Status-Backgrounds - Mint / Mint-Soft / Red-50 / Yellow-100 reichen.
- ❌ Kein Tailwind-Forms-Plugin nötig - native Inputs mit Utility-Klassen genügen.
- ❌ Kein `@tailwindcss/typography`-Plugin (Prose-Styles werden manuell mit `prose prose-sm` Approximation gebaut).
- ❌ Keine Dialoge ohne Close-via-ESC und ohne `role="dialog" aria-modal="true"`.
- ❌ Kein Modal ohne Mount-Transition (`opacity-0 scale-95 → opacity-100 scale-100`, 200 ms).

---

## 7. Tailwind-Config + Font-Einbindung

### `tailwind.config.js`

```js
/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx,ts,tsx}'],
  theme: {
    extend: {
      colors: {
        mint: {
          DEFAULT: '#00a984',
          soft: '#86c8af',
        },
        ink: '#1d1d1b',
        paper: '#ffffff',
      },
      fontFamily: {
        sans: ['Roboto', 'system-ui', 'sans-serif'],
      },
      letterSpacing: {
        wordmark: '-0.02em',
        tagline: '0.18em',
      },
    },
  },
  plugins: [],
};
```

### `postcss.config.js`

```js
export default {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
};
```

### `index.css` (Tailwind-Entry + Globals + Utilities) — Dichte v2, 1:1 übernehmen

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

@layer base {
  html {
    font-family: 'Roboto', system-ui, sans-serif;
    color: theme('colors.ink');
    background: theme('colors.paper');
  }
  html, body, #root { height: 100%; }
  body { @apply antialiased; }
  h1, h2, h3, h4 {
    font-weight: 900;
    letter-spacing: -0.01em;
  }
}

@layer components {
  /* Dichte-Norm v2: mobil 44px-Touch (py-2.5), ab sm: kompakt (~32-36px). */
  .btn {
    @apply inline-flex items-center justify-center rounded-lg px-3 py-2.5 sm:py-1.5 text-sm font-bold
           transition focus:outline-none focus:ring-2 focus:ring-mint/40
           disabled:opacity-50 disabled:cursor-not-allowed;
  }
  .btn-primary { @apply btn bg-mint text-ink hover:bg-mint/90 shadow-sm; }
  .btn-outline { @apply btn border border-ink/20 bg-paper text-ink hover:bg-ink/5; }
  .btn-ghost   { @apply btn text-ink hover:bg-ink/5; }
  /* Mini-Sekundäraktion, zusätzlich zu .btn-* (NACH den Varianten definiert,
     damit sie im Cascade gewinnt: class="btn-outline btn-sm"). */
  .btn-sm      { @apply px-2.5 py-1 text-xs; }
  .card        { @apply rounded-2xl border border-ink/10 bg-paper shadow-sm; }
  /* Tipp-Felder: mobil text-base (iOS-Zoom-Schutz) + py-2.5 (44px), Desktop dicht. */
  .input {
    @apply w-full border border-ink/20 rounded-lg px-3 py-2.5 text-base bg-paper
           sm:py-1.5 sm:text-sm
           focus:border-mint focus:ring-2 focus:ring-mint/30 outline-none;
  }
  /* Formular-Dichte v2 */
  .field-label { @apply block text-xs font-medium text-ink/60 mb-0.5; }
  .eyebrow     { @apply text-[11px] font-bold tracking-tagline text-mint uppercase; }
}
```

> Hinweis Tailwind-Purge: `@layer components`-Klassen werden nur ins Bundle aufgenommen, wenn sie in gescannten Quelldateien vorkommen. `.field-label`/`.btn-sm`/`.eyebrow` erscheinen also erst nach der ersten Verwendung - kein Bug.

### Font-Einbindung

**Standard (self-hosted, DSGVO-konform) - für alle Tools:**

```bash
npm install @fontsource/roboto
```

```js
// im JS-Entry (z. B. main.jsx)
import '@fontsource/roboto/300.css';
import '@fontsource/roboto/400.css';
import '@fontsource/roboto/500.css';
import '@fontsource/roboto/700.css';
import '@fontsource/roboto/900.css';
```

Die Tailwind-Config bleibt unverändert (`font-sans` = Roboto). Kein `<link>` auf Google-Fonts.

**Falls ein Bestands-Tool Roboto noch per Google-Fonts-CDN lädt** (`<link>` auf `fonts.googleapis.com` / `fonts.gstatic.com` in `index.html`): diesen Block entfernen und durch das `@fontsource`-Setup oben ersetzen.

### Meta / Theme-Color

```html
<meta name="theme-color" content="#00a984" />
```

- Mint als Mobile-Browser-Chrome-Farbe.

### Favicon / Logo

- `public/favicon.svg` - vereinfachte Drei-Tropfen-Marke.
- `public/logo_icon.svg` - volle Drei-Tropfen-Marke.
- Wortmarke „FIN.CO" wird als Inline-Komponente gerendert (kein Bild), damit Mint exakt aus den Tokens kommt.

---

**Ende.** Bei Konflikten zwischen Brand Manual 2023 und diesem Dokument gilt das Brand Manual für Außenkommunikation, dieses Dokument für UI-Code.
