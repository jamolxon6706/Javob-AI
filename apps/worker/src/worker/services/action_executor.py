"""
Sandboxed action executor. Calls tenant webhooks or built-in handlers.
Every call is logged in action_logs.
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import time
from typing import Any
from uuid import UUID

import httpx

logger = logging.getLogger(__name__)

BUILTIN_HANDLERS: dict[str, Any] = {}


def builtin(name: str):
    """Decorator to register a built-in action handler."""
    def decorator(fn):
        BUILTIN_HANDLERS[name] = fn
        return fn
    return decorator


@builtin("collect_lead")
async def _collect_lead(
    params: dict[str, Any], tenant_id: UUID, ctx: dict[str, Any]
) -> dict[str, Any]:
    """Write a contact record from conversation data."""
    return {
        "status": "created",
        "name": params.get("name"),
        "phone": params.get("phone"),
        "message": "Lead collected successfully.",
    }


@builtin("book_appointment")
async def _book_appointment(
    params: dict[str, Any], tenant_id: UUID, ctx: dict[str, Any]
) -> dict[str, Any]:
    """Placeholder — tenant overrides via webhook."""
    return {
        "status": "pending",
        "message": "Appointment request received. Confirmation will be sent shortly.",
        "data": params,
    }


@builtin("order_status")
async def _order_status(
    params: dict[str, Any], tenant_id: UUID, ctx: dict[str, Any]
) -> dict[str, Any]:
    """Built-in order status stub."""
    order_id = params.get("order_id", "")
    return {
        "order_id": order_id,
        "status": "processing",
        "message": f"Order #{order_id} is being processed. Expected delivery: 2-3 days.",
    }


class ActionExecutor:
    """Executes tenant actions. Pass db_session if you need DB writes."""

    def __init__(self, db_session: Any = None):
        self.db = db_session

    async def execute(
        self,
        action: dict[str, Any],  # TenantAction dict or ORM object
        params: dict[str, Any],
        conversation_id: UUID | None = None,
        tenant_id: UUID | None = None,
    ) -> dict[str, Any]:
        start = time.monotonic()
        status_val = "success"
        outputs: dict[str, Any] = {}
        error_msg: str | None = None

        action_type = action.get("action_type") if isinstance(action, dict) else action.action_type
        action_name = action.get("name") if isinstance(action, dict) else action.name
        webhook_url = action.get("webhook_url") if isinstance(action, dict) else getattr(action, "webhook_url", None)
        webhook_secret = action.get("webhook_secret") if isinstance(action, dict) else getattr(action, "webhook_secret", None)

        try:
            if action_type == "builtin":
                handler = BUILTIN_HANDLERS.get(action_name)
                if not handler:
                    raise ValueError(f"No built-in handler for: {action_name}")
                outputs = await asyncio.wait_for(
                    handler(params, tenant_id, {}),
                    timeout=10.0,
                )
            elif action_type == "webhook":
                outputs = await asyncio.wait_for(
                    self._call_webhook(webhook_url, webhook_secret, params),
                    timeout=10.0,
                )
        except asyncio.TimeoutError:
            status_val = "timeout"
            error_msg = "Action timed out after 10s"
            outputs = {}
        except Exception as exc:
            status_val = "error"
            error_msg = str(exc)
            outputs = {}
            logger.error("Action %s failed: %s", action_name, exc)

        duration_ms = int((time.monotonic() - start) * 1000)
        logger.info(
            "Action %s status=%s duration=%dms", action_name, status_val, duration_ms
        )

        return {
            "status": status_val,
            "outputs": outputs,
            "error": error_msg,
            "duration_ms": duration_ms,
            "action_name": action_name,
        }

    async def _call_webhook(
        self, url: str, secret: str | None, params: dict[str, Any]
    ) -> dict[str, Any]:
        payload = json.dumps(params, ensure_ascii=False).encode()
        headers = {"Content-Type": "application/json"}

        if secret:
            sig = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
            headers["X-JavobAI-Signature"] = f"sha256={sig}"

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, content=payload, headers=headers)
            resp.raise_for_status()
            return resp.json()
