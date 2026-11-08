"""Privatanteil bei Ausgaben (Handy, Internet, Strom im Homeoffice …).

Eine Buchungsposition speichert den gezahlten Betrag (`betrag_cent`, brutto) und den privaten Anteil in
Basispunkten (`privat_bp`, 2000 = 20 %). Nur der betriebliche Rest ist Betriebsausgabe und geht in
Summenblatt, Kennzahlen und Jahres-Check. Der private Teil ist in der EÜR keine Entnahme, sondern
schlicht keine Betriebsausgabe — es wird nichts Zusätzliches gebucht. Beim Geld bleibt alles beim
Zahlungsfluss: Kontoauszug und Bank-Zuordnung rechnen mit dem vollen Betrag.

Eine Rechenvorschrift für alles: Privatanteil kaufmännisch gerundet, der Rest ist betrieblich. Python und
SQL (`BETRIEBLICH_SQL`) rechnen mit Ganzzahlen und kommen auf denselben Cent.
"""
from __future__ import annotations

# Alias `p` = buchung_position
BETRIEBLICH_SQL = "(p.betrag_cent - (p.betrag_cent * p.privat_bp + 5000) / 10000)"


def privat_cent(betrag_cent: int, privat_bp: int) -> int:
    return (betrag_cent * privat_bp + 5000) // 10000


def betrieblich_cent(betrag_cent: int, privat_bp: int) -> int:
    return betrag_cent - privat_cent(betrag_cent, privat_bp)
