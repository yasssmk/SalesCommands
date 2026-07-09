# backend/tests/notifications/test_notification_endpoints.py
"""
Endpoint tests for the Notifications module.

Covers:
  - list returns ONLY the caller's notifications (cross-user AND
    cross-tenant isolation);
  - unread-count is exact;
  - mark-read flips read_at null -> now and is idempotent (second call
    is a no-op 200, never a 500);
  - mark-read on someone else's notification returns a scoped 404.
"""

import pytest
from django.utils import timezone

from app_modules.notifications.models import Notification, NotificationCategory


LIST_URL = '/notifications/'
UNREAD_COUNT_URL = '/notifications/unread-count/'


def _make_notification(recipient, client_id, actor, **overrides):
    """Persist a notification for `recipient` on `client_id`."""
    from app_modules.notifications.services import NotificationService
    return NotificationService.emit(
        client_id=client_id,
        recipient=recipient,
        actor=actor,
        category=overrides.pop('category', NotificationCategory.MANAGER_NOTE),
        title=overrides.pop('title', 'Test notification'),
        **overrides,
    )


@pytest.mark.django_db
def test_list_returns_only_callers_notifications_same_tenant(
    authed_api_a, user_a, user_a2, client_account_a
):
    """A user does not see another user's notifications within the tenant."""
    mine = _make_notification(user_a, client_account_a.id, actor=user_a2)
    _make_notification(user_a2, client_account_a.id, actor=user_a)  # not mine

    resp = authed_api_a.get(LIST_URL)

    assert resp.status_code == 200
    results = resp.data['data']['results']
    assert resp.data['data']['count'] == 1
    assert len(results) == 1
    assert str(results[0]['id']) == str(mine.id)


@pytest.mark.django_db
def test_list_isolates_across_tenants(
    authed_api_a, user_a, client_account_a, user_b, client_account_b
):
    """A tenant-A caller never sees a tenant-B notification."""
    _make_notification(user_a, client_account_a.id, actor=None)
    _make_notification(user_b, client_account_b.id, actor=None)  # other tenant

    resp = authed_api_a.get(LIST_URL)

    assert resp.status_code == 200
    assert resp.data['data']['count'] == 1


@pytest.mark.django_db
def test_unread_count_is_exact(authed_api_a, user_a, user_a2, client_account_a):
    """unread-count counts only the caller's unread notifications."""
    n1 = _make_notification(user_a, client_account_a.id, actor=user_a2)
    _make_notification(user_a, client_account_a.id, actor=user_a2)
    _make_notification(user_a2, client_account_a.id, actor=user_a)  # other recipient

    # Read one of user_a's two.
    n1.read_at = timezone.now()
    n1.save(user=user_a)

    resp = authed_api_a.get(UNREAD_COUNT_URL)

    assert resp.status_code == 200
    assert resp.data['data']['count'] == 1


@pytest.mark.django_db
def test_mark_read_flips_and_is_idempotent(
    authed_api_a, user_a, user_a2, client_account_a
):
    """mark-read flips null->now once, and a second call is a no-op 200."""
    notif = _make_notification(user_a, client_account_a.id, actor=user_a2)
    assert notif.read_at is None

    url = f'/notifications/{notif.id}/read/'

    resp1 = authed_api_a.post(url)
    assert resp1.status_code == 200
    notif.refresh_from_db()
    first_read_at = notif.read_at
    assert first_read_at is not None

    resp2 = authed_api_a.post(url)
    assert resp2.status_code == 200  # idempotent, not a 500
    notif.refresh_from_db()
    assert notif.read_at == first_read_at  # unchanged on second call


@pytest.mark.django_db
def test_mark_read_on_foreign_notification_returns_404(
    authed_api_a, user_a2, client_account_a
):
    """Marking another user's notification read is a scoped 404."""
    other = _make_notification(user_a2, client_account_a.id, actor=None)

    resp = authed_api_a.post(f'/notifications/{other.id}/read/')

    assert resp.status_code == 404
    other.refresh_from_db()
    assert other.read_at is None  # untouched
