"""Automatische Zuordnung von Bankumsätzen — nur, wenn der Treffer eindeutig ist.

Tab bucht hier selbst, aber ausschließlich über die vorhandenen Wege (`create_buchung`, `zuordnen`), also mit
denselben Prüfungen, der Jahres-Sperre und dem Änderungsprotokoll. Alles, was nicht eindeutig ist, bleibt offen
und erscheint wie bisher mit Vorschlägen auf der Bank-Seite. Reihenfolge je Umsatz:

  1. Schon gebucht   Buchung mit gleichem Betrag, Datum ≤ 14 Tage UND passender Beschreibung (≥ 80 Punkte,
                     genau eine)                                     -> nur verknüpfen
  2. Rechnung        Eingang = offener Betrag genau einer versendeten Rechnung, deren Nummer im Zweck steht
                     — oder, ohne Nummer, deren Empfänger als Einziger passt -> Einnahme buchen (wie „Als
                     Einnahme buchen“); Skonto und Teilzahlungen bleiben Handarbeit
  3. Dauerbeleg      Betrag, Bezeichnung UND Termin (± 7 Tage) passen, genau eine Vorlage -> Termin buchen
  4. Beleg           genau ein offener Beleg im Eingang mit exakt diesem Betrag und Belegdatum bis 21 Tage
                     vor (3 Tage nach) dem Umsatz, der zu keinem anderen offenen Umsatz passt, UND die
                     Kategorie ist gelernt: die letzten (bis zu 3)
                     Buchungen derselben Gegenpartei hatten je eine Position und alle dieselbe Kategorie
                     -> buchen mit Beleg, Kategorie und zuletzt genutztem Privatanteil

Umsätze mit `auto_aus = 1` (nach „Rückgängig“/„Verknüpfung lösen“) oder schon gesetztem `auto_grund` (Buchung
später gelöscht) fasst Tab nie wieder an. Ohne Beleg bucht Tab nichts (Belegprinzip).
"""
from __future__ import annotations

import datetime as dt
import logging
import os
import sqlite3

from fastapi import HTTPException

from ..config import settings
from . import bank_match as match
from . import besteuerung as best
from . import dauerbelege as dsvc
from . import rechnung_summen
from . import zahlungen as zsvc
from .beleg_extract import vorschlag_fuer_beleg

log = logging.getLogger("tab.auto_zuordnung")

SCHWELLE_SCHON_GEBUCHT = 80
MAX_BELEGE = 60
MAX_BILDER = 40  # Fotos brauchen Texterkennung (Sekunden je Bild)
BELEG_FENSTER_TAGE = 21  # Umsatz höchstens 21 Tage nach dem Belegdatum …
BELEG_VORLAUF_TAGE = 3   # … oder bis zu 3 Tage davor


def _offene_umsaetze(conn: sqlite3.Connection, gewerbe_id: int) -> list[dict]:
    return [
        dict(r) for r in conn.execute(
            "SELECT * FROM bank_umsatz WHERE gewerbe_id = ? AND buchung_id IS NULL AND status = 'offen' "
            "AND auto_aus = 0 AND auto_grund IS NULL ORDER BY datum, id",
            (gewerbe_id,),
        )
    ]


def _markieren(conn: sqlite3.Connection, umsatz_id: int, grund: str, neu_gebucht: bool) -> None:
    conn.execute(
        "UPDATE bank_umsatz SET auto_grund = ?, auto_buchung = ? WHERE id = ?",
        (grund[:300], 1 if neu_gebucht else 0, umsatz_id),
    )
    conn.commit()


