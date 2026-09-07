import base64
import ctypes
import getpass
import hmac
import io
import json
import os
import platform
import shutil
import struct
import sys
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.hashes import SHA256
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


MAGIC = b"APLOCK03"
VERSION = 3
SALT_SIZE = 16
NONCE_SIZE = 12
KEY_SIZE = 32
ITERATIONS = 600_000
LOCKED_SUFFIX = ".locked"
if getattr(sys, "frozen", False):
    APP_DIR = Path(os.environ.get("APPDATA", Path.home())) / "App Locker"
    APP_DIR.mkdir(parents=True, exist_ok=True)
else:
    APP_DIR = Path(__file__).resolve().parent
CONFIG_PATH = APP_DIR / "app_locker.json"
AUDIT_PATH = APP_DIR / "app_locker_audit.json"
DPAPI_ENTROPY = b"App Locker recovery v1"


class DATA_BLOB(ctypes.Structure):
    _fields_ = [("cbData", ctypes.c_uint32), ("pbData", ctypes.POINTER(ctypes.c_ubyte))]


@dataclass
class Session:
    username: str
    recovery_key: bytes
    recovery_mode: bool = False


def _blob(data: bytes):
    buffer = (ctypes.c_ubyte * len(data)).from_buffer_copy(data)
    return DATA_BLOB(len(data), buffer), buffer


def dpapi_protect(data: bytes) -> bytes:
    if os.name != "nt":
        raise RuntimeError("La recuperación protegida por Windows requiere Windows.")
    output = DATA_BLOB()
    input_blob, input_buffer = _blob(data)
    entropy_blob, entropy_buffer = _blob(DPAPI_ENTROPY)
    if not ctypes.windll.crypt32.CryptProtectData(ctypes.byref(input_blob), None, ctypes.byref(entropy_blob), None, None, 0, ctypes.byref(output)):
        raise OSError("Windows no pudo proteger la clave de recuperación.")
    try:
        return ctypes.string_at(output.pbData, output.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(output.pbData)


def dpapi_unprotect(data: bytes) -> bytes:
    if os.name != "nt":
        raise RuntimeError("La recuperación protegida por Windows requiere Windows.")
    output = DATA_BLOB()
    input_blob, input_buffer = _blob(data)
    entropy_blob, entropy_buffer = _blob(DPAPI_ENTROPY)
    if not ctypes.windll.crypt32.CryptUnprotectData(ctypes.byref(input_blob), None, ctypes.byref(entropy_blob), None, None, 0, ctypes.byref(output)):
        raise ValueError("Windows no pudo validar al propietario de esta cuenta.")
    try:
        return ctypes.string_at(output.pbData, output.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(output.pbData)


def _write_json(path: Path, data: dict | list) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, indent=2, ensure_ascii=True), encoding="utf-8")
    os.replace(temporary, path)


def audit(username: str, action: str, path: Path | None, success: bool, method: str, error: str | None = None) -> None:
    try:
        entries = json.loads(AUDIT_PATH.read_text(encoding="utf-8")) if AUDIT_PATH.exists() else []
    except (OSError, json.JSONDecodeError):
        entries = []
    entries.append({
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "app_user": username,
        "windows_user": getpass.getuser(),
        "computer": platform.node(),
        "action": action,
        "file_name": path.name if path else None,
        "file_path": str(path) if path else None,
        "file_size_bytes": path.stat().st_size if path and path.exists() else None,
        "credential_method": method,
        "success": success,
        "error": error,
    })
    _write_json(AUDIT_PATH, entries[-1000:])


def derive_key(password: str, salt: bytes) -> bytes:
    kdf = PBKDF2HMAC(algorithm=SHA256(), length=KEY_SIZE, salt=salt, iterations=ITERATIONS)
    return kdf.derive(password.encode("utf-8"))


def create_account(username: str, password: str) -> Session:
    if not username.strip() or len(password) < 8:
        raise ValueError("El usuario es obligatorio y la contraseña debe tener al menos 8 caracteres.")
    if CONFIG_PATH.exists():
        raise ValueError("La cuenta ya existe.")
    salt = os.urandom(SALT_SIZE)
    recovery_key = AESGCM.generate_key(bit_length=KEY_SIZE * 8)
    config = {
        "username": username.strip(),
        "password_salt": base64.b64encode(salt).decode("ascii"),
        "password_hash": base64.b64encode(derive_key(password, salt)).decode("ascii"),
        "recovery_key_dpapi": base64.b64encode(dpapi_protect(recovery_key)).decode("ascii"),
        "created_utc": datetime.now(timezone.utc).isoformat(),
    }
    _write_json(CONFIG_PATH, config)
    audit(username.strip(), "account_created", None, True, "password")
    return Session(username.strip(), recovery_key)


