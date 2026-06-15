import json
import os
from typing import Any

from cryptography.fernet import Fernet, InvalidToken

_fernet: Fernet | None = None


def _get_fernet() -> Fernet:
    global _fernet
    if _fernet is None:
        key = os.environ.get("FERNET_KEY", "")
        if not key:
            raise RuntimeError("FERNET_KEY env var is required")
        _fernet = Fernet(key.encode())
    return _fernet


def decrypt_dict(token: str) -> dict[str, Any]:
    try:
        raw = _get_fernet().decrypt(token.encode())
        return json.loads(raw)  # type: ignore[no-any-return]
    except (InvalidToken, ValueError) as exc:
        raise ValueError("Cannot decrypt credentials") from exc