def gelernte_kategorie(conn: sqlite3.Connection, u: dict) -> tuple[int, int, int] | None:
    """(kategorie_id, privat_bp, ust_bp) aus den letzten Buchungen derselben Gegenpartei — nur wenn eindeutig.
    Steuersatz: in einem Kleinunternehmer-Jahr 0; sonst der zuletzt gebuchte Satz, war der 0 (z. B. aus einem
    KU-Jahr), der vorgeschlagene Satz der Kategorie."""
    name = (u.get("gegenpartei") or "").strip().lower()
    iban = (u.get("gegenpartei_iban") or "").strip()
    if not name and not iban:
        return None
    rows = conn.execute(
        """
        SELECT b.id, COUNT(p.id) AS n, MAX(p.kategorie_id) AS kat, MAX(p.privat_bp) AS privat, MAX(p.ust_bp) AS ust
        FROM bank_umsatz x
        JOIN buchung b ON b.id = x.buchung_id
        JOIN buchung_position p ON p.buchung_id = b.id
        WHERE x.gewerbe_id = ? AND x.id != ?
          AND ((? != '' AND x.gegenpartei_iban = ?) OR (? != '' AND lower(x.gegenpartei) = ?))
          AND ((x.betrag_cent > 0) = (? > 0))
        GROUP BY b.id
        ORDER BY MAX(x.datum) DESC, b.id DESC
        LIMIT 3
        """,
        (u["gewerbe_id"], u["id"], iban, iban, name, name, u["betrag_cent"]),
    ).fetchall()
    if not rows or any(r["n"] != 1 for r in rows) or len({r["kat"] for r in rows}) != 1:
        return None
    k = conn.execute("SELECT * FROM kategorie WHERE id = ?", (rows[0]["kat"],)).fetchone()
    if k is None or k["ist_afa"] or k["belegpflicht_extra"] or not k["aktiv"]:
        return None
    if k["typ"] != ("einnahme" if u["betrag_cent"] > 0 else "ausgabe"):
        return None
    art = best.art_zum_datum(conn, u["gewerbe_id"], u["datum"])
    if (k["nur_besteuerung"] or art) != art:
        return None
    ust_bp = 0 if art == best.KU or k["key"] in best.OHNE_SATZ else (rows[0]["ust"] or k["ust_standard_bp"])
    return k["id"], ((rows[0]["privat"] or 0) if k["typ"] == "ausgabe" else 0), ust_bp


class _Belege:
    """Offene Eingangs-Belege mit gelesenem Betrag/Datum — je Lauf nur einmal auslesen."""

    def __init__(self, conn: sqlite3.Connection, gewerbe_id: int, bilder: bool):
        self.conn, self.liste = conn, None
        self.gewerbe_id, self.bilder = gewerbe_id, bilder

    def _laden(self) -> list[dict]:
        out, n_bilder = [], 0
        for b in self.conn.execute(
            "SELECT * FROM beleg WHERE gewerbe_id = ? AND buchung_id IS NULL ORDER BY created_at DESC LIMIT ?",
            (self.gewerbe_id, MAX_BELEGE),
        ).fetchall():
            bild = (b["content_type"] or "").startswith("image/")
            if bild and (not self.bilder or n_bilder >= MAX_BILDER):
                continue
            n_bilder += bild
            pfad = os.path.join(settings.UPLOAD_ROOT, b["stored_name"])
            if not os.path.exists(pfad):
                continue
            try:
                v = vorschlag_fuer_beleg(self.conn, b, pfad)
            except Exception:
                continue
            if v.get("betrag_cent") and v.get("datum"):
                out.append({"id": b["id"], "name": b["original_name"], "betrag_cent": v["betrag_cent"], "datum": v["datum"]})
        return out

    @staticmethod
    def _im_fenster(beleg_datum: str, umsatz_datum: str) -> bool:
        try:
            abstand = (dt.date.fromisoformat(umsatz_datum) - dt.date.fromisoformat(beleg_datum)).days
        except ValueError:
            return False
        return -BELEG_VORLAUF_TAGE <= abstand <= BELEG_FENSTER_TAGE

    def passend(self, u: dict, offene: list[dict]) -> dict | None:
        """Genau ein Beleg passt zu diesem Umsatz UND dieser Beleg passt zu keinem anderen offenen Umsatz
        (sonst landet z. B. die März-Rechnung auf der Februar-Abbuchung)."""
        if self.liste is None:
            self.liste = self._laden()
        betrag = abs(u["betrag_cent"])
        treffer = [b for b in self.liste if b["betrag_cent"] == betrag and self._im_fenster(b["datum"], u["datum"])]
        if len(treffer) != 1:
            return None
        b = treffer[0]
        andere = [
            x for x in offene
            if x["id"] != u["id"] and abs(x["betrag_cent"]) == betrag and (x["betrag_cent"] > 0) == (u["betrag_cent"] > 0)
            and self._im_fenster(b["datum"], x["datum"])
        ]
        return None if andere else b

    def verbraucht(self, beleg_id: int) -> None:
        if self.liste is not None:
            self.liste = [b for b in self.liste if b["id"] != beleg_id]


def _rechnung_eindeutig(offen: list[dict], u: dict) -> tuple[dict, str] | None:
    gleich = [r for r in offen if r["offen_cent"] == u["betrag_cent"]]
    if not gleich:
        return None
    text = match._norm(f"{u['verwendungszweck'] or ''} {u['referenz'] or ''}")
    mit_nr = [r for r in gleich if match._norm(r["nummer"]) and match._norm(r["nummer"]) in text]
    if len(mit_nr) == 1:
        return mit_nr[0], f"Rechnung {mit_nr[0]['nummer']}: Betrag und Nummer im Verwendungszweck"
    if mit_nr:
        return None
    mit_name = [r for r in gleich if match._name_passt(r["empfaenger_name"], u["gegenpartei"], u["verwendungszweck"])]
    if len(mit_name) == 1:
        return mit_name[0], f"Rechnung {mit_name[0]['nummer']}: Betrag und Name, einzige offene Rechnung"
    return None