def login(username: str, password: str) -> Session:
    try:
        account = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        stored_username = account["username"]
        salt = base64.b64decode(account["password_salt"])
        expected = base64.b64decode(account["password_hash"])
        protected_recovery = base64.b64decode(account["recovery_key_dpapi"])
    except (OSError, KeyError, ValueError, json.JSONDecodeError) as error:
        raise ValueError(f"No se pudo leer la cuenta: {error}") from error
    if username != stored_username or not password or not hmac.compare_digest(derive_key(password, salt), expected):
        audit(stored_username, "login", None, False, "password", "Credenciales no válidas")
        raise ValueError("Usuario o contraseña incorrectos.")
    recovery_key = dpapi_unprotect(protected_recovery)
    audit(stored_username, "login", None, True, "password")
    return Session(stored_username, recovery_key)


def login_with_windows_recovery() -> Session:
    try:
        account = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        username = account["username"]
        recovery_key = dpapi_unprotect(base64.b64decode(account["recovery_key_dpapi"]))
    except (OSError, KeyError, ValueError, json.JSONDecodeError) as error:
        raise ValueError(f"No se pudo usar la recuperación de Windows: {error}") from error
    audit(username, "recovery_login", None, True, "Windows DPAPI")
    return Session(username, recovery_key, True)


def _encrypt_payload(name: str, kind: int, payload: bytes, password: str, recovery_key: bytes, destination: Path) -> Path:
    salt = os.urandom(SALT_SIZE)
    file_nonce = os.urandom(NONCE_SIZE)
    password_wrap_nonce = os.urandom(NONCE_SIZE)
    recovery_wrap_nonce = os.urandom(NONCE_SIZE)
    file_key = AESGCM.generate_key(bit_length=KEY_SIZE * 8)
    name_bytes = name.encode("utf-8")
    header = (MAGIC + bytes([VERSION, kind]) + salt + file_nonce + password_wrap_nonce + recovery_wrap_nonce
              + struct.pack(">I", len(name_bytes)) + name_bytes)
    password_wrap = AESGCM(derive_key(password, salt)).encrypt(password_wrap_nonce, file_key, header)
    recovery_wrap = AESGCM(recovery_key).encrypt(recovery_wrap_nonce, file_key, header)
    encrypted_payload = AESGCM(file_key).encrypt(file_nonce, payload, header)
    temporary = destination.with_name(destination.name + ".tmp")
    try:
        temporary.write_bytes(header + password_wrap + recovery_wrap + encrypted_payload)
        os.replace(temporary, destination)
    finally:
        if temporary.exists():
            temporary.unlink()
    return destination


def encrypt_path(source: Path, password: str, recovery_key: bytes) -> Path:
    if source.is_file():
        return _encrypt_payload(source.name, 0, source.read_bytes(), password, recovery_key, source.with_name(source.name + LOCKED_SUFFIX))
    if not source.is_dir():
        raise ValueError("La ruta seleccionada no existe.")
    destination = source.with_name(source.name + LOCKED_SUFFIX)
    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as temporary:
        zip_path = Path(temporary.name)
    try:
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
            for item in source.rglob("*"):
                archive.write(item, item.relative_to(source.parent))
        return _encrypt_payload(source.name, 1, zip_path.read_bytes(), password, recovery_key, destination)
    finally:
        zip_path.unlink(missing_ok=True)


def _safe_extract(archive: zipfile.ZipFile, destination: Path) -> None:
    root = destination.resolve()
    for member in archive.infolist():
        target = (destination / member.filename).resolve()
        if os.path.commonpath((str(root), str(target))) != str(root):
            raise ValueError("El contenedor incluye una ruta insegura.")
    archive.extractall(destination)


