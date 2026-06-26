import logging
import random
import string
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from javobai.config import settings
from javobai.db.models import Tenant, User

logger = logging.getLogger(__name__)

ALGORITHM = "HS256"


def _otp_key(phone: str) -> str:
    return f"otp:{phone}"


def _refresh_key(token: str) -> str:
    return f"refresh:{token}"


async def send_otp(phone: str, redis: Redis) -> str:  # type: ignore[type-arg]
    otp = "".join(random.choices(string.digits, k=6))
    await redis.setex(_otp_key(phone), settings.otp_ttl_seconds, otp)
    # In production: send via SMS gateway (Eskiz.uz)
    # For dev: log the OTP
    logger.info("OTP for %s: %s", phone, otp)
    return otp


async def verify_otp(phone: str, otp: str, redis: Redis) -> bool:  # type: ignore[type-arg]
    stored = await redis.get(_otp_key(phone))
    if not stored:
        return False
    if stored.decode() != otp:
        return False
    await redis.delete(_otp_key(phone))
    return True


def _make_access_token(user_id: str, tenant_id: str, phone: str, role: str) -> str:
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=settings.jwt_access_expire_minutes)
    return jwt.encode(
        {
            "sub": user_id,
            "tenant_id": tenant_id,
            "phone": phone,
            "role": role,
            "iat": now,
            "exp": expire,
            "type": "access",
        },
        settings.jwt_secret,
        algorithm=ALGORITHM,
    )


def _make_refresh_token(user_id: str, tenant_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=settings.jwt_refresh_expire_days)
    return jwt.encode(
        {
            "sub": user_id,
            "tenant_id": tenant_id,
            "exp": expire,
            "type": "refresh",
        },
        settings.jwt_secret,
        algorithm=ALGORITHM,
    )


async def issue_tokens(
    user: User, redis: Redis  # type: ignore[type-arg]
) -> tuple[str, str]:
    access = _make_access_token(user.id, user.tenant_id, user.phone, user.role)
    refresh = _make_refresh_token(user.id, user.tenant_id)
    ttl = settings.jwt_refresh_expire_days * 86400
    await redis.setex(_refresh_key(refresh), ttl, user.id)
    return access, refresh


def decode_token(token: str) -> dict:  # type: ignore[type-arg]
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM])
    except JWTError as exc:
        raise ValueError("Invalid token") from exc


async def refresh_access_token(
    refresh_token: str, redis: Redis, db: AsyncSession  # type: ignore[type-arg]
) -> tuple[str, str]:
    payload = decode_token(refresh_token)
    if payload.get("type") != "refresh":
        raise ValueError("Not a refresh token")

    stored = await redis.get(_refresh_key(refresh_token))
    if not stored:
        raise ValueError("Refresh token revoked or expired")

    user_id: str = payload["sub"]
    result = await db.execute(select(User).where(User.id == user_id, User.is_active == True))  # noqa: E712
    user = result.scalar_one_or_none()
    if not user:
        raise ValueError("User not found")

    # Rotate: revoke old, issue new
    await redis.delete(_refresh_key(refresh_token))
    return await issue_tokens(user, redis)


async def revoke_refresh_token(refresh_token: str, redis: Redis) -> bool:  # type: ignore[type-arg]
    """
    Best-effort revocation: delete the refresh:{token} Redis key so the token
    cannot be used to mint new access tokens. Returns True if a key was removed.
    Safe to call with garbage input — JWT decode errors are logged and ignored.
    """
    try:
        payload = decode_token(refresh_token)
    except ValueError:
        logger.info("revoke_refresh_token: token failed to decode; nothing to revoke")
        return False
    if payload.get("type") != "refresh":
        logger.info("revoke_refresh_token: not a refresh token; nothing to revoke")
        return False
    removed = await redis.delete(_refresh_key(refresh_token))
    return bool(removed)


async def get_or_create_user(phone: str, db: AsyncSession) -> User:
    """Return existing user for phone, or create a tenant+user pair."""
    result = await db.execute(select(User).where(User.phone == phone, User.is_active == True))  # noqa: E712
    user = result.scalar_one_or_none()
    if user:
        return user

    # New user → create a default tenant
    tenant = Tenant(name=f"Tenant {phone}", slug=phone.replace("+", "").replace(" ", ""))
    db.add(tenant)
    await db.flush()  # get tenant.id

    user = User(tenant_id=tenant.id, phone=phone, role="owner")
    db.add(user)
    await db.flush()
    return user
