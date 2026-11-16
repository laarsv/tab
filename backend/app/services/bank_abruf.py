"""Bankabruf über Enable Banking (PSD2-Kontoinformationsdienst). Nur lesen: Umsätze und Konten, keine Zahlungen.

Ablauf: Bank wählen → `starten()` legt eine Verbindung im Zustand „ausstehend“ an und holt bei Enable Banking die
Anmeldeadresse der Bank → der Nutzer meldet sich dort an und stimmt zu → die Bank leitet auf
`<FRONTEND_URL>/bank/verbunden?code=…&state=…` zurück → `abschliessen()` tauscht den Code gegen eine Sitzung,
ordnet die Konten über die IBAN zu (legt fehlende an) und ruft gleich ab. Danach holt `lauf_alle()` die Umsätze im
Hintergrund (je Konto höchstens alle 6 Stunden — PSD2 erlaubt ohne den Nutzer nur 4 Abrufe am Tag).

Umsätze laufen in dieselbe Tabelle wie der Datei-Import (`bank_umsatz`, je Abruf ein `bank_import` mit Format
`api`), also gelten Dubletten-Schutz, Zuordnung, Vorschläge und die automatische Zuordnung unverändert:
  * Fingerprint `eb:<entry_reference>` (sonst Hash der Felder) — derselbe Umsatz kommt bei jedem Abruf wieder.
  * Gegen Umsätze aus Dateien (andere Schreibweise, anderer Fingerprint): gleicher Tag + gleicher Betrag auf dem
    Konto gilt als schon vorhanden (je vorhandenem Umsatz nur einmal). Der erste Abruf beginnt außerdem nach dem
    letzten Tag, der schon aus Dateien da ist.
  * Nur gebuchte Umsätze (`BOOK`) in EUR; Vorgemerktes kommt beim nächsten Abruf als gebucht.

Zugangsdaten: `ENABLE_BANKING_APP_ID` + private Schlüsseldatei; die Anfragen sind JWT (RS256, `kid` = App-ID,
höchstens 24 h gültig). Die Sitzung gilt bis `gueltig_bis` (Bank-Maximum, höchstens 180 Tage) — danach neu verbinden.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import logging
import secrets
import sqlite3
import time
from decimal import Decimal, InvalidOperation

import httpx
import jwt

from ..config import settings
from .bank_import import konto_aufloesen
from .girocode import iban_normal

log = logging.getLogger("tab.bank_abruf")

MAX_TAGE = 180
ERSTER_ABRUF_TAGE = 90  # so weit zurück, wenn das Konto noch keine Umsätze hat
UEBERLAPPUNG_TAGE = 7  # späte Buchungen der Bank mitnehmen
MIN_ABSTAND_STUNDEN = 6  # Hintergrund: je Verbindung höchstens 4 Abrufe am Tag
AUSSTEHEND_MINUTEN = 30


class AbrufFehler(Exception):
    """Fachlicher Fehler (→ 400/502 mit lesbarer Meldung)."""


def konfiguriert() -> bool:
    if not settings.ENABLE_BANKING_APP_ID:
        return False
    try:
        with open(settings.ENABLE_BANKING_KEY_FILE, "rb"):
            return True
    except OSError:
        return False


def _token() -> str:
    try:
        with open(settings.ENABLE_BANKING_KEY_FILE, "rb") as f:
            key = f.read()
    except OSError:
        raise AbrufFehler("Bankabruf ist nicht eingerichtet (Schlüsseldatei fehlt).")
    jetzt = int(time.time())
    return jwt.encode(
        {"iss": "enablebanking.com", "aud": "api.enablebanking.com", "iat": jetzt, "exp": jetzt + 3600},
        key, algorithm="RS256", headers={"kid": settings.ENABLE_BANKING_APP_ID},
    )


class Client:
    """Dünne Hülle um die Enable-Banking-API. In Tests wird `transport` ersetzt."""

    transport: httpx.BaseTransport | None = None

    def __init__(self, psu: dict | None = None):
        headers = {"Authorization": f"Bearer {_token()}"}
        if psu:  # Nutzer sitzt davor: zählt bei der Bank nicht gegen die 4 Hintergrund-Abrufe
            headers.update({k: v for k, v in psu.items() if v})
        self._c = httpx.Client(base_url=settings.ENABLE_BANKING_URL, headers=headers, timeout=60,
                               transport=self.transport)

    def _req(self, method: str, url: str, **kw) -> dict:
        try:
            r = self._c.request(method, url, **kw)
        except httpx.HTTPError as e:
            raise AbrufFehler(f"Enable Banking nicht erreichbar ({type(e).__name__}).")
        if r.status_code >= 400:
            try:
                d = r.json()
                code, msg = d.get("error") or d.get("code") or r.status_code, d.get("message") or d.get("detail") or ""
            except ValueError:
                code, msg = r.status_code, r.text[:200]
            raise AbrufFehler(f"Enable Banking: {code} {msg}".strip())
        return r.json() if r.content else {}

    def banken(self, land: str) -> list[dict]:
        return self._req("GET", "/aspsps", params={"country": land, "service": "AIS"}).get("aspsps", [])

    def auth(self, body: dict) -> dict:
        return self._req("POST", "/auth", json=body)

    def session(self, code: str) -> dict:
        return self._req("POST", "/sessions", json={"code": code})

    def session_loeschen(self, session_id: str) -> None:
        self._req("DELETE", f"/sessions/{session_id}")

    def details(self, uid: str) -> dict:
        return self._req("GET", f"/accounts/{uid}/details")

    def umsaetze(self, uid: str, ab: str) -> list[dict]:
        out, key, seiten = [], None, 0
        while True:
            params = {"date_from": ab}
            if key:
                params["continuation_key"] = key
            d = self._req("GET", f"/accounts/{uid}/transactions", params=params)
            out += d.get("transactions") or []
            key = d.get("continuation_key")
            seiten += 1
            if not key or seiten >= 50:
                return out

    def close(self) -> None:
        self._c.close()


# ── Banken, Verbinden ────────────────────────────────────────────────────────

_BANKEN_CACHE: dict[str, tuple[float, list[dict]]] = {}


def banken(land: str = "DE") -> list[dict]:
    """Banken eines Landes (12 h zwischengespeichert): Name, BIC, Logo, Kontoarten, max. Gültigkeit in Tagen."""
    land = land.upper()
    c = _BANKEN_CACHE.get(land)
    if c and c[0] > time.time():
        return c[1]
    cl = Client()
    try:
        roh = cl.banken(land)
    finally:
        cl.close()
    liste = sorted(
        ({"name": b["name"], "land": b.get("country", land), "bic": b.get("bic"), "logo": b.get("logo"),
          "psu_types": b.get("psu_types") or ["personal"], "beta": bool(b.get("beta")),
          "max_tage": min(MAX_TAGE, int((b.get("maximum_consent_validity") or MAX_TAGE * 86400) // 86400))}
         for b in roh if b.get("name")),
        key=lambda b: b["name"].lower(),
    )
    _BANKEN_CACHE[land] = (time.time() + 12 * 3600, liste)
    return liste


def _hash(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def starten(conn: sqlite3.Connection, *, gewerbe_id: int, bank_name: str, land: str, psu_type: str, email: str) -> str:
    """Legt die Verbindung an und gibt die Adresse der Bank-Anmeldung zurück."""
    bank = next((b for b in banken(land) if b["name"] == bank_name), None)
    if bank is None:
        raise AbrufFehler("Diese Bank kennt Enable Banking nicht.")
    if psu_type not in bank["psu_types"]:
        psu_type = bank["psu_types"][0]
    conn.execute(
        "DELETE FROM bank_verbindung WHERE status = 'ausstehend' AND created_at < datetime('now', ?)",
        (f"-{AUSSTEHEND_MINUTEN} minutes",),
    )
    state = secrets.token_urlsafe(24)
    gueltig = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=bank["max_tage"])).replace(microsecond=0)
    cl = Client()
    try:
        d = cl.auth({
            "access": {"valid_until": gueltig.isoformat()},
            "aspsp": {"name": bank["name"], "country": bank["land"]},
            "state": state,
            "redirect_url": f"{settings.public_origin}/bank/verbunden",
            "psu_type": psu_type,
            "language": "de",
        })
    finally:
        cl.close()
    if not d.get("url"):
        raise AbrufFehler("Enable Banking hat keine Anmeldeadresse geliefert.")
    conn.execute(
        "INSERT INTO bank_verbindung (gewerbe_id, bank_name, bank_land, psu_type, status, state_hash, gueltig_bis, "
        "angelegt_von) VALUES (?, ?, ?, ?, 'ausstehend', ?, ?, ?)",
        (gewerbe_id, bank["name"], bank["land"], psu_type, _hash(state), gueltig.date().isoformat(), email),
    )
    conn.commit()
    return d["url"]


def ausstehende(conn: sqlite3.Connection, state: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM bank_verbindung WHERE state_hash = ? AND status = 'ausstehend' "
        "AND created_at >= datetime('now', ?)",
        (_hash(state), f"-{AUSSTEHEND_MINUTEN} minutes"),
    ).fetchone()


def _iban(acc: dict) -> str | None:
    for k in ("account_id", "all_account_ids"):
        v = acc.get(k)
        for x in (v if isinstance(v, list) else [v]):
            if isinstance(x, dict) and (x.get("iban") or (x.get("scheme_name") == "IBAN" and x.get("identification"))):
                return iban_normal(x.get("iban") or x.get("identification"))
    return None


def abschliessen(conn: sqlite3.Connection, v: sqlite3.Row, code: str, psu: dict | None = None) -> dict:
    """Code gegen Sitzung tauschen, Konten zuordnen, erster Abruf."""
    cl = Client(psu)
    try:
        s = cl.session(code)
        konten = []
        for acc in s.get("accounts") or []:
            if isinstance(acc, str):  # nur die UID → Details holen
                acc = {"uid": acc, **cl.details(acc)}
            if acc.get("currency") and acc["currency"] != "EUR":
                continue
            iban = _iban(acc)
            if not iban:
                continue
            konten.append((acc["uid"], iban, acc.get("name") or acc.get("product")))
    finally:
        cl.close()
    if not s.get("session_id"):
        raise AbrufFehler("Die Bank hat keine Sitzung bestätigt.")
    gueltig = ((s.get("access") or {}).get("valid_until") or v["gueltig_bis"] or "")[:10] or None
    conn.execute(
        "UPDATE bank_verbindung SET status = 'aktiv', state_hash = NULL, session_id = ?, gueltig_bis = ?, "
        "letzter_fehler = NULL WHERE id = ?",
        (s["session_id"], gueltig, v["id"]),
    )
    namen = []
    for uid, iban, name in konten:
        k = konto_aufloesen(conn, v["gewerbe_id"], None, iban, name or v["bank_name"])
        conn.execute("UPDATE bankkonto SET verbindung_id = ?, eb_uid = ? WHERE id = ?", (v["id"], uid, k["id"]))
        namen.append(k["name"])
    conn.commit()
    if not konten:
        raise AbrufFehler("Die Bank hat kein Euro-Konto mit IBAN freigegeben.")
    try:
        erg = abrufen(conn, v["id"], email=v["angelegt_von"] or "system", psu=psu)
    except AbrufFehler as e:  # verbunden ist es trotzdem; der nächste Abruf versucht es wieder
        erg = {"neu": 0, "dubletten": 0, "fehler": str(e)}
    return {**erg, "konten": namen}


def trennen(conn: sqlite3.Connection, v: sqlite3.Row) -> None:
    if v["session_id"]:
        try:
            cl = Client()
            try:
                cl.session_loeschen(v["session_id"])
            finally:
                cl.close()
        except AbrufFehler as e:
            log.warning("Sitzung %s ließ sich nicht schließen: %s", v["id"], e)
    conn.execute("UPDATE bankkonto SET verbindung_id = NULL, eb_uid = NULL WHERE verbindung_id = ?", (v["id"],))
    conn.execute("UPDATE bank_verbindung SET status = 'getrennt', session_id = NULL WHERE id = ?", (v["id"],))
    conn.commit()


# ── Abrufen ──────────────────────────────────────────────────────────────────

def _cent(betrag) -> int | None:
    try:
        return int((Decimal(str(betrag)) * 100).to_integral_value())
    except (InvalidOperation, ValueError):
        return None


def umsatz_aus_api(t: dict) -> dict | None:
    """Enable-Banking-Transaktion → Felder für bank_umsatz (None = überspringen)."""
    if (t.get("status") or "BOOK") != "BOOK":
        return None
    amt = t.get("transaction_amount") or {}
    if (amt.get("currency") or "EUR") != "EUR":
        return None
    cent = _cent(amt.get("amount"))
    datum = t.get("booking_date") or t.get("value_date") or t.get("transaction_date")
    if cent is None or not datum:
        return None
    cent = abs(cent) * (-1 if t.get("credit_debit_indicator") == "DBIT" else 1)
    seite = "creditor" if cent < 0 else "debtor"
    partei = ((t.get(seite) or {}).get("name") or "").strip()
    konto = t.get(f"{seite}_account") or {}
    zweck = " ".join(x.strip() for x in (t.get("remittance_information") or []) if x and x.strip())
    if not zweck and t.get("note"):
        zweck = str(t["note"]).strip()
    btc = t.get("bank_transaction_code") or {}
    if not partei and not zweck and btc.get("description"):
        zweck = str(btc["description"])
    ref = t.get("entry_reference") or t.get("transaction_id")
    roh = "|".join([datum, str(cent), partei.lower(), zweck, t.get("reference_number") or ""])
    return {
        "datum": datum[:10], "wert_datum": (t.get("value_date") or "")[:10] or None, "betrag_cent": cent,
        "gegenpartei": partei or None, "gegenpartei_iban": iban_normal(konto.get("iban")) or None,
        "verwendungszweck": zweck[:1000] or None, "referenz": (t.get("reference_number") or "")[:200] or None,
        "fingerprint": f"eb:{ref}" if ref else f"eb:h:{hashlib.sha256(roh.encode()).hexdigest()}",
    }


def _ab_datum(conn: sqlite3.Connection, k: sqlite3.Row) -> str:
    heute = dt.date.today()
    if k["abruf_ab"]:
        ab = dt.date.fromisoformat(k["abruf_ab"]) - dt.timedelta(days=UEBERLAPPUNG_TAGE)
    else:
        letzter = conn.execute("SELECT MAX(datum) FROM bank_umsatz WHERE konto_id = ?", (k["id"],)).fetchone()[0]
        ab = (dt.date.fromisoformat(letzter) + dt.timedelta(days=1)) if letzter else heute - dt.timedelta(days=ERSTER_ABRUF_TAGE)
    return max(ab, heute - dt.timedelta(days=730)).isoformat()


def _speichern(conn: sqlite3.Connection, k: sqlite3.Row, roh: list[dict], ab: str, email: str, bank: str) -> dict:
    umsaetze = [u for u in (umsatz_aus_api(t) for t in roh) if u]
    gesehen: dict[str, int] = {}
    belegt: set[int] = set()  # Datei-Umsätze, die in diesem Lauf schon einem API-Umsatz entsprechen
    neu = dubletten = 0
    ids = []
    for u in umsaetze:
        # derselbe Fingerprint zweimal in einer Antwort (Banken ohne entry_reference): laufender Index
        n = gesehen.get(u["fingerprint"], 0)
        gesehen[u["fingerprint"]] = n + 1
        fp = u["fingerprint"] if n == 0 else f"{u['fingerprint']}:{n}"
        if conn.execute("SELECT 1 FROM bank_umsatz WHERE konto_id = ? AND fingerprint = ?", (k["id"], fp)).fetchone():
            dubletten += 1
            continue
        datei = conn.execute(
            "SELECT id FROM bank_umsatz WHERE konto_id = ? AND datum = ? AND betrag_cent = ? AND fingerprint NOT LIKE 'eb:%' "
            "ORDER BY id",
            (k["id"], u["datum"], u["betrag_cent"]),
        ).fetchall()
        frei = [r["id"] for r in datei if r["id"] not in belegt]
        if frei:
            belegt.add(frei[0])
            dubletten += 1
            continue
        ids.append(conn.execute(
            "INSERT INTO bank_umsatz (konto_id, gewerbe_id, datum, wert_datum, betrag_cent, gegenpartei, gegenpartei_iban, "
            "verwendungszweck, referenz, fingerprint) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (k["id"], k["gewerbe_id"], u["datum"], u["wert_datum"], u["betrag_cent"], u["gegenpartei"],
             u["gegenpartei_iban"], u["verwendungszweck"], u["referenz"], fp),
        ).lastrowid)
        neu += 1
    daten = sorted(u["datum"] for u in umsaetze)
    bis = dt.date.today().isoformat()
    cur = conn.execute(
        "INSERT INTO bank_import (konto_id, gewerbe_id, dateiname, sha256, format, von, bis, anzahl_neu, "
        "anzahl_dubletten, saldo_pruefung, importiert_am, importiert_von) VALUES (?, ?, ?, ?, 'api', ?, ?, ?, ?, ?, ?, ?)",
        (k["id"], k["gewerbe_id"], f"Abruf {bank}"[:200],
         hashlib.sha256(json.dumps(roh, sort_keys=True, default=str).encode()).hexdigest(),
         daten[0] if daten else ab, bis, neu, dubletten, "unbekannt",
         dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), email),
    )
    if ids:
        conn.execute(f"UPDATE bank_umsatz SET import_id = ? WHERE id IN ({','.join('?' * len(ids))})", (cur.lastrowid, *ids))
    neuester = daten[-1] if daten else None
    if neuester and (not k["abruf_ab"] or neuester > k["abruf_ab"]):
        conn.execute("UPDATE bankkonto SET abruf_ab = ? WHERE id = ?", (neuester, k["id"]))
    elif not k["abruf_ab"]:
        conn.execute("UPDATE bankkonto SET abruf_ab = ? WHERE id = ?", (ab, k["id"]))
    return {"neu": neu, "dubletten": dubletten}


def abrufen(conn: sqlite3.Connection, verbindung_id: int, *, email: str, psu: dict | None = None) -> dict:
    """Alle Konten einer Verbindung abrufen. Fehler werden an der Verbindung vermerkt und weitergereicht."""
    v = conn.execute("SELECT * FROM bank_verbindung WHERE id = ?", (verbindung_id,)).fetchone()
    if v is None or v["status"] != "aktiv" or not v["session_id"]:
        raise AbrufFehler("Die Verbindung ist nicht aktiv — bitte neu verbinden.")
    if v["gueltig_bis"] and v["gueltig_bis"] < dt.date.today().isoformat():
        conn.execute("UPDATE bank_verbindung SET status = 'abgelaufen' WHERE id = ?", (v["id"],))
        conn.commit()
        raise AbrufFehler("Die Freigabe der Bank ist abgelaufen — bitte neu verbinden.")
    erg = {"neu": 0, "dubletten": 0, "konten": 0}
    jetzt = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        cl = Client(psu)
        try:
            for k in conn.execute("SELECT * FROM bankkonto WHERE verbindung_id = ? AND eb_uid IS NOT NULL", (v["id"],)).fetchall():
                ab = _ab_datum(conn, k)
                e = _speichern(conn, k, cl.umsaetze(k["eb_uid"], ab), ab, email, v["bank_name"])
                erg["neu"] += e["neu"]
                erg["dubletten"] += e["dubletten"]
                erg["konten"] += 1
        finally:
            cl.close()
    except AbrufFehler as e:
        conn.rollback()
        text = str(e)
        status = "abgelaufen" if any(x in text for x in ("EXPIRED", "REVOKED", "CLOSED", "SESSION_DOES_NOT_EXIST")) else "aktiv"
        conn.execute("UPDATE bank_verbindung SET letzter_fehler = ?, letzter_abruf = ?, status = ? WHERE id = ?",
                     (text[:500], jetzt, status, v["id"]))
        conn.commit()
        raise
    conn.execute("UPDATE bank_verbindung SET letzter_abruf = ?, letzter_fehler = NULL WHERE id = ?", (jetzt, v["id"]))
    conn.commit()
    return erg


def lauf_alle(conn: sqlite3.Connection) -> None:
    """Hintergrund: aktive Verbindungen, deren letzter Abruf mindestens 6 Stunden her ist; danach automatische
    Zuordnung des Gewerbes (wie nach einem Datei-Import)."""
    if not konfiguriert():
        return
    from . import auto_zuordnung as auto  # Zirkel vermeiden

    grenze = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=MIN_ABSTAND_STUNDEN)).strftime("%Y-%m-%dT%H:%M:%SZ")
    for v in conn.execute(
        "SELECT v.id, v.gewerbe_id, g.owner_email FROM bank_verbindung v JOIN gewerbe g ON g.id = v.gewerbe_id "
        "WHERE v.status = 'aktiv' AND (v.letzter_abruf IS NULL OR v.letzter_abruf <= ?)",
        (grenze,),
    ).fetchall():
        try:
            erg = abrufen(conn, v["id"], email="system:bank_abruf")
            if erg["neu"] and v["owner_email"]:
                auto.lauf(conn, v["gewerbe_id"], {"email": v["owner_email"], "rolle": "inhaber"}, bilder=True)
            log.info("Verbindung %s: %s neu, %s schon da", v["id"], erg["neu"], erg["dubletten"])
        except AbrufFehler as e:
            log.warning("Verbindung %s: %s", v["id"], e)
        except Exception:
            conn.rollback()
            log.exception("Abruf Verbindung %s fehlgeschlagen", v["id"])
