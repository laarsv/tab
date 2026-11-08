"""Kontoauszug-Import: CAMT.053 (XML) und CSV. Kein Bankabruf — die Datei kommt vom Nutzer.

Aufbau nach Haben (Konto aus der IBAN der Datei, Dubletten-Erkennung, Saldenprüfung, CSV mit
Spaltenzuordnung), eigenständig umgesetzt. Hier nur Parsen + Speichern; Zuordnen steht in
routes/bank.py, Vorschläge in services/bank_match.py.

Beträge in Cent mit Vorzeichen (+ Eingang, − Ausgang). Eine Datei darf beliebig oft importiert
werden: gleiche Umsätze werden an ihrem Fingerprint erkannt und übersprungen (gleiche Umsätze
am selben Tag zählen einzeln mit, darum geht ein laufender Index in den Fingerprint ein).
"""
from __future__ import annotations

import csv
import datetime as dt
import hashlib
import io
import re
import sqlite3
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

from .girocode import iban_gueltig, iban_normal

MAX_BYTES = 20 * 1024 * 1024


class BankImportError(Exception):
    """Fachlicher Fehler beim Lesen/Importieren (→ HTTP 400)."""


@dataclass
class Umsatz:
    datum: str
    betrag_cent: int
    wert_datum: str | None = None
    gegenpartei: str = ""
    gegenpartei_iban: str = ""
    verwendungszweck: str = ""
    referenz: str = ""


@dataclass
class Ergebnis:
    format: str
    umsaetze: list[Umsatz] = field(default_factory=list)
    iban: str | None = None
    kontoname: str | None = None
    saldo_anfang: int | None = None
    saldo_ende: int | None = None
    warnungen: list[str] = field(default_factory=list)


# ── gemeinsame Helfer ───────────────────────────────────────────────────────

def _spaces(text: str | None) -> str:
    return " ".join((text or "").split())


def _betrag_zu_cent(text: str) -> int | None:
    """'1.234,56', '-12,34', '12,34-', '(12,34)', '1234.56', '+5,00 €' → Cent; None bei Unsinn."""
    s = re.sub(r"[\s€]|EUR", "", (text or "").strip(), flags=re.I)
    if not s:
        return None
    negativ = False
    if s.startswith("(") and s.endswith(")"):
        negativ, s = True, s[1:-1]
    if s.endswith("-"):
        negativ, s = True, s[:-1]
    if s.startswith("-"):
        negativ, s = True, s[1:]
    elif s.startswith("+"):
        s = s[1:]
    if not re.fullmatch(r"[\d.,]+", s) or not re.search(r"\d", s):
        return None
    if "," in s and "." in s:  # das letzte Zeichen trennt die Dezimalstellen
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        s = s.replace(".", "").replace(",", ".")
    elif s.count(".") == 1 and len(s.split(".")[1]) == 3 and len(s.split(".")[0]) <= 3:
        s = s.replace(".", "")  # 1.234 = tausendzweihundertvierunddreißig
    elif s.count(".") > 1:
        s = s.replace(".", "")
    try:
        cent = int((Decimal(s) * 100).to_integral_value())
    except InvalidOperation:
        return None
    return -cent if negativ else cent


def _datum_iso(text: str) -> str | None:
    s = (text or "").strip()
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        j, mo, t = map(int, m.groups())
    else:
        m = re.match(r"^(\d{1,2})\.(\d{1,2})\.(\d{2,4})", s)
        if not m:
            m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{2,4})", s)  # selten, dann TT/MM/JJJJ
        if not m:
            return None
        t, mo, j = map(int, m.groups())
        if j < 100:
            j += 2000
    try:
        return dt.date(j, mo, t).isoformat()
    except ValueError:
        return None