def lauf(conn: sqlite3.Connection, gewerbe_id: int, user: dict, *, bilder: bool = True) -> dict:
    """Ordnet die offenen Umsätze eines Gewerbes zu, soweit eindeutig. Gibt eine Zusammenfassung zurück."""
    from ..routes.buchungen import BuchungIn, PositionIn, create_buchung  # Zirkel vermeiden

    g = conn.execute("SELECT bank_auto FROM gewerbe WHERE id = ?", (gewerbe_id,)).fetchone()
    ergebnis = {"verknuepft": 0, "gebucht": 0, "offen": 0, "fehler": [], "details": []}
    if g is None or not g["bank_auto"]:
        return ergebnis
    umsaetze = _offene_umsaetze(conn, gewerbe_id)
    if not umsaetze:
        return ergebnis
    offen_rech = match.offene_rechnungen(conn, gewerbe_id)
    belege = _Belege(conn, gewerbe_id, bilder)
    zugeordnet: set[int] = set()  # in diesem Lauf erledigt; alle anderen gelten weiter als offen

    def buchen(u: dict, body: dict, grund: str) -> bool:
        try:
            create_buchung(BuchungIn(gewerbe_id=gewerbe_id, bank_umsatz_id=u["id"], **body), user, conn)
        except (HTTPException, sqlite3.Error, ValueError) as e:
            conn.rollback()
            text = getattr(e, "detail", None) or str(e)
            ergebnis["fehler"].append({"umsatz_id": u["id"], "grund": grund, "fehler": str(text)[:200]})
            return False
        _markieren(conn, u["id"], grund, True)
        zugeordnet.add(u["id"])
        ergebnis["gebucht"] += 1
        ergebnis["details"].append({"umsatz_id": u["id"], "grund": grund, "neu": True})
        return True

    for u in umsaetze:
        # 1) schon gebucht -> nur verknüpfen
        t = [x for x in match.buchung_treffer(conn, u) if x["punkte"] >= SCHWELLE_SCHON_GEBUCHT]
        if len(t) == 1:
            frei = not conn.execute("SELECT 1 FROM bank_umsatz WHERE buchung_id = ?", (t[0]["id"],)).fetchone()
            if frei:
                conn.execute(
                    "UPDATE bank_umsatz SET buchung_id = ?, zugeordnet_am = datetime('now') WHERE id = ?",
                    (t[0]["id"], u["id"]),
                )
                grund = f"Schon gebucht: „{t[0]['beschreibung'] or 'Buchung'}“ vom {t[0]['datum']} (Betrag, Datum, Beschreibung)"
                _markieren(conn, u["id"], grund, False)
                zugeordnet.add(u["id"])
                ergebnis["verknuepft"] += 1
                ergebnis["details"].append({"umsatz_id": u["id"], "grund": grund, "neu": False})
                continue

        # 2) Eingang -> offene Rechnung
        if u["betrag_cent"] > 0:
            r = _rechnung_eindeutig(offen_rech, u)
            if r:
                rech, grund = r
                rrow = conn.execute("SELECT * FROM rechnung WHERE id = ?", (rech["id"],)).fetchone()
                pos = [PositionIn(kategorie_id=p["kategorie_id"], betrag_cent=p["betrag_cent"], ust_bp=p["ust_bp"],
                                  ust_cent=p["ust_cent"])
                       for p in rechnung_summen.zahlung_positionen(conn, rrow, u["betrag_cent"], u["datum"])]
                if pos and buchen(
                    u,
                    {"datum": u["datum"], "beschreibung": f"Rechnung {rech['nummer']} – {rech['empfaenger_name']}",
                     "positionen": pos,
                     "rechnung_id": rech["id"]},
                    grund,
                ):
                    offen_rech = match.offene_rechnungen(conn, gewerbe_id)
                    continue

        # 3) Umsatz -> Dauerbeleg-Termin (Abbuchung -> Ausgabe-, Eingang -> Einnahme-Vorlage)
        if u["betrag_cent"] != 0:
            t = [x for x in match.dauerbeleg_treffer(conn, u) if x["punkte"] >= 100]
            if len(t) == 1:
                d = t[0]
                grund = f"Dauerbeleg „{d['bezeichnung']}“, Termin {d['termin']}: Betrag, Bezeichnung und Termin"
                if buchen(
                    u,
                    {"datum": u["datum"], "beschreibung": d["bezeichnung"],
                     "positionen": [PositionIn(kategorie_id=d["kategorie_id"], betrag_cent=d["betrag_cent"],
                                               privat_bp=d["privat_bp"] or 0, ust_bp=d.get("ust_bp") or 0,
                                               ust_cent=d.get("ust_cent") if d.get("ust_bp") else None)],
                     "dauerbeleg_id": d["id"], "termin": d["termin"]},
                    grund,
                ):
                    continue

        # 4) Beleg im Eingang + gelernte Kategorie
        gelernt = gelernte_kategorie(conn, u)
        if gelernt:
            b = belege.passend(u, [x for x in umsaetze if x["id"] not in zugeordnet])
            if b:
                kat, privat, ust_bp = gelernt
                kname = conn.execute("SELECT name FROM kategorie WHERE id = ?", (kat,)).fetchone()["name"]
                grund = (f"Beleg „{b['name']}“: Betrag und Datum passen; Kategorie „{kname}“ wie bei "
                         f"{u['gegenpartei'] or 'dieser Gegenpartei'} zuletzt")
                if buchen(
                    u,
                    {"datum": u["datum"], "beschreibung": u["gegenpartei"] or b["name"],
                     "positionen": [PositionIn(kategorie_id=kat, betrag_cent=abs(u["betrag_cent"]), privat_bp=privat,
                                                 ust_bp=ust_bp)],
                     "beleg_ids": [b["id"]]},
                    grund,
                ):
                    belege.verbraucht(b["id"])
                    continue
        ergebnis["offen"] += 1
    return ergebnis


