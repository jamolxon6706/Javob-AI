import json
from typing import Any

from cryptography.fernet import Fernet, InvalidToken

from javobai.config import settings

_fernet: Fernet | None = None


def _get_fernet() -> Fernet:
    global _fernet
    if _fernet is None:
        _fernet = Fernet(settings.fernet_key.encode())
    return _fernet


def encrypt_dict(data: dict[str, Any]) -> str:
    return _get_fernet().encrypt(json.dumps(data).encode()).decode()


def decrypt_dict(token: str) -> dict[str, Any]:
    try:
        raw = _get_fernet().decrypt(token.encode())
        return json.loads(raw)  # type: ignore[no-any-return]
    except (InvalidToken, ValueError) as exc:
        raise ValueError("Cannot decrypt credentials — invalid key or tampered data") from exc
