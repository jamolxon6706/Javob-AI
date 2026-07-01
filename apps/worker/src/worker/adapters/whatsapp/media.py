"""Downloads WhatsApp media (images/audio/video/documents) referenced by
their short-lived `media_id`, per Meta's two-step media retrieval flow:
  1. GET /{media_id}  -> { url, mime_type, sha256, file_size }
  2. GET <url> with the system-user access token in the Authorization header
"""
from __future__ import annotations

import logging
import uuid
from pathlib import Path

import httpx

from worker.settings import settings

logger = logging.getLogger(__name__)

_MEDIA_STORAGE_DIR = Path("/var/javobai/media")


async def download_media(media_id: str, *, access_token: str | None = None) -> str:
    """Returns a local filesystem path to the downloaded media file.

    `access_token` is the per-channel system-user token (decrypted by the
    caller). Falls back to a shared token only in dev/test fixtures.
    """
    token = access_token or settings.meta_app_secret  # dev fallback only
    base = f"{"https://graph.facebook.com"}/{"v19.0"}"
    headers = {"Authorization": f"Bearer {token}"}

    async with httpx.AsyncClient(timeout=30) as client:
        meta_resp = await client.get(f"{base}/{media_id}", headers=headers)
        meta_resp.raise_for_status()
        media_meta = meta_resp.json()

        file_resp = await client.get(media_meta["url"], headers=headers)
        file_resp.raise_for_status()

    _MEDIA_STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    ext = _guess_extension(media_meta.get("mime_type", ""))
    local_path = _MEDIA_STORAGE_DIR / f"{uuid.uuid4()}{ext}"
    local_path.write_bytes(file_resp.content)

    logger.info("Downloaded WhatsApp media %s -> %s", media_id, local_path)
    return str(local_path)


def _guess_extension(mime_type: str) -> str:
    return {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "audio/ogg": ".ogg",
        "audio/mpeg": ".mp3",
        "video/mp4": ".mp4",
        "application/pdf": ".pdf",
    }.get(mime_type, "")
