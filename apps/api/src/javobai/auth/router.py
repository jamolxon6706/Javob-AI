from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from javobai.auth import service
from javobai.auth.cookies import clear_auth_cookies, set_auth_cookies
from javobai.auth.deps import CurrentUser
from javobai.config import settings
from javobai.db.session import get_db
from javobai.redis import get_redis

router = APIRouter(prefix="/auth", tags=["auth"])


class RequestOTPIn(BaseModel):
    phone: str


class RequestOTPOut(BaseModel):
    detail: str
    # Only returned in non-production environments for dev convenience
    otp: str | None = None


class VerifyOTPIn(BaseModel):
    phone: str
    otp: str


class TokenOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"  # noqa: S105


class RefreshIn(BaseModel):
    refresh_token: str


class MeOut(BaseModel):
    id: str
    tenant_id: str
    phone: str
    name: str | None
    role: str


@router.post("/request-otp", response_model=RequestOTPOut)
async def request_otp(
    body: RequestOTPIn,
    redis: Annotated[Redis, Depends(get_redis)],  # type: ignore[type-arg]
    db: Annotated[AsyncSession, Depends(get_db)],
) -> RequestOTPOut:
    from javobai.config import settings

    otp = await service.send_otp(body.phone, redis)
    # Expose OTP in response only in non-production (dev convenience)
    expose = otp if settings.environment != "production" else None
    return RequestOTPOut(detail="OTP sent", otp=expose)


@router.post("/verify", response_model=TokenOut)
async def verify(
    body: VerifyOTPIn,
    response: Response,
    redis: Annotated[Redis, Depends(get_redis)],  # type: ignore[type-arg]
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TokenOut:
    valid = await service.verify_otp(body.phone, body.otp, redis)
    if not valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OTP"
        )

    user = await service.get_or_create_user(body.phone, db)
    access, refresh = await service.issue_tokens(user, redis)
    # Phase 6: also stash HttpOnly cookies so the dashboard BFF can forward them.
    set_auth_cookies(response, access=access, refresh=refresh, settings=settings)
    return TokenOut(access_token=access, refresh_token=refresh)


@router.post("/refresh", response_model=TokenOut)
async def refresh(
    body: RefreshIn,
    response: Response,
    redis: Annotated[Redis, Depends(get_redis)],  # type: ignore[type-arg]
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TokenOut:
    try:
        access, new_refresh = await service.refresh_access_token(body.refresh_token, redis, db)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    set_auth_cookies(response, access=access, refresh=new_refresh, settings=settings)
    return TokenOut(access_token=access, refresh_token=new_refresh)


class LogoutIn(BaseModel):
    refresh_token: str


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    body: LogoutIn,
    response: Response,
    redis: Annotated[Redis, Depends(get_redis)],  # type: ignore[type-arg]
) -> Response:
    """Revoke the refresh token server-side and clear both cookies on the browser."""
    await service.revoke_refresh_token(body.refresh_token, redis)
    clear_auth_cookies(response, settings=settings)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/me", response_model=MeOut)
async def me(current_user: CurrentUser) -> MeOut:
    return MeOut(
        id=current_user.id,
        tenant_id=current_user.tenant_id,
        phone=current_user.phone,
        name=current_user.name,
        role=current_user.role,
    )
