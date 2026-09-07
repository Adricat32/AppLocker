"""Secure key material generation for App Locker containers."""

import secrets

KEY_SIZE = 32


def generate_key() -> bytes:
    """Return a cryptographically secure 256-bit key."""
    return secrets.token_bytes(KEY_SIZE)


def generate_nonce(size: int = 12) -> bytes:
    """Return a cryptographically secure nonce."""
    return secrets.token_bytes(size)


def choose_method(method_ids) -> int:
    """Choose one encryption method using the system CSPRNG."""
    choices = tuple(method_ids)
    if not choices:
        raise ValueError("No hay métodos disponibles.")
    return secrets.choice(choices)
