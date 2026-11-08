"""Festschreibung: Änderungsprotokoll mit Hash-Kette + Jahres-Sperre — als SQLite-Trigger.

Aufbau nach Haben (Sperren und Protokoll stecken in der Datenbank, nicht nur im Anwendungscode,
und greifen darum bei jeder Schreib-Route, auch bei künftigen). Eigenständig umgesetzt:

  * **Änderungsprotokoll** (`audit_log`): Trigger schreiben jede Änderung an den wichtigen Tabellen
    (siehe AUDIT_TABELLEN) mit altem und neuem Wert als JSON. Wer schreibt, sagt die SQL-Funktion
    `tab_actor()` (Verbindung → E-Mail aus dem Session-Cookie bzw. „system:<name>“).
  * **Hash-Kette:** jeder Eintrag bekommt `prev_hash` (Hash des Vorgängers) und `row_hash` =
    SHA-256(prev_hash ‖ Inhalt). Das Protokoll ist nur anhängbar (Trigger lehnen UPDATE/DELETE ab).
    Die Kette verhindert keine Manipulation, sie macht sie sichtbar (`kette_pruefen`).
  * **Jahres-Sperre:** ist ein Jahr in `jahr_abschluss` abgeschlossen, lehnen Trigger Änderungen an
    Buchungen, Positionen, ihren Belegen, Fahrten und der AfA dieses Jahres ab (RAISE mit Präfix
    JAHR_GESPERRT → HTTP 409, siehe main.py).

`ensure_triggers` legt alle Trigger an und hält sie aktuell (Spaltenlisten aus dem echten Schema);
es läuft bei jedem Start nach den Migrationen. Rebuild-Migrationen einer geschützten Tabelle dürfen
die Trigger also verlieren — der nächste Start stellt sie wieder her.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import sqlite3
from collections.abc import Callable

SPERR_PRAEFIX = "JAHR_GESPERRT"
SPERR_MELDUNG = (
    f"{SPERR_PRAEFIX}: Dieses Jahr ist abgeschlossen. Buchungen, Belege, AfA und Fahrten dieses "
    "Jahres sind gesperrt — unter „Jahresabschluss“ lässt es sich mit Begründung wieder öffnen."
)
PROTOKOLL_MELDUNG = "Das Änderungsprotokoll ist unveränderlich."
GENESIS = "GENESIS"
TRENNER = chr(31)  # Einheitentrenner zwischen den Feldern des Hashes

# Tabellen im Änderungsprotokoll → Ausdruck für die Gewerbe-ID der Zeile (r = Alias OLD/NEW).
# Kind-Tabellen fragen den Kopf ab und fallen, wenn der schon gelöscht ist (Kaskade), auf den
# Protokolleintrag des Kopfes zurück — sonst fehlte die Gewerbe-ID bei gelöschten Positionen.
def _gid_direkt(r: str) -> str:
    return f"{r}.gewerbe_id"


def _gid_kind(kopf: str, fk: str) -> Callable[[str], str]:
    return lambda r: (
        f"COALESCE((SELECT gewerbe_id FROM {kopf} WHERE id = {r}.{fk}), "
        f"(SELECT gewerbe_id FROM audit_log WHERE tabelle = '{kopf}' AND zeile_id = {r}.{fk} "
        "AND gewerbe_id IS NOT NULL ORDER BY id DESC LIMIT 1))"
    )


AUDIT_TABELLEN: dict[str, Callable[[str], str]] = {
    "gewerbe": lambda r: f"{r}.id",
    "buchung": _gid_direkt,
    "buchung_position": _gid_kind("buchung", "buchung_id"),
    "beleg": _gid_direkt,
    "afa_buchung": _gid_direkt,
    "fahrt": _gid_direkt,
    "rechnung": _gid_direkt,
    "rechnung_position": _gid_kind("rechnung", "rechnung_id"),
    "mahnung": _gid_kind("rechnung", "rechnung_id"),
    "jahr_abschluss": _gid_direkt,
}


# ── Hash der Kette (muss exakt dem SQL in _kette_sql entsprechen) ──────────

def eintrag_hash(r: sqlite3.Row | dict, prev_hash: str) -> str:
    teile = [
        prev_hash,
        str(r["id"]),
        r["ts"],
        r["actor"] or "",
        "" if r["gewerbe_id"] is None else str(r["gewerbe_id"]),
        r["tabelle"],
        str(r["zeile_id"]),
        r["aktion"],
        r["vorher"] or "",
        r["nachher"] or "",
    ]
    return hashlib.sha256(TRENNER.join(teile).encode("utf-8")).hexdigest()


# ── Trigger-SQL ─────────────────────────────────────────────────────────────

def _raise(meldung: str) -> str:
    return f"BEGIN SELECT RAISE(ABORT, '{meldung}'); END"


def _jahr(datum: str) -> str:
    return f"CAST(substr({datum}, 1, 4) AS INTEGER)"


def _jahr_gesperrt(gid: str, datum: str) -> str:
    return (
        "EXISTS (SELECT 1 FROM jahr_abschluss a WHERE a.abgeschlossen = 1 "
        f"AND a.gewerbe_id = {gid} AND a.jahr = {_jahr(datum)})"
    )


def _buchung_gesperrt(bid: str) -> str:
    return (
        "EXISTS (SELECT 1 FROM buchung b JOIN jahr_abschluss a ON a.abgeschlossen = 1 "
        f"AND a.gewerbe_id = b.gewerbe_id AND a.jahr = {_jahr('b.datum')} WHERE b.id = {bid})"
    )


def _afa_betrifft(r: str) -> str:
    """Trägt das Wirtschaftsgut zur AfA eines abgeschlossenen Jahres bei?"""
    return (
        "EXISTS (SELECT 1 FROM jahr_abschluss a WHERE a.abgeschlossen = 1 "
        f"AND a.gewerbe_id = {r}.gewerbe_id AND a.jahr >= {_jahr(r + '.anschaffungsdatum')} "
        f"AND ({r}.abgang_datum IS NULL OR a.jahr <= {_jahr(r + '.abgang_datum')}))"
    )


def _afa_abgang_aendert_abgeschlossen() -> str:
    """Eine Änderung des Abgangsdatums berührt ein abgeschlossenes Jahr nur, wenn dieses Jahr
    mindestens so spät liegt wie das frühere der beiden Abgangsjahre (kein Abgang = unendlich)."""
    return (
        "(OLD.abgang_datum IS NOT NEW.abgang_datum AND EXISTS (SELECT 1 FROM jahr_abschluss a "
        "WHERE a.abgeschlossen = 1 AND a.gewerbe_id = OLD.gewerbe_id "
        f"AND a.jahr >= {_jahr('OLD.anschaffungsdatum')} "
        f"AND a.jahr >= MIN(COALESCE({_jahr('OLD.abgang_datum')}, 9999), "
        f"COALESCE({_jahr('NEW.abgang_datum')}, 9999))))"
    )


def _sperr_trigger() -> dict[str, str]:
    m = SPERR_MELDUNG
    t: dict[str, str] = {}

    def neu(name: str, zeitpunkt: str, when: str) -> None:
        t[name] = f"CREATE TRIGGER {name}\n{zeitpunkt}\nWHEN {when}\n{_raise(m)}"

    # Buchungen (Kopf) und Positionen
    neu("tab_lock_buchung_ins", "BEFORE INSERT ON buchung", _jahr_gesperrt("NEW.gewerbe_id", "NEW.datum"))
    neu(
        "tab_lock_buchung_upd", "BEFORE UPDATE ON buchung",
        f"{_jahr_gesperrt('OLD.gewerbe_id', 'OLD.datum')} OR {_jahr_gesperrt('NEW.gewerbe_id', 'NEW.datum')}",
    )
    neu("tab_lock_buchung_del", "BEFORE DELETE ON buchung", _jahr_gesperrt("OLD.gewerbe_id", "OLD.datum"))
    neu("tab_lock_position_ins", "BEFORE INSERT ON buchung_position", _buchung_gesperrt("NEW.buchung_id"))
    neu(
        "tab_lock_position_upd", "BEFORE UPDATE ON buchung_position",
        f"{_buchung_gesperrt('OLD.buchung_id')} OR {_buchung_gesperrt('NEW.buchung_id')}",
    )
    neu("tab_lock_position_del", "BEFORE DELETE ON buchung_position", _buchung_gesperrt("OLD.buchung_id"))
    # Belege nur, solange sie an einer Buchung des abgeschlossenen Jahres hängen (Eingang bleibt frei)
    neu(
        "tab_lock_beleg_ins", "BEFORE INSERT ON beleg",
        f"NEW.buchung_id IS NOT NULL AND {_buchung_gesperrt('NEW.buchung_id')}",
    )
    neu(
        "tab_lock_beleg_upd", "BEFORE UPDATE ON beleg",
        f"(OLD.buchung_id IS NOT NULL AND {_buchung_gesperrt('OLD.buchung_id')}) "
        f"OR (NEW.buchung_id IS NOT NULL AND {_buchung_gesperrt('NEW.buchung_id')})",
    )
    neu(
        "tab_lock_beleg_del", "BEFORE DELETE ON beleg",
        f"OLD.buchung_id IS NOT NULL AND {_buchung_gesperrt('OLD.buchung_id')}",
    )
    # Fahrten
    neu("tab_lock_fahrt_ins", "BEFORE INSERT ON fahrt", _jahr_gesperrt("NEW.gewerbe_id", "NEW.datum"))
    neu(
        "tab_lock_fahrt_upd", "BEFORE UPDATE ON fahrt",
        f"{_jahr_gesperrt('OLD.gewerbe_id', 'OLD.datum')} OR {_jahr_gesperrt('NEW.gewerbe_id', 'NEW.datum')}",
    )
    neu("tab_lock_fahrt_del", "BEFORE DELETE ON fahrt", _jahr_gesperrt("OLD.gewerbe_id", "OLD.datum"))
    # AfA: Anlegen/Löschen, wenn das Gut zu einem abgeschlossenen Jahr beiträgt; Ändern, wenn sich
    # etwas ändert, das die Jahres-AfA bestimmt (Bezeichnung/Beschreibung bleiben frei, sie stehen im Protokoll)
    neu("tab_lock_afa_ins", "BEFORE INSERT ON afa_buchung", _afa_betrifft("NEW"))
    neu("tab_lock_afa_del", "BEFORE DELETE ON afa_buchung", _afa_betrifft("OLD"))
    betraege_aendern = (
        "(OLD.gewerbe_id IS NOT NEW.gewerbe_id OR OLD.kategorie_id IS NOT NEW.kategorie_id "
        "OR OLD.anschaffungskosten_cent IS NOT NEW.anschaffungskosten_cent "
        "OR OLD.anschaffungsdatum IS NOT NEW.anschaffungsdatum "
        "OR OLD.nutzungsdauer_jahre IS NOT NEW.nutzungsdauer_jahre "
        "OR OLD.afa_methode IS NOT NEW.afa_methode)"
    )
    neu(
        "tab_lock_afa_upd", "BEFORE UPDATE ON afa_buchung",
        f"({betraege_aendern} AND ({_afa_betrifft('OLD')} OR {_afa_betrifft('NEW')})) "
        f"OR {_afa_abgang_aendert_abgeschlossen()}",
    )
    return t


def _kette_sql() -> dict[str, str]:
    """Hash-Kette + Schutz des Protokolls selbst."""
    inhalt = (
        f"NEW.prev_hash || char(31) || NEW.id || char(31) || NEW.ts || char(31) || COALESCE(NEW.actor, '') "
        f"|| char(31) || COALESCE(NEW.gewerbe_id, '') || char(31) || NEW.tabelle || char(31) || NEW.zeile_id "
        f"|| char(31) || NEW.aktion || char(31) || COALESCE(NEW.vorher, '') || char(31) || COALESCE(NEW.nachher, '')"
    )
    return {
        # 1) neuer Eintrag: Hash des Vorgängers eintragen (kein Vorgänger → GENESIS)
        "tab_kette_1": (
            "CREATE TRIGGER tab_kette_1\nAFTER INSERT ON audit_log\nBEGIN\n"
            "UPDATE audit_log SET prev_hash = COALESCE((SELECT row_hash FROM audit_log WHERE id = "
            f"(SELECT MAX(id) FROM audit_log WHERE id < NEW.id)), '{GENESIS}') WHERE id = NEW.id;\nEND"
        ),
        # 2) damit steht der Vorgänger fest: eigenen Hash bilden
        "tab_kette_2": (
            "CREATE TRIGGER tab_kette_2\nAFTER UPDATE OF prev_hash ON audit_log\nWHEN NEW.row_hash IS NULL\nBEGIN\n"
            f"UPDATE audit_log SET row_hash = tab_sha256({inhalt}) WHERE id = NEW.id;\nEND"
        ),
        # nur anhängbar: einzig erlaubte Änderung ist das einmalige Setzen der beiden Hashes
        "tab_schutz_audit_upd": (
            "CREATE TRIGGER tab_schutz_audit_upd\nBEFORE UPDATE ON audit_log\n"
            "WHEN OLD.row_hash IS NOT NULL OR NEW.id IS NOT OLD.id OR NEW.ts IS NOT OLD.ts "
            "OR NEW.actor IS NOT OLD.actor OR NEW.gewerbe_id IS NOT OLD.gewerbe_id "
            "OR NEW.tabelle IS NOT OLD.tabelle OR NEW.zeile_id IS NOT OLD.zeile_id "
            "OR NEW.aktion IS NOT OLD.aktion OR NEW.vorher IS NOT OLD.vorher OR NEW.nachher IS NOT OLD.nachher\n"
            + _raise(PROTOKOLL_MELDUNG)
        ),
        "tab_schutz_audit_del": f"CREATE TRIGGER tab_schutz_audit_del\nBEFORE DELETE ON audit_log\n{_raise(PROTOKOLL_MELDUNG)}",
    }


def _audit_sql(conn: sqlite3.Connection, tabelle: str, gid: Callable[[str], str]) -> dict[str, str]:
    spalten = [r["name"] for r in conn.execute(f"PRAGMA table_info({tabelle})")]
    if not spalten:
        return {}

    def obj(r: str) -> str:
        return "json_object(" + ", ".join(f"'{c}', {r}.\"{c}\"" for c in spalten) + ")"

    jetzt = "strftime('%Y-%m-%dT%H:%M:%fZ', 'now')"
    kopf = "INSERT INTO audit_log (ts, actor, gewerbe_id, tabelle, zeile_id, aktion, vorher, nachher)\nVALUES"

    def eintrag(aktion: str, r_gid: str, r_id: str, vorher: str, nachher: str) -> str:
        return (
            f"{kopf} ({jetzt}, tab_actor(), {gid(r_gid)}, '{tabelle}', {r_id}.rowid, '{aktion}', "
            f"{vorher}, {nachher});"
        )

    return {
        f"tab_audit_{tabelle}_ins": (
            f"CREATE TRIGGER tab_audit_{tabelle}_ins\nAFTER INSERT ON {tabelle}\nBEGIN\n"
            + eintrag("INSERT", "NEW", "NEW", "NULL", obj("NEW")) + "\nEND"
        ),
        f"tab_audit_{tabelle}_upd": (
            f"CREATE TRIGGER tab_audit_{tabelle}_upd\nAFTER UPDATE ON {tabelle}\n"
            f"WHEN {obj('OLD')} IS NOT {obj('NEW')}\nBEGIN\n"
            + eintrag("UPDATE", "NEW", "NEW", obj("OLD"), obj("NEW")) + "\nEND"
        ),
        f"tab_audit_{tabelle}_del": (
            f"CREATE TRIGGER tab_audit_{tabelle}_del\nAFTER DELETE ON {tabelle}\nBEGIN\n"
            + eintrag("DELETE", "OLD", "OLD", obj("OLD"), "NULL") + "\nEND"
        ),
    }


def soll_trigger(conn: sqlite3.Connection) -> dict[str, str]:
    """Alle Trigger, die es geben muss: Name → SQL."""
    soll: dict[str, str] = {}
    soll.update(_sperr_trigger())
    soll.update(_kette_sql())
    for tabelle, gid in AUDIT_TABELLEN.items():
        soll.update(_audit_sql(conn, tabelle, gid))
    return soll


def _vorhanden(conn: sqlite3.Connection) -> dict[str, str]:
    return {
        r["name"]: (r["sql"] or "").strip()
        for r in conn.execute("SELECT name, sql FROM sqlite_master WHERE type = 'trigger' AND name LIKE 'tab\\_%' ESCAPE '\\'")
    }


def ensure_triggers(conn: sqlite3.Connection) -> int:
    """Legt fehlende oder veraltete Trigger an, entfernt überzählige (tab_*) und schreibt beim
    ersten Mal den Anfangseintrag ins Protokoll. Gibt die Zahl geänderter Trigger zurück."""
    soll = soll_trigger(conn)
    ist = _vorhanden(conn)
    geaendert = 0
    # Kette zuerst anlegen (die Audit-Trigger schreiben in audit_log, das braucht sie sofort)
    reihenfolge = sorted(soll, key=lambda n: (not n.startswith(("tab_kette", "tab_schutz")), n))
    for name in reihenfolge:
        if ist.get(name) != soll[name].strip():
            conn.execute(f"DROP TRIGGER IF EXISTS {name}")
            conn.execute(soll[name])
            geaendert += 1
    for name in set(ist) - set(soll):
        conn.execute(f"DROP TRIGGER IF EXISTS {name}")
        geaendert += 1
    if conn.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0] == 0:
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        conn.execute(
            "INSERT INTO audit_log (ts, actor, gewerbe_id, tabelle, zeile_id, aktion, vorher, nachher) "
            "VALUES (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'), 'system', NULL, 'system', 0, 'GENESIS', NULL, "
            "json_object('hinweis', 'Das Änderungsprotokoll beginnt hier. Frühere Änderungen sind nicht protokolliert.', "
            "'schema_version', ?))",
            (version,),
        )
    conn.commit()
    return geaendert


def trigger_fehlen(conn: sqlite3.Connection) -> list[str]:
    """Namen der Schutz-Trigger, die fehlen oder verändert wurden (Laufzeit-Prüfung)."""
    soll = soll_trigger(conn)
    ist = _vorhanden(conn)
    return sorted(n for n in soll if ist.get(n) != soll[n].strip())


# ── Kette prüfen ────────────────────────────────────────────────────────────

def kopf(conn: sqlite3.Connection) -> dict | None:
    """Kopf der Kette = der Prüfwert zum Aufbewahren außerhalb des Servers."""
    r = conn.execute("SELECT id, row_hash, ts FROM audit_log ORDER BY id DESC LIMIT 1").fetchone()
    return {"id": r["id"], "hash": r["row_hash"], "ts": r["ts"]} if r else None


def kette_pruefen(conn: sqlite3.Connection, max_fehler: int = 25) -> dict:
    """Rechnet jeden Hash nach und prüft die lückenlose Verkettung."""
    fehler: list[str] = []
    prev = GENESIS
    erwartet: int | None = None
    n = 0
    for r in conn.execute("SELECT * FROM audit_log ORDER BY id"):
        n += 1
        if erwartet is not None and r["id"] != erwartet:
            fehler.append(f"Lücke: Eintrag {erwartet} fehlt (weiter mit {r['id']}).")
        if r["prev_hash"] != prev:
            fehler.append(f"Eintrag {r['id']}: Vorgänger-Hash passt nicht zur Kette.")
        elif r["row_hash"] != eintrag_hash(r, r["prev_hash"]):
            fehler.append(f"Eintrag {r['id']}: Inhalt oder Hash wurde verändert.")
        prev = r["row_hash"] or ""
        erwartet = r["id"] + 1
        if len(fehler) >= max_fehler:
            fehler.append("… weitere Abweichungen nicht aufgeführt.")
            break
    return {"ok": not fehler, "eintraege": n, "fehler": fehler, "kopf": kopf(conn)}


def jetzt_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
