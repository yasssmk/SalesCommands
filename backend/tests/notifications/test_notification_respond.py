# backend/tests/notifications/test_notification_respond.py
"""
Endpoint tests for POST /notifications/{pk}/respond/ (Palier 3b).

Covers the respond contract:
  - the recipient responds to an actionable (PENDING) notification:
    PENDING -> ACCEPTED and PENDING -> DECLINED;
  - re-response is allowed: ACCEPTED -> DECLINED (the user changes their mind);
  - an INFORMATIVE notification (response_status null, E1/E4) is refused (400);
  - an invalid body value is refused (400);
  - responding to another user's notification is a scoped 404 (isolation
    identical to mark-read), and leaves it untouched.
"""

import pytest

from app_modules.notifications.models import (
    Notification, NotificationCategory, NotificationResponseStatus,
)
from app_modules.notifications.services import NotificationService


def _emit(recipient, client_id, actor, category, **overrides):
    return NotificationService.emit(
        client_id=client_id,
        recipient=recipient,
        actor=actor,
        category=category,
        title=overrides.pop('title', 'Test notification'),
        **overrides,
    )


def _invitation(recipient, client_id, actor):
    """An ACTIONABLE notification (E2) -> emitted as PENDING."""
    n = _emit(recipient, client_id, actor, NotificationCategory.ACTIVITY_INVITATION)
    assert n.response_status == NotificationResponseStatus.PENDING
    return n


def _informative(recipient, client_id, actor):
    """An INFORMATIVE notification (E1) -> response_status stays null."""
    n = _emit(recipient, client_id, actor, NotificationCategory.MANAGER_NOTE)
    assert n.response_status is None
    return n


def _url(notif):
    return f'/notifications/{notif.id}/respond/'


@pytest.mark.django_db
def test_recipient_accepts_pending(authed_api_a, user_a, user_a2, client_account_a):
    notif = _invitation(user_a, client_account_a.id, actor=user_a2)

    resp = authed_api_a.post(_url(notif), {'response_status': 'ACCEPTED'}, format='json')

    assert resp.status_code == 200
    assert resp.data['data']['response_status'] == 'ACCEPTED'
    notif.refresh_from_db()
    assert notif.response_status == NotificationResponseStatus.ACCEPTED


@pytest.mark.django_db
def test_recipient_declines_pending(authed_api_a, user_a, user_a2, client_account_a):
    notif = _invitation(user_a, client_account_a.id, actor=user_a2)

    resp = authed_api_a.post(_url(notif), {'response_status': 'DECLINED'}, format='json')

    assert resp.status_code == 200
    assert resp.data['data']['response_status'] == 'DECLINED'
    notif.refresh_from_db()
    assert notif.response_status == NotificationResponseStatus.DECLINED


@pytest.mark.django_db
def test_reresponse_accepted_to_declined(authed_api_a, user_a, user_a2, client_account_a):
    """A user may change their mind while the notification stays actionable."""
    notif = _invitation(user_a, client_account_a.id, actor=user_a2)

    r1 = authed_api_a.post(_url(notif), {'response_status': 'ACCEPTED'}, format='json')
    assert r1.status_code == 200
    r2 = authed_api_a.post(_url(notif), {'response_status': 'DECLINED'}, format='json')
    assert r2.status_code == 200
    assert r2.data['data']['response_status'] == 'DECLINED'
    notif.refresh_from_db()
    assert notif.response_status == NotificationResponseStatus.DECLINED


@pytest.mark.django_db
def test_informative_notification_is_refused(authed_api_a, user_a, user_a2, client_account_a):
    """An informative notification (null) cannot be responded to -> 400."""
    notif = _informative(user_a, client_account_a.id, actor=user_a2)

    resp = authed_api_a.post(_url(notif), {'response_status': 'ACCEPTED'}, format='json')

    assert resp.status_code == 400
    notif.refresh_from_db()
    assert notif.response_status is None  # untouched


@pytest.mark.django_db
def test_invalid_response_status_is_refused(authed_api_a, user_a, user_a2, client_account_a):
    notif = _invitation(user_a, client_account_a.id, actor=user_a2)

    resp = authed_api_a.post(_url(notif), {'response_status': 'MAYBE'}, format='json')

    assert resp.status_code == 400
    notif.refresh_from_db()
    assert notif.response_status == NotificationResponseStatus.PENDING  # untouched


@pytest.mark.django_db
def test_respond_on_foreign_notification_returns_404(
    authed_api_a, user_a2, client_account_a
):
    """Responding to another user's notification is a scoped 404, untouched."""
    other = _invitation(user_a2, client_account_a.id, actor=None)

    resp = authed_api_a.post(_url(other), {'response_status': 'ACCEPTED'}, format='json')

    assert resp.status_code == 404
    other.refresh_from_db()
    assert other.response_status == NotificationResponseStatus.PENDING  # untouched
