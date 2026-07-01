import hashlib
import hmac

import pytest

from worker.adapters.whatsapp.security import (
    InvalidSignatureError,
    verify_handshake_token,
    verify_signature,
)


def _sign(body: bytes, secret: str) -> str:
    digest = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def test_verify_signature_accepts_valid_signature(monkeypatch):
    monkeypatch.setattr(
        "worker.adapters.whatsapp.security.settings.whatsapp_app_secret", "topsecret"
    )
    body = b'{"object":"whatsapp_business_account"}'
    header = _sign(body, "topsecret")
    verify_signature(body, header)  # should not raise


def test_verify_signature_rejects_tampered_body(monkeypatch):
    monkeypatch.setattr(
        "worker.adapters.whatsapp.security.settings.whatsapp_app_secret", "topsecret"
    )
    body = b'{"object":"whatsapp_business_account"}'
    header = _sign(body, "topsecret")
    tampered_body = body + b"x"
    with pytest.raises(InvalidSignatureError):
        verify_signature(tampered_body, header)


def test_verify_signature_rejects_missing_header(monkeypatch):
    monkeypatch.setattr(
        "worker.adapters.whatsapp.security.settings.whatsapp_app_secret", "topsecret"
    )
    with pytest.raises(InvalidSignatureError):
        verify_signature(b"{}", None)


def test_verify_signature_rejects_malformed_header(monkeypatch):
    monkeypatch.setattr(
        "worker.adapters.whatsapp.security.settings.whatsapp_app_secret", "topsecret"
    )
    with pytest.raises(InvalidSignatureError):
        verify_signature(b"{}", "not-sha256=abc")


def test_handshake_token_match(monkeypatch):
    monkeypatch.setattr(
        "worker.adapters.whatsapp.security.settings.whatsapp_verify_token", "mytoken"
    )
    assert verify_handshake_token("subscribe", "mytoken") is True
    assert verify_handshake_token("subscribe", "wrong") is False
    assert verify_handshake_token("not-subscribe", "mytoken") is False
