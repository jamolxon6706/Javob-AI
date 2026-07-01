"""Tenant-facing WhatsApp channel onboarding.

Flow:
  1. Tenant pastes a system-user access token + phone_number_id.
  2. We call GET /{phone_number_id} on the Graph API to verify the token.
  3. We encrypt the token (Fernet) and persist a channels row.
  4. We register webhook subscription fields on the WABA.
"""
from __future__ import annotations

import json
import logging
import uuid

import httpx
from cryptography.fernet import Fernet
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from javobai.config import settings
from javobai.crypto import encrypt
from javobai.db.models.channel import Channel

logger = logging.getLogger(__name__)

_META_GRAPH_BASE = "https://graph.facebook.com"
_META_API_VERSION = "v19.0"


class ConnectWhatsAppRequest(BaseModel):
    phone_number_id: str = Field(..., description="Meta WhatsApp phone_number_id")
    waba_id: str = Field(..., description="WhatsApp Business Account id")
    access_token: str = Field(..., description="System-user permanent access token")


class WhatsAppCredentialError(Exception):
    pass


async def connect_whatsapp_channel(
    *, tenant_id: uuid.UUID, body: ConnectWhatsAppRequest, db: AsyncSession
) -> Channel:
    await _verify_token_owns_number(body.phone_number_id, body.access_token)
    await _subscribe_app_to_waba(body.waba_id, body.access_token)

    channel = Channel(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        platform="whatsapp",
        external_id=body.phone_number_id,
        name=f"WhatsApp {body.phone_number_id}",
        credentials=encrypt(
            json.dumps(
                {
                    "phone_number_id": body.phone_number_id,
                    "waba_id": body.waba_id,
                    "access_token": body.access_token,
                }
            )
        ),
        is_active=True,
    )
    db.add(channel)
    await db.commit()
    await db.refresh(channel)

    logger.info("Tenant %s connected WhatsApp number %s", tenant_id, body.phone_number_id)
    return channel


async def _verify_token_owns_number(phone_number_id: str, access_token: str) -> None:
    url = f"{_META_GRAPH_BASE}/{_META_API_VERSION}/{phone_number_id}"
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            url,
            params={"fields": "verified_name,display_phone_number"},
            headers={"Authorization": f"Bearer {access_token}"},
        )
    if resp.status_code != 200:
        raise WhatsAppCredentialError(
            f"Token does not have access to phone_number_id={phone_number_id}: {resp.text}"
        )


async def _subscribe_app_to_waba(waba_id: str, access_token: str) -> None:
    url = f"{_META_GRAPH_BASE}/{_META_API_VERSION}/{waba_id}/subscribed_apps"
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(url, headers={"Authorization": f"Bearer {access_token}"})
    if resp.status_code != 200:
        logger.error("Failed to subscribe app to WABA %s: %s", waba_id, resp.text)
        raise WhatsAppCredentialError(f"Could not subscribe app to WABA {waba_id}")


def decrypt_token(ciphertext: str) -> str:
    f = Fernet(settings.fernet_key.encode("utf-8"))
    return f.decrypt(ciphertext.encode("utf-8")).decode("utf-8")
