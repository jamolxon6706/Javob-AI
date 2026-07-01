import json
from typing import Any

from cryptography.fernet import Fernet, InvalidToken

from javobai.config import settings


def _get_fernet() -> Fernet:
    return Fernet(settings.fernet_key.encode())


def encrypt_dict(data: dict[str, Any]) -> str:
    return _get_fernet().encrypt(json.dumps(data).encode()).decode()


def decrypt_dict(token: str) -> dict[str, Any]:
    try:
        raw = _get_fernet().decrypt(token.encode())
        return json.loads(raw)  # type: ignore[no-any-return]
    except (InvalidToken, ValueError) as exc:
        raise ValueError("Cannot decrypt credentials — invalid key or tampered data") from exc


def encrypt(value: str) -> str:
    """Encrypt a plain string."""
    return _get_fernet().encrypt(value.encode()).decode()


def decrypt(token: str) -> str:
    """Decrypt a string token."""
    try:
        return _get_fernet().decrypt(token.encode()).decode()
    except (InvalidToken, ValueError) as exc:
        raise ValueError("Cannot decrypt — invalid key or tampered data") from exc
