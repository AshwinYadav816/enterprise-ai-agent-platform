from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import jwt
import pytest
from fastapi import Depends, FastAPI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth import REFRESH_COOKIE
from app.core.deps import CurrentUser, require_roles
from app.core.errors import AppError
from app.core.ratelimit import RateLimiter, hit
from app.core.security import JWT_ALGORITHM, expand_roles, hash_refresh_token
from app.models import RefreshToken, User, UserRole
from tests.conftest import FakeRedis
from tests.factories import make_org, make_user

API = "/api/v1"
PASSWORD = "correct-horse-battery"
SECRET = "test-secret-not-for-production-use-0123456789"


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def register(client: httpx.AsyncClient, email: str = "Ana@Acme.com") -> httpx.Response:
    return await client.post(
        f"{API}/auth/register",
        json={"org_name": "Acme", "full_name": "Ana Admin", "email": email, "password": PASSWORD},
    )


async def login(client: httpx.AsyncClient, email: str, password: str = PASSWORD) -> httpx.Response:
    return await client.post(f"{API}/auth/login", json={"email": email, "password": password})


def refresh_cookie(r: httpx.Response) -> str:
    return r.cookies[REFRESH_COOKIE]


async def call_refresh(client: httpx.AsyncClient, raw: str) -> httpx.Response:
    client.cookies.clear()
    client.cookies.set(REFRESH_COOKIE, raw)
    return await client.post(f"{API}/auth/refresh")


# --- register / login / me ------------------------------------------------------------------


async def test_register_login_me(client: httpx.AsyncClient, db: AsyncSession) -> None:
    r = await register(client)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["token_type"] == "bearer" and body["expires_in"] == 15 * 60
    assert body["user"]["role"] == "admin" and body["user"]["email"] == "ana@acme.com"
    assert body["must_change_password"] is False
    cookie = r.headers["set-cookie"].lower()
    assert "httponly" in cookie and "path=/api/v1/auth" in cookie and "samesite=lax" in cookie
    assert "secure" not in cookie  # only in prod

    r = await login(client, "ANA@acme.com")  # email is case-insensitive
    assert r.status_code == 200
    me = await client.get(f"{API}/users/me", headers=bearer(r.json()["access_token"]))
    assert me.status_code == 200 and me.json()["full_name"] == "Ana Admin"
    assert me.json()["last_login_at"] is not None

    user = await db.scalar(select(User).where(User.email == "ana@acme.com"))
    assert user is not None and user.password_hash.startswith("$argon2")
    tokens = (await db.scalars(select(RefreshToken).where(RefreshToken.user_id == user.id))).all()
    assert len(tokens) == 2 and refresh_cookie(r) not in {t.token_hash for t in tokens}  # hashed


async def test_register_duplicate_email_and_validation(
    client: httpx.AsyncClient, db: AsyncSession
) -> None:
    assert (await register(client)).status_code == 201
    dup = await register(client, email="ana@ACME.com")
    assert dup.status_code == 409 and dup.json()["error"]["code"] == "email_taken"
    short = await client.post(
        f"{API}/auth/register",
        json={"org_name": "X", "full_name": "Y", "email": "y@x.com", "password": "short"},
    )
    assert short.status_code == 422 and short.json()["error"]["details"][0]["field"] == "password"


async def test_wrong_password_and_unknown_email_look_identical(
    client: httpx.AsyncClient, db: AsyncSession
) -> None:
    user = await make_user(db, password=PASSWORD)
    wrong = await login(client, user.email, "wrong-password")
    unknown = await login(client, "nobody@example.com")
    assert wrong.status_code == unknown.status_code == 401
    assert (
        wrong.json()
        == unknown.json()
        == {"error": {"code": "invalid_credentials", "message": "Invalid email or password"}}
    )


# --- access tokens ---------------------------------------------------------------------------


def _token(user: User, **overrides: Any) -> str:
    now = datetime.now(UTC)
    claims = {
        "sub": str(user.id),
        "org": str(user.org_id),
        "role": user.role.value,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=5),
        **overrides,
    }
    return jwt.encode(claims, SECRET, algorithm=JWT_ALGORITHM)