def rueckgaengig(conn: sqlite3.Connection, umsatz: dict) -> None:
    """Automatische Zuordnung zurücknehmen: neu angelegte Buchung löschen (mit der Zahlung auf der Rechnung
    und dem Dauerbeleg-Zeiger), sonst nur die Verknüpfung lösen. Danach nie wieder automatisch."""
    bid = umsatz["buchung_id"]
    if bid and umsatz["auto_buchung"]:
        b = conn.execute("SELECT * FROM buchung WHERE id = ?", (bid,)).fetchone()
        rechnungen = [
            r["rechnung_id"] for r in conn.execute(
                "SELECT DISTINCT rechnung_id FROM rechnung_zahlung WHERE buchung_id = ?", (bid,)
            )
        ]
        conn.execute("DELETE FROM rechnung_zahlung WHERE buchung_id = ? AND art = 'zahlung'", (bid,))
        if b is not None and b["dauerbeleg_id"] and b["termin"]:
            d = conn.execute("SELECT * FROM dauerbeleg WHERE id = ?", (b["dauerbeleg_id"],)).fetchone()
            if d is not None and d["naechste_am"] == dsvc.termin_nach(b["termin"], d["intervall"], d["anker_tag"]):
                conn.execute("UPDATE dauerbeleg SET naechste_am = ?, updated_at = datetime('now') WHERE id = ?",
                             (b["termin"], d["id"]))
        conn.execute("DELETE FROM buchung WHERE id = ?", (bid,))
        for rid in rechnungen:
            zsvc.aktualisiere_status(conn, rid)
    conn.execute(
        "UPDATE bank_umsatz SET buchung_id = NULL, zugeordnet_am = NULL, auto_grund = NULL, auto_buchung = 0, "
        "auto_aus = 1 WHERE id = ?",
        (umsatz["id"],),
    )
    conn.commit()


def lauf_alle(conn: sqlite3.Connection) -> None:
    """Hintergrund: alle Gewerbe mit Bankkonto und eingeschalteter Automatik (Akteur system:auto_zuordnung)."""
    for g in conn.execute(
        "SELECT g.id, g.owner_email FROM gewerbe g WHERE g.bank_auto = 1 AND g.owner_email IS NOT NULL "
        "AND EXISTS (SELECT 1 FROM bank_umsatz u WHERE u.gewerbe_id = g.id AND u.buchung_id IS NULL "
        "AND u.status = 'offen' AND u.auto_aus = 0 AND u.auto_grund IS NULL)"
    ).fetchall():
        try:
            erg = lauf(conn, g["id"], {"email": g["owner_email"], "rolle": "inhaber"}, bilder=True)
            if erg["verknuepft"] or erg["gebucht"]:
                log.info("Gewerbe %s: %s verknüpft, %s gebucht", g["id"], erg["verknuepft"], erg["gebucht"])
        except Exception:
            conn.rollback()
            log.exception("Auto-Zuordnung für Gewerbe %s fehlgeschlagen", g["id"])
