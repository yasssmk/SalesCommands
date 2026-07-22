# backend/tests/integration/end_users/test_current_user_role_tier.py
"""
GET /client/user/ must expose `role_tier` inside the returned `user` object.

This hits the REAL endpoint. UserCurrentView returns a hand-built dict
{"success": True, "user": {...}} (the UserSerializer instance there is dead
code), so the tier must live in that dict — asserting the serializer in
isolation proved nothing. Without role_tier here the frontend defaulted every
tier to 'mine'.

RED REPRO: on the current code the `user` dict carries no role_tier, so
`assert "role_tier" in user` fails. It goes green once role_tier is added to
the /me dict (UserCurrentView).
"""

import uuid

import pytest
from rest_framework.test import APIClient

from end_users.models import User, UserRole, ClientAccount

URL = "/client/user/"


@pytest.fixture(autouse=True)
def _jwt_only_no_csrf(settings):
    rf = dict(getattr(settings, "REST_FRAMEWORK", {}))
    rf["DEFAULT_AUTHENTICATION_CLASSES"] = (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    )
    settings.REST_FRAMEWORK = rf
    settings.MIDDLEWARE = [
        m for m in settings.MIDDLEWARE
        if m != "django.middleware.csrf.CsrfViewMiddleware"
    ]


@pytest.fixture
def api():
    return APIClient(enforce_csrf_checks=False)


@pytest.fixture
def client_account(db):
    return ClientAccount.objects.create(
        id=uuid.uuid4(), name="Company A", is_b2b=True, max_users=100
    )


def _role(client_account, *, is_admin=False, is_manager=False, is_individual=False):
    # Unique name so this never collides with roles the client_account fixture
    # already seeds (e.g. a default "Admin"), which would violate the
    # (name, client_account) unique constraint. The tier comes from the flags via
    # get_tier(), not the name, so a suffixed name does not affect the assertion.
    base = "Admin" if is_admin else "Manager" if is_manager else "Individual"
    name = f"{base}-{uuid.uuid4().hex[:8]}"
    return UserRole.objects.create(
        client_account=client_account,
        name=name,
        is_admin=is_admin,
        is_manager=is_manager,
        is_individual=is_individual,
        read=True,
        write=True,
        modify=True,
        can_delete=is_admin,
    )


def _user(client_account, role, email):
    return User.objects.create(
        email=email, client_account=client_account, role=role, is_active=True
    )


def _authenticate(api, user, client_id):
    role = user.role
    claims = {
        "origin": "end_users",
        "user_id": str(user.id),
        "client_account": str(client_id),
        "role": {
            "id": str(role.id) if role else "",
            "name": role.name if role else "",
            "is_admin": bool(getattr(role, "is_admin", False)),
            "is_manager": bool(getattr(role, "is_manager", False)),
            "is_individual": bool(getattr(role, "is_individual", False)),
        },
        "is_superuser": bool(user.is_superuser),
    }
    api.force_authenticate(user=user, token=claims)
    api.credentials(
        HTTP_X_CLIENT_ID=str(client_id),
        HTTP_CLIENT_ID=str(client_id),
        HTTP_X_TENANT_ID=str(client_id),
        HTTP_TENANT=str(client_id),
        HTTP_AUTHORIZATION="Bearer test-token",
    )
    api.cookies["access_token"] = "test.jwt.token"


def _user_payload(resp):
    """Unwrap the /client/user/ envelope: {'success': True, 'user': {...}}."""
    body = resp.data
    return body["user"] if isinstance(body, dict) and "user" in body else body


@pytest.mark.django_db
@pytest.mark.parametrize(
    "flags,expected_tier",
    [
        ({"is_manager": True}, "manager"),
        ({"is_admin": True}, "admin"),
        ({"is_individual": True}, "individual"),
    ],
)
def test_current_user_exposes_role_tier(api, client_account, flags, expected_tier):
    role = _role(client_account, **flags)
    user = _user(client_account, role, f"{expected_tier}@a.test")
    _authenticate(api, user, client_account.id)

    resp = api.get(URL)
    assert resp.status_code == 200
    user_payload = _user_payload(resp)

    # RED on current code: the /me user dict has no role_tier yet.
    assert "role_tier" in user_payload, (
        "role_tier missing from GET /client/user/ user dict — the /me hand-built "
        "dict (UserCurrentView) does not include it yet"
    )
    assert user_payload["role_tier"] == expected_tier
