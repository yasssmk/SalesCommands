# backend/tests/activities/test_notes_autosave_csrf.py
"""
Sprint « Source / Notes » — notes panel, N2: the front flushes the notes
autosave with `fetch(..., { keepalive: true, credentials: 'include' })` on
unmount / beforeunload — the HttpOnly `access_token` cookie, NO CSRF token.
Proof that CSRF does not block that path, with the PRODUCTION auth stack
(the autouse _jwt_only_no_csrf fixture is undone here): the Django CSRF
middleware ON, DRF authenticating with core.jwt_helpers.CustomJWTAuthentication
(cookie), and a client that ENFORCES CSRF checks.

Why it passes: DRF views are csrf_exempt (the Django middleware skips them)
and DRF only enforces CSRF inside SessionAuthentication — which the project
does not use: ActivityViewSet authenticates with CustomJWTAuthentication
(authentication_classes, activities/views/views.py), the DRF default too
(salescommands/settings.py DEFAULT_AUTHENTICATION_CLASSES).
Control: the same client authenticated by SESSION is refused (403) and the
exception DRF raised is « CSRF Failed » — the client does enforce CSRF.
"""

from unittest import mock

import pytest
from django.conf import settings as django_settings
from rest_framework.test import APIClient

import salescommands.settings as project_settings
from app_modules.activities.constants import ActivityStatus, ActivityType
from core.jwt_helpers import JWTHelpers


pytestmark = pytest.mark.django_db
URL = '/module-activities/{}/notes/'


@pytest.fixture
def production_auth_stack(settings):
    """Undo _jwt_only_no_csrf: the project's own middleware + DRF auth."""
    settings.MIDDLEWARE = list(project_settings.MIDDLEWARE)
    settings.REST_FRAMEWORK = dict(project_settings.REST_FRAMEWORK)
    assert 'django.middleware.csrf.CsrfViewMiddleware' in settings.MIDDLEWARE
    assert settings.REST_FRAMEWORK['DEFAULT_AUTHENTICATION_CLASSES'] == (
        'core.jwt_helpers.CustomJWTAuthentication',
    )
    return settings


def _activity(account, owner):
    from app_modules.activities.models import Activity
    a = Activity(title='Discovery', activity_type=ActivityType.MEETING, status=ActivityStatus.PLANNED,
                 account=account, owner=owner, scheduled_date='2026-11-11')
    a.save(user=owner, client_id=account.client_id)
    return a


def test_the_keepalive_path_cookie_jwt_without_csrf_token_passes(production_auth_stack, account, user_a):
    activity = _activity(account, user_a)
    client = APIClient(enforce_csrf_checks=True)
    tokens = JWTHelpers.generate_token_response(
        user_a, 'end_users', django_settings.SIMPLE_JWT['REFRESH_TOKEN_LIFETIME'],
    )
    client.cookies['access_token'] = tokens['access']

    r = client.post(URL.format(activity.id), {'outcome_notes': 'Flushed on unload'}, format='json')

    assert r.status_code == 200, r.content
    activity.refresh_from_db()
    assert activity.outcome_notes == 'Flushed on unload'


def test_control_a_session_authenticated_post_is_refused_by_csrf(
    production_auth_stack, monkeypatch, account, user_a,
):
    # The same enforcing client, authenticated by SESSION through DRF's
    # SessionAuthentication: DRF enforces CSRF there → refused. Proves the
    # client checks CSRF, so the pass above is meaningful.
    from rest_framework.authentication import SessionAuthentication
    from app_modules.activities.views.views import ActivityViewSet
    monkeypatch.setattr(ActivityViewSet, 'authentication_classes', [SessionAuthentication])
    from core.apps_shared_methods import BaseAPIView
    activity = _activity(account, user_a)
    client = APIClient(enforce_csrf_checks=True)
    client.force_login(user_a)
    seen = []

    original = BaseAPIView.handle_exception

    def spy(view, exc):
        # BaseAPIView.handle_exception rewrites a 403 into the generic
        # PERMISSION_DENIED message: read the exception DRF raised.
        seen.append(str(exc))
        return original(view, exc)

    with mock.patch.object(BaseAPIView, 'handle_exception', spy):
        refused = client.post(URL.format(activity.id), {'outcome_notes': 'x'}, format='json')
    assert refused.status_code == 403, refused.content
    assert any(m.startswith('CSRF Failed') for m in seen), seen
