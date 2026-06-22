#!/usr/bin/env python3
"""Erzeugt einen bcrypt-Hash für ADMIN_PASSWORD_HASH in der .env.

Nutzung (interaktiv, Passwort wird nicht angezeigt):
    python3 scripts/hash_password.py

Oder direkt:
    python3 scripts/hash_password.py 'mein-passwort'

Benötigt das Paket bcrypt (im Backend-venv enthalten):
    pip install bcrypt
"""
import getpass
import sys

try:
    import bcrypt
except ImportError:
    sys.exit("bcrypt fehlt. Installieren mit:  pip install bcrypt")


def main() -> None:
    if len(sys.argv) > 1:
        pw = sys.argv[1]
    else:
        pw = getpass.getpass("Passwort: ")
        if pw != getpass.getpass("Passwort wiederholen: "):
            sys.exit("Passwörter stimmen nicht überein.")
    if not pw:
        sys.exit("Leeres Passwort ist nicht erlaubt.")
    h = bcrypt.hashpw(pw.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    print()
    print("In die .env eintragen (Hash ggf. in Anführungszeichen):")
    print(f"ADMIN_PASSWORD_HASH={h}")


if __name__ == "__main__":
    main()
