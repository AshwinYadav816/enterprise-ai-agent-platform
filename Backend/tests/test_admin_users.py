import uuid
from datetime import UTC, datetime

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.pagination import decode_cursor, encode_cursor
from app.models import AuditLog, Organization, RefreshToken, User, UserRole
from app.services import audit
from app.services.users import TEMP_PASSWORD_LENGTH, _ensure_another_active_admin
from tests.factories import make_org, make_user

API = "/api/v1"
PASSWORD = "correct-horse-battery"


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def login(client: httpx.AsyncClient, email: str, password: str = PASSWORD) -> httpx.Response:
    return await client.post(f"{API}/auth/login", json={"email": email, "password": password})


async def token_for(client: httpx.AsyncClient, user: User, password: str = PASSWORD) -> str:
    r = await login(client, user.email, password)
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


async def admin_setup(
    client: httpx.AsyncClient, db: AsyncSession
) -> tuple[Organization, User, dict[str, str]]:
    org = await make_org(db, "Acme")
    admin = await make_user(db, org, role=UserRole.admin, email="boss@acme.com", password=PASSWORD)
    return org, admin, bearer(await token_for(client, admin))


async def actions(db: AsyncSession, org_id: uuid.UUID) -> list[str]:
    rows = await db.scalars(
        select(AuditLog.action).where(AuditLog.org_id == org_id).order_by(AuditLog.created_at)
    )
    return list(rows)


# --- the "Done when" flow ------------------------------------------------------------------


async def test_admin_creates_users_who_must_change_temp_password(
    client: httpx.AsyncClient, db: AsyncSession
) -> None:
    org, _, h = await admin_setup(client, db)
    for email, role in (("mina@acme.com", "manager"), ("eli@acme.com", "employee")):
        r = await client.post(
            f"{API}/admin/users",
            headers=h,
            json={"email": email.upper(), "full_name": "New Person", "role": role},
        )
        assert r.status_code == 201, r.text
        body = r.json()
        temp = body["temporary_password"]
        assert len(temp) == TEMP_PASSWORD_LENGTH
        assert (
            body["user"] | {"email": email, "role": role, "must_change_password": True}
            == body["user"]
        )

        first = await login(client, email, temp)
        assert first.status_code == 200 and first.json()["must_change_password"] is True
        changed = await client.post(
            f"{API}/users/me/password",
            headers=bearer(first.json()["access_token"]),
            json={"current_password": temp, "new_password": f"{role}-new-password"},
        )
        assert changed.status_code == 200 and changed.json()["must_change_password"] is False
        assert (await login(client, email, f"{role}-new-password")).status_code == 200

    stored = await db.scalar(select(User).where(User.email == "eli@acme.com"))
    assert stored is not None and stored.password_hash.startswith("$argon2")  # temp never stored


async def test_create_user_duplicate_email(client: httpx.AsyncClient, db: AsyncSession) -> None:
    _, admin, h = await admin_setup(client, db)
    r = await client.post(
        f"{API}/admin/users", headers=h, json={"email": admin.email, "full_name": "Dup"}
    )
    assert r.status_code == 409 and r.json()["error"]["code"] == "email_taken"


# --- access control -----------------------------------------------------------------------


@pytest.mark.parametrize("role", [UserRole.manager, UserRole.employee])
async def test_non_admin_gets_403(
    client: httpx.AsyncClient, db: AsyncSession, role: UserRole
) -> None:
    user = await make_user(db, role=role, password=PASSWORD)
    h = bearer(await token_for(client, user))
    for method, path in (
        ("GET", "/admin/users"),
        ("POST", "/admin/users"),
        ("PATCH", f"/admin/users/{user.id}"),
        ("GET", "/admin/activity"),
    ):
        r = await client.request(method, f"{API}{path}", headers=h, json={"role": "admin"})
        assert r.status_code == 403, (method, path)


async def test_cross_org_user_is_404(client: httpx.AsyncClient, db: AsyncSession) -> None:
    _, _, h = await admin_setup(client, db)
    outsider = await make_user(db, await make_org(db, "Globex"))
    r = await client.patch(f"{API}/admin/users/{outsider.id}", headers=h, json={"role": "admin"})
    assert r.status_code == 404 and r.json()["error"]["code"] == "not_found"
    await db.refresh(outsider)
    assert outsider.role is UserRole.employee
    missing = await client.patch(
        f"{API}/admin/users/{uuid.uuid4()}", headers=h, json={"role": "admin"}
    )
    assert missing.json() == r.json()  # indistinguishable from a missing user


