"""Authentication helpers for individual dashboard accounts."""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
import re
import secrets
import threading
import time
from collections import deque

_ALGORITHM = "pbkdf2_sha256"
_ITERATIONS = 600_000
_USERNAME = re.compile(r"^[A-Za-z0-9_.-]{3,40}$")
_DUMMY_SALT = "authentication-timing-salt"
_DUMMY_DIGEST = base64.urlsafe_b64encode(
    hashlib.pbkdf2_hmac("sha256", b"not-a-real-password", _DUMMY_SALT.encode(), _ITERATIONS)
).decode().rstrip("=")
_DUMMY_HASH = f"{_ALGORITHM}${_ITERATIONS}${_DUMMY_SALT}${_DUMMY_DIGEST}"


def enabled() -> bool:
    return os.getenv("DASHBOARD_AUTH_ENABLED", "false").strip().lower() in {"1", "true", "yes"}


def cookie_secure() -> bool:
    return os.getenv("DASHBOARD_COOKIE_SECURE", "false").strip().lower() in {"1", "true", "yes"}


def session_max_age() -> int:
    try:
        value = int(os.getenv("DASHBOARD_SESSION_MAX_AGE", "28800"))
    except ValueError as exc:
        raise RuntimeError("DASHBOARD_SESSION_MAX_AGE debe ser un entero en segundos.") from exc
    if not 300 <= value <= 86400:
        raise RuntimeError("DASHBOARD_SESSION_MAX_AGE debe estar entre 300 y 86400 segundos.")
    return value


def sesion_vigente(datos_sesion: dict, ahora: float | None = None) -> bool:
    emitida = datos_sesion.get("emitida")
    if not isinstance(emitida, int) or isinstance(emitida, bool):
        return False
    edad = (time.time() if ahora is None else ahora) - emitida
    return 0 <= edad < session_max_age()


def cargar_usuarios() -> dict[str, str]:
    usuarios: dict[str, str] = {}
    raw = os.getenv("DASHBOARD_USERS", "").strip()
    if not raw:
        return usuarios
    for entrada in raw.split(";"):
        usuario, separador, clave_hash = entrada.partition(":")
        usuario = usuario.strip()
        clave_hash = clave_hash.strip()
        if not separador or not _USERNAME.fullmatch(usuario) or not validar_hash(clave_hash):
            raise RuntimeError(
                "DASHBOARD_USERS debe contener entradas usuario:hash_pbkdf2 separadas por punto y coma."
            )
        if usuario in usuarios:
            raise RuntimeError(f"El usuario {usuario!r} está duplicado en DASHBOARD_USERS.")
        usuarios[usuario] = clave_hash
    return usuarios


def validar_hash(clave_hash: str) -> bool:
    try:
        hash_decodificado = base64.urlsafe_b64decode(clave_hash + "=" * (-len(clave_hash) % 4)).decode("ascii")
    except (ValueError, UnicodeDecodeError):
        return False
    partes = hash_decodificado.split("$")
    if len(partes) != 4 or partes[0] != _ALGORITHM:
        return False
    try:
        iteraciones = int(partes[1])
        sal = base64.urlsafe_b64decode(partes[2] + "=" * (-len(partes[2]) % 4))
        digest = base64.urlsafe_b64decode(partes[3] + "=" * (-len(partes[3]) % 4))
    except (ValueError, TypeError):
        return False
    return 100_000 <= iteraciones <= 1_000_000 and len(sal) >= 16 and len(digest) == 32


def crear_hash_contrasena(contrasena: str, sal: bytes | None = None) -> str:
    if len(contrasena) < 12:
        raise ValueError("La contraseña debe tener al menos 12 caracteres.")
    sal = sal or secrets.token_bytes(16)
    derivado = hashlib.pbkdf2_hmac("sha256", contrasena.encode("utf-8"), sal, _ITERATIONS)
    sal_txt = base64.urlsafe_b64encode(sal).decode().rstrip("=")
    digest_txt = base64.urlsafe_b64encode(derivado).decode().rstrip("=")
    hash_interno = f"{_ALGORITHM}${_ITERATIONS}${sal_txt}${digest_txt}"
    return base64.urlsafe_b64encode(hash_interno.encode("ascii")).decode("ascii").rstrip("=")


def verificar_contrasena(contrasena: str, clave_hash: str) -> bool:
    if not validar_hash(clave_hash):
        clave_hash = _DUMMY_HASH
        hash_decodificado = clave_hash
    else:
        hash_decodificado = base64.urlsafe_b64decode(clave_hash + "=" * (-len(clave_hash) % 4)).decode("ascii")
    algoritmo, iteraciones_txt, sal_txt, digest_esperado = hash_decodificado.split("$")
    sal = base64.urlsafe_b64decode(sal_txt + "=" * (-len(sal_txt) % 4))
    digest = hashlib.pbkdf2_hmac(algoritmo.removeprefix("pbkdf2_"), contrasena.encode("utf-8"), sal, int(iteraciones_txt))
    digest_txt = base64.urlsafe_b64encode(digest).decode().rstrip("=")
    return hmac.compare_digest(digest_txt, digest_esperado)


def validar_configuracion() -> None:
    if not enabled():
        if os.getenv("APP_ENV", "").strip().lower() == "production":
            raise RuntimeError("La autenticación DASHBOARD_AUTH_ENABLED=true es obligatoria en producción.")
        return
    secreto = os.getenv("DASHBOARD_SESSION_SECRET", "")
    if len(secreto.encode("utf-8")) < 32:
        raise RuntimeError("DASHBOARD_SESSION_SECRET debe tener al menos 32 bytes aleatorios.")
    if not cargar_usuarios():
        raise RuntimeError("Configura al menos una cuenta individual en DASHBOARD_USERS.")
    session_max_age()
    if os.getenv("APP_ENV", "").strip().lower() == "production":
        if not cookie_secure():
            raise RuntimeError("DASHBOARD_COOKIE_SECURE=true es obligatorio en producción.")
        if not os.getenv("ALLOWED_HOSTS", "").strip():
            raise RuntimeError("Configura ALLOWED_HOSTS con el dominio público permitido.")


class LimitadorAccesos:
    def __init__(
        self,
        max_intentos: int = 10,
        ventana_segundos: int = 60,
        max_clientes: int = 10_000,
    ) -> None:
        self.max_intentos = max_intentos
        self.ventana_segundos = ventana_segundos
        self.max_clientes = max_clientes
        self._intentos: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def esperar(self, clave: str) -> int:
        ahora = time.monotonic()
        with self._lock:
            if clave not in self._intentos:
                if len(self._intentos) >= self.max_clientes:
                    vencidos = [
                        cliente
                        for cliente, marcas in self._intentos.items()
                        if not marcas or ahora - marcas[-1] >= self.ventana_segundos
                    ]
                    for cliente in vencidos:
                        del self._intentos[cliente]
                    if len(self._intentos) >= self.max_clientes:
                        return self.ventana_segundos
                self._intentos[clave] = deque()
            intentos = self._intentos[clave]
            while intentos and ahora - intentos[0] >= self.ventana_segundos:
                intentos.popleft()
            if len(intentos) >= self.max_intentos:
                return max(1, int(self.ventana_segundos - (ahora - intentos[0])))
            intentos.append(ahora)
            return 0
