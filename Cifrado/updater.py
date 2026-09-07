import hashlib
import json
import os
import subprocess
import tempfile
import urllib.request
import webbrowser
from pathlib import Path


APP_VERSION = "1.3.0"
UPDATE_MANIFEST_URL = "https://raw.githubusercontent.com/Adricat32/AppLocker/main/update.json"
REQUEST_TIMEOUT_SECONDS = 4


def _version_tuple(value: str) -> tuple[int, ...]:
    try:
        return tuple(int(part) for part in value.strip().lstrip("v").split("."))
    except ValueError:
        return (0,)


def _download_json(url: str) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": "AppLocker-Updater"})
    with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
        data = json.loads(response.read().decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError("El manifiesto de actualización no es válido.")
    return data


def get_available_update() -> dict | None:
    if not UPDATE_MANIFEST_URL or "example.com" in UPDATE_MANIFEST_URL:
        return None
    try:
        manifest = _download_json(UPDATE_MANIFEST_URL)
        version = str(manifest["version"])
        if _version_tuple(version) <= _version_tuple(APP_VERSION):
            return None
        for required in ("installer_url", "sha256", "details_url"):
            if not manifest.get(required):
                raise ValueError(f"Falta {required} en el manifiesto.")
        checksum = str(manifest["sha256"]).strip().lower()
        if len(checksum) != 64 or any(character not in "0123456789abcdef" for character in checksum):
            raise ValueError("El SHA-256 del manifiesto no es válido.")
        manifest["version"] = version
        return manifest
    except (OSError, ValueError, KeyError, json.JSONDecodeError):
        return None


def download_and_launch_installer(update: dict) -> None:
    installer_url = str(update["installer_url"])
    expected_hash = str(update["sha256"]).lower()
    suffix = Path(installer_url.split("?", 1)[0]).suffix or ".exe"
    target = Path(tempfile.gettempdir()) / f"AppLockerUpdate-{update['version']}{suffix}"
    request = urllib.request.Request(installer_url, headers={"User-Agent": "AppLocker-Updater"})
    with urllib.request.urlopen(request, timeout=30) as response, target.open("wb") as output:
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            output.write(chunk)
    actual_hash = hashlib.sha256(target.read_bytes()).hexdigest().lower()
    if actual_hash != expected_hash:
        target.unlink(missing_ok=True)
        raise ValueError("La actualización no coincide con su huella SHA-256.")
    if os.name != "nt":
        raise RuntimeError("La instalación automática está disponible en Windows.")
    subprocess.Popen([str(target)], close_fds=True)


def show_update_dialog(parent, update: dict) -> str:
    import tkinter as tk
    from tkinter import ttk

    result = {"value": "later"}
    dialog = tk.Toplevel(parent)
    dialog.title("Actualización disponible")
    dialog.transient(parent)
    dialog.grab_set()
    dialog.resizable(True, True)
    dialog.geometry("560x430")

    frame = ttk.Frame(dialog, padding=24)
    frame.pack(fill="both", expand=True)
    ttk.Label(frame, text=f"App Locker {update['version']} está disponible", font=("Segoe UI Semibold", 16)).pack(anchor="w")
    details = (
        f"Versión instalada: {APP_VERSION}\n"
        f"Nueva versión: {update['version']}\n"
        f"Fecha: {update.get('release_date', 'No indicada')}\n"
        f"Tamaño: {update.get('size', 'No indicado')}\n\n"
        f"{update.get('summary', 'Hay una nueva versión disponible.')}\n\n"
        f"Cambios:\n{update.get('notes', 'Consulta los detalles de la actualización.')}"
    )
    text = tk.Text(frame, height=13, wrap="word", relief="flat", bg="#f4f1eb", fg="#24211d")
    text.insert("1.0", details)
    text.configure(state="disabled")
    text.pack(fill="both", expand=True, pady=(16, 16))

    buttons = ttk.Frame(frame)
    buttons.pack(fill="x")

    def close(value: str) -> None:
        result["value"] = value
        dialog.destroy()

    ttk.Button(buttons, text="Saber más", command=lambda: webbrowser.open(update.get("details_url", UPDATE_MANIFEST_URL))).pack(side="left")
    ttk.Button(buttons, text="Más tarde", command=lambda: close("later")).pack(side="right", padx=(8, 0))
    ttk.Button(buttons, text="Actualizar ahora", command=lambda: close("update")).pack(side="right")
    dialog.protocol("WM_DELETE_WINDOW", lambda: close("later"))
    parent.wait_window(dialog)
    return result["value"]