# --- listing / pagination --------------------------------------------------------------------


async def test_list_users_search_filter_and_org_isolation(
    client: httpx.AsyncClient, db: AsyncSession
) -> None:
    org, _, h = await admin_setup(client, db)
    await make_user(db, org, role=UserRole.manager, full_name="Priya Sharma", email="ps@acme.com")
    await make_user(db, org, full_name="Rahul Verma", email="rahul@acme.com")
    await make_user(db, org, full_name="100% Literal", email="pct@acme.com")
    await make_user(db, await make_org(db, "Globex"), full_name="Priya Other")

    async def names(**params: str) -> set[str]:
        r = await client.get(f"{API}/admin/users", headers=h, params=params)
        assert r.status_code == 200
        return {u["full_name"] for u in r.json()["items"]}

    assert await names(search="priya") == {"Priya Sharma"}  # other org's Priya not visible
    assert await names(search="RAHUL@") == {"Rahul Verma"}
    assert await names(role="manager") == {"Priya Sharma"}
    assert await names(search="%") == {"100% Literal"}  # % is literal, not a wildcard
    assert len(await names()) == 4


async def test_pagination_walks_all_users_once(client: httpx.AsyncClient, db: AsyncSession) -> None:
    org, _, h = await admin_setup(client, db)
    for i in range(5):
        await make_user(db, org, email=f"u{i}@acme.com")
    seen: list[str] = []
    cursor = None
    while True:
        params = {"limit": "2"} | ({"cursor": cursor} if cursor else {})
        page = (await client.get(f"{API}/admin/users", headers=h, params=params)).json()
        seen += [u["email"] for u in page["items"]]
        cursor = page["next_cursor"]
        if not cursor:
            break
    assert len(seen) == 6 and len(set(seen)) == 6  # 5 + admin, no duplicates or gaps

    bad = await client.get(f"{API}/admin/users", headers=h, params={"cursor": "garbage!"})
    assert bad.status_code == 400 and bad.json()["error"]["code"] == "invalid_cursor"
    too_big = await client.get(f"{API}/admin/users", headers=h, params={"limit": "500"})
    assert too_big.status_code == 422


def test_cursor_roundtrip() -> None:
    t, i = datetime(2026, 10, 22, 9, 30, tzinfo=UTC), uuid.uuid4()
    assert decode_cursor(encode_cursor(t, i)) == (t, i)


# --- guards ------------------------------------------------------------------------------------


async def test_admin_cannot_demote_or_deactivate_self(
    client: httpx.AsyncClient, db: AsyncSession
) -> None:
    _, admin, h = await admin_setup(client, db)
    for body in ({"role": "manager"}, {"is_active": False}):
        r = await client.patch(f"{API}/admin/users/{admin.id}", headers=h, json=body)
        assert r.status_code == 400 and r.json()["error"]["code"] == "cannot_modify_self"
    empty = await client.patch(f"{API}/admin/users/{admin.id}", headers=h, json={})
    assert empty.status_code == 422


async def test_admin_can_demote_another_admin(client: httpx.AsyncClient, db: AsyncSession) -> None:
    org, _, h = await admin_setup(client, db)
    other = await make_user(db, org, role=UserRole.admin)
    r = await client.patch(f"{API}/admin/users/{other.id}", headers=h, json={"role": "employee"})
    assert r.status_code == 200 and r.json()["role"] == "employee"


async def test_last_admin_guard(db: AsyncSession) -> None:
    org = await make_org(db)
    only_admin = await make_user(db, org, role=UserRole.admin)
    with pytest.raises(AppError) as err:
        await _ensure_another_active_admin(db, org.id, only_admin.id)
    assert err.value.code == "last_admin" and err.value.status == 409
    second = await make_user(db, org, role=UserRole.admin)
    await _ensure_another_active_admin(db, org.id, only_admin.id)  # ok now
    second.is_active = False
    await db.flush()
    with pytest.raises(AppError):  # inactive admins don't count
        await _ensure_another_active_admin(db, org.id, only_admin.id)


