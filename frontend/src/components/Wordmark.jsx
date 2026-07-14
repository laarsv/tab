// Marken-Bausteine gemäß VRWB CI (Design-Projekt „VRWB Markenidentität").
//
// Wordmark (default) — Produkt-Lockup „Standalone": vrwb in Roboto 900, der
// Unterstrich wird zum Trenner in Royal, der Toolname hängt direkt dran in
// Roboto Mono 500 Royal, ~0,83× Größe, Laufweite −1 %.
export default function Wordmark({ onInk = false, className = '' }) {
  return (
    <span className={`font-black tracking-wordmark ${onInk ? 'text-paper' : 'text-ink'} ${className}`}>
      vrwb
      <span className={onInk ? 'text-royal-soft' : 'text-royal'}>
        _<span className="font-mono font-medium tracking-toolname text-[0.83em]">tab</span>
      </span>
    </span>
  );
}

// Handschriftliche Signatur (logo-clean.svg aus dem Design-Projekt) als
// Inline-SVG in currentColor — kein CSS-Mask, rendert überall zuverlässig.
function SignaturSvg({ className = '' }) {
  return (
    <svg viewBox="0 0 333 658" className={className} fill="currentColor" aria-hidden="true">
      <g transform="translate(0,658) scale(0.1,-0.1)" stroke="none">
        <path d="M1704 6562 c-42 -27 -100 -142 -130 -260 -46 -177 -44 -357 8 -790 17 -141 18 -184 9 -229 -14 -74 -113 -299 -225 -518 -175 -340 -311 -534 -565 -808 -97 -106 -108 -130 -70 -168 35 -35 58 -21 157 101 201 249 336 469 576 938 88 172 163 309 166 305 4 -5 31 -82 59 -173 132 -412 392 -983 655 -1437 48 -83 85 -156 82 -162 -29 -47 -611 -99 -980 -89 -184 6 -255 20 -393 79 -50 21 -102 39 -113 39 -60 0 -114 -65 -103 -124 8 -37 73 -103 128 -127 53 -23 219 -64 345 -83 309 -49 615 -57 1029 -26 293 21 298 21 337 -38 25 -36 66 -202 89 -356 53 -360 44 -987 -21 -1416 -46 -306 -156 -635 -267 -800 -110 -163 -287 -291 -474 -342 -112 -30 -325 -30 -438 1 -90 24 -201 74 -272 122 -152 102 -315 332 -493 694 -100 206 -99 197 -62 362 91 403 136 816 137 1248 0 225 -4 301 -18 388 -23 138 -57 253 -91 311 -59 101 -181 113 -249 24 -58 -76 -59 -142 -3 -295 41 -112 66 -285 73 -493 8 -265 -16 -751 -43 -870 -5 -20 -12 -8 -39 66 -54 148 -75 178 -147 209 -87 36 -169 6 -218 -78 -101 -174 -156 -534 -130 -847 27 -332 62 -429 172 -475 82 -34 164 -13 220 56 70 87 190 303 226 409 12 32 13 32 31 16 10 -9 33 -45 51 -79 202 -385 448 -667 668 -764 116 -51 244 -76 397 -77 403 -2 629 150 833 559 122 246 201 583 228 975 23 329 12 962 -22 1225 -7 57 -13 59 100 -36 79 -67 150 -93 248 -94 52 0 73 5 94 21 52 38 68 70 69 134 0 89 -27 117 -173 176 -47 19 -182 153 -182 180 0 9 10 29 21 46 32 45 35 104 7 158 -30 59 -75 84 -142 81 -87 -5 -108 -2 -128 16 -24 21 -216 310 -316 475 -272 447 -567 1066 -634 1331 -16 64 -19 102 -16 196 4 104 9 130 50 261 60 187 86 316 96 465 13 222 -9 337 -74 380 -41 26 -94 29 -130 7z m69 -362 c2 -154 -4 -199 -56 -415 l-31 -130 -13 65 c-8 36 -16 137 -20 225 -5 143 -3 169 16 245 12 47 36 113 53 148 32 62 33 63 41 35 5 -15 10 -93 10 -173z m-1465 -4512 c15 -20 174 -389 182 -425 8 -31 -19 -164 -56 -277 -36 -110 -133 -318 -164 -349 -18 -19 -81 196 -101 348 -14 108 -5 406 15 510 15 74 59 184 79 197 18 11 33 10 45 -4z" />
      </g>
    </svg>
  );
}

// SignaturLockup — präferierte Marke im App-Header (CI-Update): Signatur in
// Royal + Haarlinie + Standalone-Lockup vrwb_tab.
export function SignaturLockup({ className = '' }) {
  return (
    <span className={`flex items-center gap-3 ${className}`} aria-label="vrwb tab">
      <SignaturSvg className="h-11 w-auto shrink-0 text-royal" />
      <span aria-hidden="true" className="h-8 w-px bg-ink/15" />
      <Wordmark className="text-2xl" />
    </span>
  );
}
