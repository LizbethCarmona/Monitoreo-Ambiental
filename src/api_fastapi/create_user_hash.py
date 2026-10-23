"""Generate a password hash for DASHBOARD_USERS without storing the password."""
from __future__ import annotations

import argparse
import getpass
import re
import sys

from app.auth import crear_hash_contrasena


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("username", help="Individual account name (3-40 letters, digits, . _ -)")
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_.-]{3,40}", args.username):
        parser.error("El usuario debe tener de 3 a 40 letras, números, puntos, guiones o guiones bajos.")

    password = getpass.getpass("Contraseña (mínimo 12 caracteres): ")
    confirmation = getpass.getpass("Confirma la contraseña: ")
    if password != confirmation:
        print("Las contraseñas no coinciden.", file=sys.stderr)
        return 2
    try:
        password_hash = crear_hash_contrasena(password)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(f"{args.username}:{password_hash}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
