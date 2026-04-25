"""Authentication endpoints: register, login, current user."""

from fastapi import APIRouter, Depends, Request
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from app.services.security.auth_service import authenticate_user, register_user

router = APIRouter(prefix="/auth", tags=["auth"])
_limiter = Limiter(key_func=get_remote_address)


@router.post("/register", response_model=UserResponse, status_code=201)
@_limiter.limit("5/minute")
async def register(
    request: Request,
    body: RegisterRequest,
    db: AsyncSession = Depends(get_db),
):
    user = await register_user(
        email=body.email,
        password=body.password,
        pref_lang=body.pref_lang,
        db=db,
    )
    return user


@router.post("/login", response_model=TokenResponse)
@_limiter.limit("10/minute")
async def login(
    request: Request,
    body: LoginRequest,
    db: AsyncSession = Depends(get_db),
):
    user = await authenticate_user(
        email=body.email,
        password=body.password,
        db=db,
    )
    token = create_access_token({"sub": str(user.id), "tier": user.membership_tier.value})
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserResponse)
async def me(current_user: User = Depends(get_current_user)):
    return current_user
