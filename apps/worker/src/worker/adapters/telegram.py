import asyncio
import logging

import httpx

logger = logging.getLogger(__name__)

TG_API = "https://api.telegram.org/bot{token}/{method}"
_RETRY_DELAYS = [1, 2, 4]  # seconds, exponential backoff


async def send_message(
    bot_token: str,
    chat_id: str,
    text: str,
    parse_mode: str = "HTML",
) -> dict:  # type: ignore[type-arg]
    """Send a text message. Retries on 429 / transient errors."""
    url = TG_API.format(token=bot_token, method="sendMessage")
    payload = {"chat_id": chat_id, "text": text, "parse_mode": parse_mode}

    async with httpx.AsyncClient(timeout=10) as client:
        for attempt, delay in enumerate(_RETRY_DELAYS + [None], start=1):  # type: ignore[operator]
            try:
                resp = await client.post(url, json=payload)
                if resp.status_code == 429:
                    retry_after = int(resp.headers.get("Retry-After", delay or 4))
                    logger.warning("Telegram rate-limited; retrying after %ds", retry_after)
                    await asyncio.sleep(retry_after)
                    continue
                resp.raise_for_status()
                return resp.json()
            except httpx.HTTPStatusError as exc:
                if delay is None:
                    logger.error("Telegram sendMessage failed permanently: %s", exc)
                    raise
                logger.warning("sendMessage attempt %d failed: %s", attempt, exc)
                await asyncio.sleep(delay)

    raise RuntimeError("send_message: exhausted retries")