@pytest.mark.parametrize(
    ("make_header", "code"),
    [
        (lambda u: {}, "not_authenticated"),
        (lambda u: bearer("garbled.token.value"), "invalid_token"),
        (
            lambda u: bearer(_token(u, exp=datetime.now(UTC) - timedelta(seconds=1))),
            "token_expired",
        ),
        (lambda u: bearer(jwt.encode({"sub": str(u.id)}, "x" * 32 + "-wrong")), "invalid_token"),
        (lambda u: bearer(_token(u, type="refresh")), "invalid_token"),
        (lambda u: bearer(_token(u, org="00000000-0000-0000-0000-000000000000")), "invalid_token"),
    ],
)
async def test_bad_access_tokens_are_401(
    client: httpx.AsyncClient, db: AsyncSession, make_header: Any, code: str
) -> None:
    user = await make_user(db)
    r = await client.get(f"{API}/users/me", headers=make_header(user))
    assert r.status_code == 401 and r.json()["error"]["code"] == code
    assert r.headers.get("www-authenticate") == "Bearer"


# --- refresh rotation / reuse / logout -----------------------------------------------------


async def test_refresh_rotates_and_detects_reuse(
    client: httpx.AsyncClient, db: AsyncSession
) -> None:
    user = await make_user(db, password=PASSWORD)
    first = refresh_cookie(await login(client, user.email))

    rotated = await call_refresh(client, first)
    assert rotated.status_code == 200 and rotated.json()["access_token"]
    second = refresh_cookie(rotated)
    assert second != first

    # replaying the old token = theft signal: it fails AND every session is revoked
    replay = await call_refresh(client, first)
    assert replay.status_code == 401 and replay.json()["error"]["code"] == "invalid_refresh_token"
    assert (await call_refresh(client, second)).status_code == 401
    active = await db.scalars(
        select(RefreshToken).where(
            RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None)
        )
    )
    assert active.all() == []


async def test_refresh_rejects_missing_unknown_and_expired(
    client: httpx.AsyncClient, db: AsyncSession
) -> None:
    client.cookies.clear()
    assert (await client.post(f"{API}/auth/refresh")).status_code == 401
    assert (await call_refresh(client, "not-a-real-token")).status_code == 401
    user = await make_user(db)
    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=hash_refresh_token("old-token"),
            expires_at=datetime.now(UTC) - timedelta(minutes=1),
        )
    )
    await db.flush()
    assert (await call_refresh(client, "old-token")).status_code == 401


async def test_logout_invalidates_refresh(client: httpx.AsyncClient, db: AsyncSession) -> None:
    user = await make_user(db, password=PASSWORD)
    token = refresh_cookie(await login(client, user.email))
    client.cookies.clear()
    client.cookies.set(REFRESH_COOKIE, token)
    out = await client.post(f"{API}/auth/logout")
    assert out.status_code == 204
    assert 'refresh_token=""' in out.headers["set-cookie"]  # cookie cleared
    assert (await call_refresh(client, token)).status_code == 401
    client.cookies.clear()
    assert (await client.post(f"{API}/auth/logout")).status_code == 204  # idempotent, no cookie


# --- inactive users / roles / forced password change -------------------------------------------


async def test_inactive_user_blocked(client: httpx.AsyncClient, db: AsyncSession) -> None:
    user = await make_user(db, password=PASSWORD)
    access = (await login(client, user.email)).json()["access_token"]
    user.is_active = False
    await db.flush()
    r = await login(client, user.email)
    assert r.status_code == 403 and r.json()["error"]["code"] == "account_disabled"
    r = await client.get(f"{API}/users/me", headers=bearer(access))  # old token stops working
    assert r.status_code == 403


@pytest.fixture
def app_with_protected_route(app: FastAPI) -> FastAPI:
    @app.get("/api/v1/_test/any")
    async def any_user(user: CurrentUser) -> dict[str, str]:
        return {"role": user.role.value}

    @app.get("/api/v1/_test/admin")
    async def admin_only(user: User = Depends(require_roles(UserRole.admin))) -> dict[str, str]:  # noqa: B008
        return {"ok": "yes"}

    return app


async def test_must_change_password_guard(
    app_with_protected_route: FastAPI, client: httpx.AsyncClient, db: AsyncSession
) -> None:
    user = await make_user(db, password="temp-password-1", must_change_password=True)
    r = await login(client, user.email, "temp-password-1")
    assert r.status_code == 200 and r.json()["must_change_password"] is True
    old_refresh, access = refresh_cookie(r), r.json()["access_token"]

    blocked = await client.get(f"{API}/_test/any", headers=bearer(access))
    assert blocked.status_code == 403
    assert blocked.json()["error"]["code"] == "password_change_required"
    assert (await client.get(f"{API}/users/me", headers=bearer(access))).status_code == 200

    changed = await client.post(
        f"{API}/users/me/password",
        headers=bearer(access),
        json={"current_password": "temp-password-1", "new_password": PASSWORD},
    )
    assert changed.status_code == 200 and changed.json()["must_change_password"] is False
    new_access = changed.json()["access_token"]
    assert (await client.get(f"{API}/_test/any", headers=bearer(new_access))).status_code == 200
    assert (await call_refresh(client, old_refresh)).status_code == 401  # other sessions revoked
    assert (await login(client, user.email)).status_code == 200  # new password works


