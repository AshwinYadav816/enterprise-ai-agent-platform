from typing import Annotated

from fastapi import APIRouter, Cookie, Response, status

from app.core.config import get_settings
from app.core.db import DbSession
from app.core.deps import ClientIP
from app.core.ratelimit import Limiter
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse
from app.schemas.users import UserOut
from app.services import auth as auth_service

router = APIRouter(prefix="/auth", tags=["auth"])

REFRESH_COOKIE = "refresh_token"
REFRESH_COOKIE_PATH = "/api/v1/auth"  # the browser sends it only to auth endpoints

RefreshCookie = Annotated[str | None, Cookie(alias=REFRESH_COOKIE, include_in_schema=False)]


def set_refresh_cookie(response: Response, raw_token: str) -> None:
    s = get_settings()
    response.set_cookie(
        REFRESH_COOKIE,
        raw_token,
        max_age=s.refresh_token_days * 24 * 3600,
        path=REFRESH_COOKIE_PATH,
        httponly=True,
        secure=s.env == "prod",
        samesite="lax",
    )


def clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(REFRESH_COOKIE, path=REFRESH_COOKIE_PATH)


def session_response(response: Response, session: auth_service.Session) -> TokenResponse:
    set_refresh_cookie(response, session.refresh_token)
    return TokenResponse(
        access_token=session.access_token,
        expires_in=session.expires_in,
        must_change_password=session.user.must_change_password,
        user=UserOut.model_validate(session.user),
    )


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(
    data: RegisterRequest, db: DbSession, response: Response, ip: ClientIP
) -> TokenResponse:
    """Create a new organization and its first admin, and log them in."""
    return session_response(response, await auth_service.register(db, data, ip))


@router.post("/login")
async def login(
    data: LoginRequest, db: DbSession, response: Response, ip: ClientIP, limiter: Limiter
) -> TokenResponse:
    await limiter.login(ip, data.email)
    return session_response(response, await auth_service.login(db, data, ip))


@router.post("/refresh")
async def refresh(db: DbSession, response: Response, token: RefreshCookie = None) -> TokenResponse:
    """Exchange the refresh cookie for a new access token (the cookie is rotated)."""
    return session_response(response, await auth_service.refresh(db, token))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(db: DbSession, response: Response, token: RefreshCookie = None) -> None:
    await auth_service.logout(db, token)
    clear_refresh_cookie(response)