def _iban_in_text(text: str) -> str | None:
    for m in re.finditer(r"[A-Z]{2}\d{2}(?:\s?[A-Z0-9]{4}){2,7}\s?[A-Z0-9]{1,4}", text or ""):
        kandidat = iban_normal(m.group(0))
        if iban_gueltig(kandidat):
            return kandidat
    return None


# ── CAMT.053 ────────────────────────────────────────────────────────────────

def _l(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _kinder(el: ET.Element, name: str) -> list[ET.Element]:
    return [c for c in el if _l(c.tag) == name]


def _pfad(el: ET.Element | None, *namen: str) -> ET.Element | None:
    for n in namen:
        if el is None:
            return None
        kinder = _kinder(el, n)
        el = kinder[0] if kinder else None
    return el


def _t(el: ET.Element | None) -> str:
    return _spaces(el.text) if el is not None and el.text else ""


def _cent_aus_betrag(amt: ET.Element | None, ind: str) -> int | None:
    if amt is None or not (amt.text or "").strip():
        return None
    try:
        cent = int((Decimal(amt.text.strip()) * 100).to_integral_value())
    except InvalidOperation:
        return None
    return -cent if ind.upper() == "DBIT" else cent


def parse_camt053(data: bytes) -> Ergebnis:
    # XML aus unbekannter Quelle: DOCTYPE/ENTITY (XXE, Entity-Bombe) gar nicht erst zulassen
    kopf = data[:200_000].lower()
    if b"<!doctype" in kopf or b"<!entity" in kopf:
        raise BankImportError("Die XML-Datei enthält eine DOCTYPE-/ENTITY-Angabe und wird aus Sicherheitsgründen nicht gelesen.")
    try:
        root = ET.fromstring(data)
    except ET.ParseError as e:
        raise BankImportError(f"Die XML-Datei ist nicht lesbar: {e}")
    stmts = [e for e in root.iter() if _l(e.tag) == "Stmt"]
    if not stmts:
        raise BankImportError("In der Datei steht kein CAMT.053-Kontoauszug (kein <Stmt>).")

    erg = Ergebnis(format="camt053")
    fremdwaehrung = 0
    for i, st in enumerate(stmts):
        acct = _pfad(st, "Acct")
        iban = _t(_pfad(acct, "Id", "IBAN")) or _t(_pfad(acct, "Id", "Othr", "Id"))
        if iban and not erg.iban:
            erg.iban = iban_normal(iban)
        if acct is not None and not erg.kontoname:
            erg.kontoname = _t(_pfad(acct, "Nm")) or None
        for bal in _kinder(st, "Bal"):
            code = _t(_pfad(bal, "Tp", "CdOrPrtry", "Cd"))
            cent = _cent_aus_betrag(_pfad(bal, "Amt"), _t(_pfad(bal, "CdtDbtInd")))
            if cent is None:
                continue
            if code in ("OPBD", "PRCD") and i == 0:
                erg.saldo_anfang = cent
            elif code == "CLBD" and i == len(stmts) - 1:
                erg.saldo_ende = cent
        for ntry in _kinder(st, "Ntry"):
            status = _t(_pfad(ntry, "Sts")) or _t(_pfad(ntry, "Sts", "Cd"))
            if status and status.upper() not in ("BOOK", "BOOKED"):
                continue  # vorgemerkt/abgelehnt
            amt = _pfad(ntry, "Amt")
            if amt is not None and amt.get("Ccy", "EUR").upper() != "EUR":
                fremdwaehrung += 1
                continue
            ind = _t(_pfad(ntry, "CdtDbtInd"))
            cent = _cent_aus_betrag(amt, ind)
            if cent is None:
                continue
            if _t(_pfad(ntry, "RvslInd")).lower() == "true":
                cent = -cent  # Storno-Buchung kehrt das Vorzeichen um
            datum = _datum_iso(_t(_pfad(ntry, "BookgDt", "Dt")) or _t(_pfad(ntry, "BookgDt", "DtTm")))
            wert = _datum_iso(_t(_pfad(ntry, "ValDt", "Dt")) or _t(_pfad(ntry, "ValDt", "DtTm")))
            if not datum:
                continue
            eingang = cent > 0
            namen, ibans, zwecke, refs = [], [], [], []
            for det in [d for nd in _kinder(ntry, "NtryDtls") for d in _kinder(nd, "TxDtls")]:
                partei = _pfad(det, "RltdPties")
                # Eingang: Gegenseite ist der Zahler (Dbtr), Ausgang: der Empfänger (Cdtr)
                p_name, p_acct = ("Dbtr", "DbtrAcct") if eingang else ("Cdtr", "CdtrAcct")
                namen.append(_t(_pfad(partei, p_name, "Nm")) or _t(_pfad(partei, p_name, "Pty", "Nm")))
                ibans.append(_t(_pfad(partei, p_acct, "Id", "IBAN")))
                zwecke += [_t(u) for u in (_pfad(det, "RmtInf").iter() if _pfad(det, "RmtInf") is not None else []) if _l(u.tag) == "Ustrd"]
                refs.append(_t(_pfad(det, "Refs", "EndToEndId")))
            zweck = _spaces(" ".join(z for z in zwecke if z)) or _t(_pfad(ntry, "AddtlNtryInf"))
            ref = next((r for r in refs if r and r.upper() != "NOTPROVIDED"), "") or _t(_pfad(ntry, "AcctSvcrRef"))
            erg.umsaetze.append(
                Umsatz(
                    datum=datum, wert_datum=wert, betrag_cent=cent,
                    gegenpartei=next((n for n in namen if n), ""),
                    gegenpartei_iban=iban_normal(next((i for i in ibans if i), "")),
                    verwendungszweck=zweck, referenz=ref,
                )
            )
    if fremdwaehrung:
        erg.warnungen.append(f"{fremdwaehrung} Umsätze in Fremdwährung übersprungen (Tab bucht nur in Euro).")
    return erg


# ── CSV ─────────────────────────────────────────────────────────────────────

DATUM_NAMEN = ("buchungsdatum", "buchungstag", "buchung", "datum", "booking date", "date")
WERT_NAMEN = ("wertstellung", "valuta", "wert")
BETRAG_NAMEN = ("betrag", "amount", "umsatz in eur", "umsatz")
SOLL_NAMEN = ("soll", "belastung", "debit", "ausgabe")
HABEN_NAMEN = ("haben", "gutschrift", "credit", "einnahme")
ZWECK_NAMEN = ("verwendungszweck", "buchungstext", "beschreibung", "zweck", "details", "text")
EIN_NAMEN = ("zahlungspflichtig", "auftraggeber", "zahler", "absender", "payer")
AUS_NAMEN = ("zahlungsempf", "empf", "begünstigt", "beguenstigt", "payee", "gläubiger")
GENERISCH_NAMEN = ("name zahlungsbeteiligter", "beguenstigter/zahlungspflichtiger", "begünstigter/zahlungspflichtiger",
                   "partner", "counterparty", "gegenpartei", "name")
IBAN_NAMEN = ("iban zahlungsbeteiligter", "kontonummer/iban", "gegenkonto", "iban")
REF_NAMEN = ("kundenreferenz", "end-to-end", "referenz", "mandatsreferenz")


def _norm(zelle: str) -> str:
    return re.sub(r"[\*\"']", "", (zelle or "").strip().lower())


def _finde(header: list[str], namen: tuple[str, ...], nicht: tuple[str, ...] = ()) -> int | None:
    """Erste Spalte, deren Name (in der Reihenfolge der Namen) passt — erst exakt, dann „beginnt mit“, dann „enthält“."""
    norm = [_norm(h) for h in header]
    for stufe in (lambda h, n: h == n, lambda h, n: h.startswith(n), lambda h, n: n in h):
        for n in namen:
            for i, h in enumerate(norm):
                if h and stufe(h, n) and not any(x in h for x in nicht):
                    return i
    return None


def _ist_kopfzeile(zeile: list[str]) -> bool:
    norm = [_norm(z) for z in zeile]
    datum = any(any(d in h for d in DATUM_NAMEN) for h in norm if h)
    betrag = any(any(b in h for b in BETRAG_NAMEN + SOLL_NAMEN + HABEN_NAMEN) for h in norm if h)
    return datum and betrag and sum(1 for h in norm if h) >= 3


def _dekodieren(data: bytes) -> str:
    for enc in ("utf-8-sig", "cp1252"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("latin-1")


def csv_einlesen(data: bytes) -> dict:
    """Zerlegt die CSV: Trennzeichen erkennen, Kopfzeile finden (Vorspann überspringen)."""
    text = _dekodieren(data)
    probe = "\n".join(text.splitlines()[:60])
    zaehl = {d: probe.count(d) for d in (";", ",", "\t", "|")}
    trenner = max(zaehl, key=zaehl.get) if max(zaehl.values()) else ";"
    zeilen = [[_spaces(c) for c in row] for row in csv.reader(io.StringIO(text), delimiter=trenner)]
    zeilen = [z for z in zeilen if any(z)]
    kopf_idx = next((i for i, z in enumerate(zeilen[:50]) if _ist_kopfzeile(z)), None)
    if kopf_idx is None:
        raise BankImportError(
            "Keine Kopfzeile mit Datum- und Betrag-Spalte gefunden. Ist das ein Kontoauszug als CSV? "
            "Sonst bitte CAMT.053 bei deiner Bank exportieren."
        )
    vorspann = " ".join(" ".join(z) for z in zeilen[:kopf_idx])
    return {
        "trenner": trenner,
        "header": zeilen[kopf_idx],
        "zeilen": zeilen[kopf_idx + 1:],
        "iban": _iban_in_text(vorspann),
    }


def mapping_raten(header: list[str]) -> dict:
    """Spaltenzuordnung aus den Überschriften raten (Index oder None); das UI lässt sie ändern."""
    datum = _finde(header, DATUM_NAMEN, nicht=("wert",))
    betrag = _finde(header, BETRAG_NAMEN, nicht=("typ", "art", "gläubiger", "iban"))
    soll = _finde(header, SOLL_NAMEN) if betrag is None else None
    haben = _finde(header, HABEN_NAMEN) if betrag is None else None
    ein = _finde(header, EIN_NAMEN)
    aus = _finde(header, AUS_NAMEN, nicht=("iban",))
    allgemein = _finde(header, GENERISCH_NAMEN, nicht=("iban",))
    return {
        "datum": datum,
        "wert_datum": _finde(header, WERT_NAMEN),
        "betrag": betrag,
        "soll": soll,
        "haben": haben,
        "verwendungszweck": _finde(header, ZWECK_NAMEN),
        "gegenpartei_ein": ein if ein is not None else allgemein,
        "gegenpartei_aus": aus if aus is not None else allgemein,
        "iban": _finde(header, IBAN_NAMEN),
        "referenz": _finde(header, REF_NAMEN),
        "status": _finde(header, ("status",)),
    }


def _zelle(zeile: list[str], idx) -> str:
    return zeile[idx] if isinstance(idx, int) and 0 <= idx < len(zeile) else ""


def parse_csv(data: bytes, mapping: dict | None = None) -> tuple[Ergebnis, dict]:
    """→ (Ergebnis, {header, mapping, trenner, uebersprungen}). Ohne mapping wird geraten."""
    csv_daten = csv_einlesen(data)
    header = csv_daten["header"]
    m = {**mapping_raten(header), **(mapping or {})}
    if m.get("datum") is None:
        raise BankImportError("Bitte die Spalte mit dem Buchungsdatum wählen.")
    if m.get("betrag") is None and m.get("soll") is None and m.get("haben") is None:
        raise BankImportError("Bitte die Betrags-Spalte (oder Soll und Haben) wählen.")
    erg = Ergebnis(format="csv", iban=csv_daten["iban"])
    uebersprungen = 0
    for z in csv_daten["zeilen"]:
        datum = _datum_iso(_zelle(z, m["datum"]))
        status = _zelle(z, m.get("status")).lower()
        if m.get("betrag") is not None:
            cent = _betrag_zu_cent(_zelle(z, m["betrag"]))
        else:
            soll = _betrag_zu_cent(_zelle(z, m.get("soll"))) or 0
            haben = _betrag_zu_cent(_zelle(z, m.get("haben"))) or 0
            cent = abs(haben) - abs(soll) if (soll or haben) else None
        if not datum or cent is None or cent == 0 or "vorgemerkt" in status or "pending" in status:
            uebersprungen += 1
            continue
        partei = _zelle(z, m.get("gegenpartei_ein" if cent > 0 else "gegenpartei_aus"))
        erg.umsaetze.append(
            Umsatz(
                datum=datum, wert_datum=_datum_iso(_zelle(z, m.get("wert_datum"))), betrag_cent=cent,
                gegenpartei=partei, gegenpartei_iban=iban_normal(_zelle(z, m.get("iban"))),
                verwendungszweck=_zelle(z, m.get("verwendungszweck")), referenz=_zelle(z, m.get("referenz")),
            )
        )
    if uebersprungen:
        erg.warnungen.append(f"{uebersprungen} Zeilen ohne gültiges Datum oder Betrag übersprungen (Summenzeilen, Vorgemerktes).")
    if not erg.umsaetze:
        raise BankImportError("Mit dieser Spaltenzuordnung wurde kein Umsatz erkannt.")
    return erg, {"header": header, "mapping": m, "trenner": csv_daten["trenner"], "uebersprungen": uebersprungen}


# ── Format, Fingerprint, Speichern ──────────────────────────────────────────

def format_erkennen(data: bytes, dateiname: str = "") -> str:
    kopf = data[:2000].lstrip(b"\xef\xbb\xbf \t\r\n")
    if kopf.startswith(b"<") or dateiname.lower().endswith((".xml", ".camt")):
        return "camt053"
    return "csv"


def lesen(data: bytes, dateiname: str = "", mapping: dict | None = None) -> tuple[Ergebnis, dict]:
    if len(data) > MAX_BYTES:
        raise BankImportError("Die Datei ist größer als 20 MB.")
    if not data.strip():
        raise BankImportError("Die Datei ist leer.")
    if format_erkennen(data, dateiname) == "camt053":
        return parse_camt053(data), {}
    return parse_csv(data, mapping)


def fingerprints(umsaetze: list[Umsatz]) -> list[str]:
    """Stabil über Importe: gleicher Umsatz → gleicher Fingerprint; mehrfach identische Umsätze
    bekommen einen laufenden Index (im Dateiumfang), damit sie nicht als Dubletten gelten."""
    gesehen: dict[str, int] = {}
    out = []
    for u in umsaetze:
        basis = hashlib.sha256(
            "|".join([u.datum, str(u.betrag_cent), u.gegenpartei.lower(), u.verwendungszweck, u.referenz]).encode("utf-8")
        ).hexdigest()
        k = gesehen.get(basis, 0)
        gesehen[basis] = k + 1
        out.append(f"{basis}:{k}")
    return out


def _saldo_pruefung(erg: Ergebnis) -> str:
    if erg.saldo_anfang is None or erg.saldo_ende is None:
        return "unbekannt"
    summe = sum(u.betrag_cent for u in erg.umsaetze)
    diff = erg.saldo_ende - erg.saldo_anfang - summe
    return "ok" if diff == 0 else f"weicht ab ({diff / 100:+.2f} EUR)".replace(".", ",")


def konto_aufloesen(
    conn: sqlite3.Connection, gewerbe_id: int, konto_id: int | None, iban: str | None, kontoname: str | None
) -> sqlite3.Row:
    """Konto für den Import: das gewählte, sonst das zur IBAN der Datei (wird angelegt)."""
    iban = iban_normal(iban) if iban else None
    if konto_id:
        k = conn.execute("SELECT * FROM bankkonto WHERE id = ? AND gewerbe_id = ?", (konto_id, gewerbe_id)).fetchone()
        if k is None:
            raise BankImportError("Konto nicht gefunden.")
        if iban and k["iban"] and iban != k["iban"]:
            raise BankImportError(f"Die Datei gehört zu {iban}, das gewählte Konto zu {k['iban']}.")
        if iban and not k["iban"]:
            conn.execute("UPDATE bankkonto SET iban = ? WHERE id = ?", (iban, k["id"]))
            k = conn.execute("SELECT * FROM bankkonto WHERE id = ?", (k["id"],)).fetchone()
        return k
    if not iban:
        raise BankImportError("Die Datei nennt keine IBAN — bitte ein Konto wählen oder neu anlegen.")
    k = conn.execute("SELECT * FROM bankkonto WHERE gewerbe_id = ? AND iban = ?", (gewerbe_id, iban)).fetchone()
    if k is None:
        cur = conn.execute(
            "INSERT INTO bankkonto (gewerbe_id, name, iban) VALUES (?, ?, ?)",
            (gewerbe_id, kontoname or f"Konto …{iban[-4:]}", iban),
        )
        k = conn.execute("SELECT * FROM bankkonto WHERE id = ?", (cur.lastrowid,)).fetchone()
    return k


def importiere(
    conn: sqlite3.Connection,
    *,
    gewerbe_id: int,
    konto_id: int | None,
    dateiname: str,
    data: bytes,
    mapping: dict | None,
    email: str,
) -> dict:
    erg, _info = lesen(data, dateiname, mapping)
    if not erg.umsaetze:
        raise BankImportError("Die Datei enthält keine Umsätze.")
    konto = konto_aufloesen(conn, gewerbe_id, konto_id, erg.iban, erg.kontoname)
    sha = hashlib.sha256(data).hexdigest()
    fps = fingerprints(erg.umsaetze)
    neu = dubletten = 0
    for u, fp in zip(erg.umsaetze, fps):
        if conn.execute("SELECT 1 FROM bank_umsatz WHERE konto_id = ? AND fingerprint = ?", (konto["id"], fp)).fetchone():
            dubletten += 1
            continue
        conn.execute(
            "INSERT INTO bank_umsatz (konto_id, gewerbe_id, datum, wert_datum, betrag_cent, gegenpartei, "
            "gegenpartei_iban, verwendungszweck, referenz, fingerprint) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (konto["id"], gewerbe_id, u.datum, u.wert_datum, u.betrag_cent, u.gegenpartei or None,
             u.gegenpartei_iban or None, u.verwendungszweck or None, u.referenz or None, fp),
        )
        neu += 1
    daten = sorted(u.datum for u in erg.umsaetze)
    saldo = _saldo_pruefung(erg)
    cur = conn.execute(
        "INSERT INTO bank_import (konto_id, gewerbe_id, dateiname, sha256, format, von, bis, anzahl_neu, "
        "anzahl_dubletten, saldo_pruefung, importiert_am, importiert_von) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (konto["id"], gewerbe_id, dateiname[:200], sha, erg.format, daten[0], daten[-1], neu, dubletten, saldo,
         dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), email),
    )
    conn.commit()
    return {
        "import_id": cur.lastrowid, "konto_id": konto["id"], "konto_name": konto["name"], "format": erg.format,
        "neu": neu, "dubletten": dubletten, "von": daten[0], "bis": daten[-1], "saldo_pruefung": saldo,
        "warnungen": erg.warnungen,
    }