async def test_deactivation_revokes_sessions_and_reactivation_works(
    client: httpx.AsyncClient, db: AsyncSession
) -> None:
    org, _, h = await admin_setup(client, db)
    user = await make_user(db, org, password=PASSWORD)
    r = await login(client, user.email)
    access, refresh_cookie = r.json()["access_token"], r.cookies["refresh_token"]

    off = await client.patch(f"{API}/admin/users/{user.id}", headers=h, json={"is_active": False})
    assert off.status_code == 200 and off.json()["is_active"] is False
    active = await db.scalars(
        select(RefreshToken).where(
            RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None)
        )
    )
    assert active.all() == []
    client.cookies.set("refresh_token", refresh_cookie)
    assert (await client.post(f"{API}/auth/refresh")).status_code == 401
    assert (await client.get(f"{API}/users/me", headers=bearer(access))).status_code == 403

    on = await client.patch(f"{API}/admin/users/{user.id}", headers=h, json={"is_active": True})
    assert on.status_code == 200 and (await login(client, user.email)).status_code == 200


# --- audit log ------------------------------------------------------------------------------------


async def test_audit_rows_written(client: httpx.AsyncClient, db: AsyncSession) -> None:
    r = await client.post(
        f"{API}/auth/register",
        json={
            "org_name": "Initech",
            "full_name": "Ina Admin",
            "email": "ina@initech.com",
            "password": PASSWORD,
        },
    )
    h = bearer(r.json()["access_token"])
    org_id = uuid.UUID(r.json()["user"]["org_id"])

    assert (await login(client, "ina@initech.com", "wrong-password")).status_code == 401
    assert (await login(client, "nobody@initech.com", "x")).status_code == 401  # no org: not stored
    h = bearer(await token_for(client, await db.scalar(select(User).where(User.org_id == org_id))))

    created = await client.post(
        f"{API}/admin/users", headers=h, json={"email": "bob@initech.com", "full_name": "Bob"}
    )
    bob_id = created.json()["user"]["id"]
    await client.patch(f"{API}/admin/users/{bob_id}", headers=h, json={"role": "manager"})
    await client.patch(f"{API}/admin/users/{bob_id}", headers=h, json={"is_active": False})
    await client.post(
        f"{API}/users/me/password",
        headers=h,
        json={"current_password": PASSWORD, "new_password": "brand-new-password"},
    )

    assert await actions(db, org_id) == [
        audit.REGISTER,
        audit.LOGIN_FAILED,
        audit.LOGIN,
        audit.USER_CREATED,
        audit.ROLE_CHANGED,
        audit.USER_DEACTIVATED,
        audit.PASSWORD_CHANGED,
    ]
    failed = await db.scalar(select(AuditLog).where(AuditLog.action == audit.LOGIN_FAILED))
    assert failed is not None and failed.user_id is None
    assert failed.meta == {"email": "ina@initech.com"} and failed.ip
    role = await db.scalar(select(AuditLog).where(AuditLog.action == audit.ROLE_CHANGED))
    assert role is not None and role.meta == {"from": "employee", "to": "manager"}


async def test_activity_endpoint_filters_and_isolation(
    client: httpx.AsyncClient, db: AsyncSession
) -> None:
    org, admin, h = await admin_setup(client, db)  # admin_setup logged in once
    other_org = await make_org(db, "Globex")
    await audit.log(db, org_id=other_org.id, user_id=None, action="auth.login")
    await client.post(
        f"{API}/admin/users", headers=h, json={"email": "new@acme.com", "full_name": "New"}
    )

    page = (await client.get(f"{API}/admin/activity", headers=h)).json()
    assert [i["action"] for i in page["items"]] == [audit.USER_CREATED, audit.LOGIN]  # newest first
    assert page["items"][0]["user_email"] == admin.email and page["next_cursor"] is None

    only_logins = await client.get(
        f"{API}/admin/activity", headers=h, params={"action": audit.LOGIN}
    )
    assert [i["action"] for i in only_logins.json()["items"]] == [audit.LOGIN]  # not Globex's
    by_user = await client.get(
        f"{API}/admin/activity", headers=h, params={"user_id": str(admin.id), "limit": "1"}
    )
    assert len(by_user.json()["items"]) == 1 and by_user.json()["next_cursor"]