async def test_change_password_errors(client: httpx.AsyncClient, db: AsyncSession) -> None:
    user = await make_user(db, password=PASSWORD)
    access = (await login(client, user.email)).json()["access_token"]
    url = f"{API}/users/me/password"
    wrong = await client.post(
        url, headers=bearer(access), json={"current_password": "nope", "new_password": "x" * 8}
    )
    assert wrong.status_code == 400 and wrong.json()["error"]["code"] == "invalid_password"
    same = await client.post(
        url, headers=bearer(access), json={"current_password": PASSWORD, "new_password": PASSWORD}
    )
    assert same.status_code == 400 and same.json()["error"]["code"] == "password_reused"


async def test_require_roles(
    app_with_protected_route: FastAPI, client: httpx.AsyncClient, db: AsyncSession
) -> None:
    org = await make_org(db)
    admin = await make_user(db, org, role=UserRole.admin, password=PASSWORD)
    employee = await make_user(db, org, role=UserRole.employee, password=PASSWORD)
    for user, expected in ((admin, 200), (employee, 403)):
        access = (await login(client, user.email)).json()["access_token"]
        r = await client.get(f"{API}/_test/admin", headers=bearer(access))
        assert r.status_code == expected


async def test_update_me(client: httpx.AsyncClient, db: AsyncSession) -> None:
    user = await make_user(db, password=PASSWORD)
    access = (await login(client, user.email)).json()["access_token"]
    r = await client.patch(
        f"{API}/users/me", headers=bearer(access), json={"full_name": "  New Name "}
    )
    assert r.status_code == 200 and r.json()["full_name"] == "New Name"


def test_expand_roles() -> None:
    assert expand_roles(UserRole.admin) == ["employee", "manager", "admin"]
    assert expand_roles("manager") == ["employee", "manager"]
    assert expand_roles(UserRole.employee) == ["employee"]


# --- rate limiting -----------------------------------------------------------------------------


async def test_login_rate_limit(
    client: httpx.AsyncClient, db: AsyncSession, fake_redis: FakeRedis
) -> None:
    user = await make_user(db, password=PASSWORD)
    for _ in range(5):
        assert (await login(client, user.email, "wrong")).status_code == 401
    blocked = await login(client, user.email)  # even the right password is blocked now
    assert blocked.status_code == 429 and blocked.json()["error"]["code"] == "rate_limited"
    assert blocked.headers["retry-after"] == "60"
    assert (await login(client, "someone-else@example.com")).status_code == 401  # per email
    assert all(ttl == 60 for ttl in fake_redis.ttls.values())


async def test_rate_limiter_fails_open() -> None:
    class DownRedis:
        async def incr(self, name: str) -> int:
            raise ConnectionError("redis down")

        async def expire(self, name: str, time: int) -> bool:
            raise ConnectionError("redis down")

    assert await hit(DownRedis(), "k", limit=1) is True
    await RateLimiter(DownRedis()).ai("user", "org")  # no exception


async def test_ai_limit_is_per_user_and_per_org(
    fake_redis: FakeRedis, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.core.config import get_settings

    monkeypatch.setenv("AI_PER_MIN", "2")
    monkeypatch.setenv("AI_ORG_PER_MIN", "3")
    get_settings.cache_clear()
    limiter = RateLimiter(fake_redis, clock=lambda: 1_000_000.0)
    await limiter.ai("u1", "org")
    await limiter.ai("u1", "org")
    with pytest.raises(AppError, match="Too many requests"):
        await limiter.ai("u1", "org")  # u1's 3rd call: over the per-user limit (2)
    await limiter.ai("u2", "org")  # org count now 3 = the org limit: still allowed
    with pytest.raises(AppError, match="Too many requests"):
        await limiter.ai("u3", "org")  # a fresh user, but the org is over its limit
    await limiter.ai("u4", "other-org")  # other orgs are unaffected


async def test_window_rolls_over(fake_redis: FakeRedis) -> None:
    now = [120.0]
    limiter = RateLimiter(fake_redis, clock=lambda: now[0])
    await limiter.check("k", limit=1)
    with pytest.raises(AppError):
        await limiter.check("k", limit=1)
    now[0] += 60  # next window
    await limiter.check("k", limit=1)
