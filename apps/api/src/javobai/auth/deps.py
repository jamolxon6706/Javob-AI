from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from javobai.auth.service import decode_token
from javobai.db.models import Tenant, User
from javobai.db.session import get_db

bearer = HTTPBearer()


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    token = credentials.credentials
    try:
        payload = decode_token(token)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from None

    if payload.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not an access token")

    user_id: str = payload["sub"]
    result = await db.execute(select(User).where(User.id == user_id, User.is_active == True))  # noqa: E712
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


async def get_current_tenant(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Tenant:
    result = await db.execute(
        select(Tenant).where(Tenant.id == current_user.tenant_id, Tenant.is_active == True)  # noqa: E712
    )
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant not found")
    return tenant


CurrentUser = Annotated[User, Depends(get_current_user)]
CurrentTenant = Annotated[Tenant, Depends(get_current_tenant)]
