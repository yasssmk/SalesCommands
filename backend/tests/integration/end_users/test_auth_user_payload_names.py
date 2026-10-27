# backend/tests/integration/end_users/test_auth_user_payload_names.py
"""
Sprint Next steps 5.9b (2) -- the AUTH user (useAuth().user on the front) now
carries first_name / last_name.

The bug: the activity creation drawer showed the owner as
« admin@test.com · admin@test.com » for a user WITH a first and last name.
Its owner is useAuth().user, whose shape is the hand-built auth dict
{id, name, email, role, ...} (TD-234) -- no first_name / last_name /
full_name -- so the shared person name fell back to the email, then the
suffix repeated it. Context's owner (ActivityUserSerializer) carries them.

Fix at the central point: ONE auth user payload (core.auth_service
.auth_user_payload) for the three auth responses -- POST /client/login/,
GET /client/user/, the token refresh -- with first_name / last_name added
(additive: `name` and the other keys are unchanged).
"""

import inspect

import pytest

from tests.integration.end_users.test_current_user_role_tier import (  # noqa: F401
    _authenticate,
    _jwt_only_no_csrf,
    _role,
    _user_payload,
    api,
    client_account,
)
from end_users.models import User


@pytest.fixture
def named_user(client_account):
    role = _role(client_account, is_individual=True)
    user = User.objects.create(
        email="admin@test.com", first_name="Admin", last_name="Tenant A",
        client_account=client_account, role=role, is_active=True,
    )
    user.set_password("Pass-1234-word")
    user.save()
    return user


@pytest.mark.django_db
def test_current_user_carries_first_and_last_name(api, client_account, named_user):
    _authenticate(api, named_user, client_account.id)
    resp = api.get("/client/user/")
    assert resp.status_code == 200, resp.content
    user = _user_payload(resp)
    assert user["first_name"] == "Admin"
    assert user["last_name"] == "Tenant A"
    # Additive: the existing keys stay.
    assert user["name"] == "Admin Tenant A"
    assert user["email"] == "admin@test.com"


@pytest.mark.django_db
def test_login_carries_first_and_last_name(api, named_user):
    resp = api.post("/client/login/", {"email": "admin@test.com", "password": "Pass-1234-word"},
                    format="json")
    assert resp.status_code == 200, resp.content
    user = resp.data["user"]
    assert user["first_name"] == "Admin"
    assert user["last_name"] == "Tenant A"
    assert user["name"] == "Admin Tenant A"


def test_one_auth_user_payload_for_the_three_responses():
    """Login, current user and refresh build the user through ONE function."""
    from core import auth_service
    from end_users.views.auth import auth_views
    assert hasattr(auth_service, "auth_user_payload")
    assert "auth_user_payload(" in inspect.getsource(auth_views.UserLoginView)
    assert "auth_user_payload(" in inspect.getsource(auth_views.UserCurrentView)
    refresh_source = inspect.getsource(auth_service)
    assert refresh_source.count("auth_user_payload(") >= 2   # definition + the refresh


def test_the_payload_shape():
    from types import SimpleNamespace
    from core.auth_service import auth_user_payload
    user = SimpleNamespace(
        id="u-1", email="admin@test.com", first_name="Admin", last_name="Tenant A",
        role_name="Individual", role=None, client_account_id=None, client_account=None,
        get_full_name=lambda: "Admin Tenant A",
    )
    assert auth_user_payload(user) == {
        "id": "u-1", "name": "Admin Tenant A", "first_name": "Admin", "last_name": "Tenant A",
        "email": "admin@test.com", "role": "Individual", "role_tier": None, "avatar": None,
        "client_id": None, "client_name": None,
    }
