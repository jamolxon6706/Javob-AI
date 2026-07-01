import uuid

import pytest

from worker.adapters.whatsapp.normalizer import normalize_payload
from worker.adapters.whatsapp.schemas import WAWebhookPayload

TENANT_ID = uuid.uuid4()
CHANNEL_ID = uuid.uuid4()


def _payload_with_text(body: str) -> dict:
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "waba1",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "998901234567",
                                "phone_number_id": "pn1",
                            },
                            "contacts": [{"wa_id": "998991112233", "profile": {"name": "Ali"}}],
                            "messages": [
                                {
                                    "id": "wamid.1",
                                    "from": "998991112233",
                                    "timestamp": "1700000000",
                                    "type": "text",
                                    "text": {"body": body},
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }


async def test_normalize_text_message():
    payload = WAWebhookPayload.model_validate(_payload_with_text("Buyurtmam qayerda?"))
    messages = await normalize_payload(payload, tenant_id=TENANT_ID, channel_id=CHANNEL_ID)

    assert len(messages) == 1
    msg = messages[0]
    assert msg.platform == "whatsapp"
    assert msg.external_user_id == "998991112233"
    assert msg.text == "Buyurtmam qayerda?"
    assert msg.conversation_id == f"{CHANNEL_ID}:998991112233"
    assert msg.media == []


async def test_normalize_audio_message_transcribes(monkeypatch):
    payload_dict = _payload_with_text("")
    payload_dict["entry"][0]["changes"][0]["value"]["messages"][0] = {
        "id": "wamid.2",
        "from": "998991112233",
        "timestamp": "1700000001",
        "type": "audio",
        "audio": {"id": "media123", "mime_type": "audio/ogg"},
    }
    payload = WAWebhookPayload.model_validate(payload_dict)

    async def fake_download(media_id, **kwargs):
        return "/tmp/fake.ogg"

    async def fake_transcribe(local_path):
        return "Mahsulot qachon yetib keladi"

    monkeypatch.setattr("worker.adapters.whatsapp.normalizer.download_media", fake_download)
    monkeypatch.setattr("worker.adapters.whatsapp.normalizer.transcribe_audio", fake_transcribe)

    messages = await normalize_payload(payload, tenant_id=TENANT_ID, channel_id=CHANNEL_ID)

    assert len(messages) == 1
    msg = messages[0]
    assert msg.text == "Mahsulot qachon yetib keladi"
    assert msg.media[0].type == "audio"
    assert msg.media[0].url == "/tmp/fake.ogg"
    assert msg.media[0].mime_type == "audio/ogg"
