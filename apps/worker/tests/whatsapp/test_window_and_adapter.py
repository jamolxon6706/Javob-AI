from datetime import datetime, timedelta, timezone

import pytest
import fakeredis.aioredis

from worker.adapters.whatsapp import window
from worker.adapters.whatsapp.adapter import TemplateRequiredError, WhatsAppAdapter


@pytest.fixture
async def redis():
    r = fakeredis.aioredis.FakeRedis()
    yield r
    await r.aclose()


async def test_window_closed_before_first_inbound(redis):
    assert await window.is_window_open(redis, "chan1", "99899xxxxxxx") is False


async def test_window_open_immediately_after_inbound(redis):
    await window.mark_inbound(redis, "chan1", "99899xxxxxxx")
    assert await window.is_window_open(redis, "chan1", "99899xxxxxxx") is True


async def test_window_closes_after_24h(redis):
    now = datetime.now(timezone.utc)
    await window.mark_inbound(redis, "chan1", "99899xxxxxxx", now=now)

    just_before_expiry = now + timedelta(hours=23, minutes=59)
    assert await window.is_window_open(redis, "chan1", "99899xxxxxxx", now=just_before_expiry) is True

    just_after_expiry = now + timedelta(hours=24, minutes=1)
    assert await window.is_window_open(redis, "chan1", "99899xxxxxxx", now=just_after_expiry) is False


async def test_send_text_raises_when_window_closed(redis, monkeypatch):
    adapter = WhatsAppAdapter(phone_number_id="pn1", access_token="tok", redis=redis)
    with pytest.raises(TemplateRequiredError):
        await adapter.send_text(channel_id="chan1", to="99899xxxxxxx", text="salom")


async def test_send_text_succeeds_inside_window(redis, monkeypatch):
    await window.mark_inbound(redis, "chan1", "99899xxxxxxx")
    adapter = WhatsAppAdapter(phone_number_id="pn1", access_token="tok", redis=redis)

    async def fake_post(self, payload, **kwargs):
        assert payload["type"] == "text"
        assert payload["text"]["body"] == "salom"
        return {"messages": [{"id": "wamid.fake"}]}

    monkeypatch.setattr(WhatsAppAdapter, "_post", fake_post)
    result = await adapter.send_text(channel_id="chan1", to="99899xxxxxxx", text="salom")
    assert result["messages"][0]["id"] == "wamid.fake"