def decrypt_path(source: Path, password: str | None, recovery_key: bytes | None) -> Path:
    raw = source.read_bytes()
    minimum = len(MAGIC) + 2 + SALT_SIZE + NONCE_SIZE * 3 + 4 + (KEY_SIZE + 16) * 2 + 16
    if len(raw) < minimum or raw[: len(MAGIC)] != MAGIC:
        raise ValueError("El contenedor no pertenece a App Locker o está dañado.")
    position = len(MAGIC)
    version, kind = raw[position], raw[position + 1]
    position += 2
    if version != VERSION or kind not in (0, 1):
        raise ValueError("Esta versión de App Locker no reconoce el contenedor.")
    salt = raw[position:position + SALT_SIZE]
    position += SALT_SIZE
    file_nonce = raw[position:position + NONCE_SIZE]
    position += NONCE_SIZE
    password_nonce = raw[position:position + NONCE_SIZE]
    position += NONCE_SIZE
    recovery_nonce = raw[position:position + NONCE_SIZE]
    position += NONCE_SIZE
    name_length = struct.unpack(">I", raw[position:position + 4])[0]
    position += 4
    if not 1 <= name_length <= 4096 or position + name_length >= len(raw):
        raise ValueError("El contenedor está dañado.")
    name = raw[position:position + name_length].decode("utf-8")
    position += name_length
    header = raw[:position]
    password_wrap = raw[position:position + KEY_SIZE + 16]
    position += KEY_SIZE + 16
    recovery_wrap = raw[position:position + KEY_SIZE + 16]
    position += KEY_SIZE + 16
    file_key = None
    if password:
        try:
            file_key = AESGCM(derive_key(password, salt)).decrypt(password_nonce, password_wrap, header)
        except InvalidTag:
            pass
    if file_key is None and recovery_key:
        try:
            file_key = AESGCM(recovery_key).decrypt(recovery_nonce, recovery_wrap, header)
        except InvalidTag:
            pass
    if file_key is None:
        raise ValueError("Contraseña incorrecta o recuperación no autorizada.")
    try:
        payload = AESGCM(file_key).decrypt(file_nonce, raw[position:], header)
    except InvalidTag as error:
        raise ValueError("Contraseña incorrecta o contenedor alterado.") from error
    safe_name = Path(name).name
    destination = source.with_name(safe_name + ".restored" if (source.with_name(safe_name)).exists() else safe_name)
    temporary = destination.with_name(destination.name + ".tmp")
    try:
        if kind == 0:
            temporary.write_bytes(payload)
        else:
            temporary.mkdir()
            zip_path = temporary / "payload.zip"
            zip_path.write_bytes(payload)
            with zipfile.ZipFile(zip_path) as archive:
                _safe_extract(archive, temporary)
            zip_path.unlink()
            extracted_root = temporary / source.with_suffix("").name
            if extracted_root.exists():
                for child in extracted_root.iterdir():
                    child.replace(temporary / child.name)
                extracted_root.rmdir()
        if destination.exists():
            shutil.rmtree(destination) if destination.is_dir() else destination.unlink()
        os.replace(temporary, destination)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary) if temporary.is_dir() else temporary.unlink()
    return destination


def inspect_path(source: Path, password: str | None, recovery_key: bytes | None) -> list[dict]:
    """Lee el contenido autenticado del contenedor sin escribirlo en disco."""
    raw = source.read_bytes()
    minimum = len(MAGIC) + 2 + SALT_SIZE + NONCE_SIZE * 3 + 4 + (KEY_SIZE + 16) * 2 + 16
    if len(raw) < minimum or raw[: len(MAGIC)] != MAGIC:
        raise ValueError("El contenedor no pertenece a App Locker o está dañado.")
    position = len(MAGIC)
    version, kind = raw[position], raw[position + 1]
    position += 2
    if version != VERSION or kind not in (0, 1):
        raise ValueError("Esta versión de App Locker no reconoce el contenedor.")
    salt = raw[position:position + SALT_SIZE]
    position += SALT_SIZE
    file_nonce = raw[position:position + NONCE_SIZE]
    position += NONCE_SIZE
    password_nonce = raw[position:position + NONCE_SIZE]
    position += NONCE_SIZE
    recovery_nonce = raw[position:position + NONCE_SIZE]
    position += NONCE_SIZE
    name_length = struct.unpack(">I", raw[position:position + 4])[0]
    position += 4
    if not 1 <= name_length <= 4096 or position + name_length >= len(raw):
        raise ValueError("El contenedor está dañado.")
    name = raw[position:position + name_length].decode("utf-8")
    position += name_length
    header = raw[:position]
    password_wrap = raw[position:position + KEY_SIZE + 16]
    position += KEY_SIZE + 16
    recovery_wrap = raw[position:position + KEY_SIZE + 16]
    position += KEY_SIZE + 16
    file_key = None
    if password:
        try:
            file_key = AESGCM(derive_key(password, salt)).decrypt(password_nonce, password_wrap, header)
        except InvalidTag:
            pass
    if file_key is None and recovery_key:
        try:
            file_key = AESGCM(recovery_key).decrypt(recovery_nonce, recovery_wrap, header)
        except InvalidTag:
            pass
    if file_key is None:
        raise ValueError("Contraseña incorrecta o recuperación no autorizada.")
    try:
        payload = AESGCM(file_key).decrypt(file_nonce, raw[position:], header)
    except InvalidTag as error:
        raise ValueError("Contraseña incorrecta o contenedor alterado.") from error
    if kind == 0:
        return [{"name": name, "type": "Archivo", "size_bytes": len(payload)}]
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        return [
            {
                "name": item.filename,
                "type": "Carpeta" if item.is_dir() else "Archivo",
                "size_bytes": item.file_size,
            }
            for item in archive.infolist()
        ]


def remove_original(path: Path) -> None:
    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()
