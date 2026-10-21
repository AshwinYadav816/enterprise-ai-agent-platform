from fastapi import APIRouter, Response

from app.api.v1.auth import session_response
from app.core.db import DbSession
from app.core.deps import ClientIP, CurrentUserAllowPasswordChange
from app.schemas.auth import TokenResponse
from app.schemas.users import ChangePasswordRequest, UpdateMeRequest, UserOut
from app.services import auth as auth_service

router = APIRouter(prefix="/users", tags=["users"])

# These routes stay reachable while must_change_password is set (temporary password flow).


@router.get("/me")
async def get_me(user: CurrentUserAllowPasswordChange) -> UserOut:
    return UserOut.model_validate(user)


@router.patch("/me")
async def update_me(
    data: UpdateMeRequest, user: CurrentUserAllowPasswordChange, db: DbSession
) -> UserOut:
    user.full_name = data.full_name.strip()
    await db.flush()
    return UserOut.model_validate(user)


@router.post("/me/password")
async def change_password(
    data: ChangePasswordRequest,
    user: CurrentUserAllowPasswordChange,
    db: DbSession,
    response: Response,
    ip: ClientIP,
) -> TokenResponse:
    """Change password. All sessions are signed out; a fresh one is returned for this device."""
    session = await auth_service.change_password(
        db, user, data.current_password, data.new_password, ip
    )
    return session_response(response, session)
