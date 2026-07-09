# backend/tests/notifications/test_notification_service.py
"""
Tests for NotificationService.emit().

Covers:
  - emit() creates exactly one row, correctly scoped to client_id and
    recipient, with created_by set from the actor;
  - the centralised self-notification guard: None when recipient is
    missing, None when recipient == actor;
  - recipient/actor accepted as either a User instance or a bare id.
"""

import pytest

from app_modules.notifications.models import Notification, NotificationCategory
from app_modules.notifications.services import NotificationService


@pytest.mark.django_db
def test_emit_creates_scoped_row(user_a, user_a2, client_account_a):
    """emit() persists one row scoped to the given client_id + recipient."""
    notif = NotificationService.emit(
        client_id=client_account_a.id,
        recipient=user_a,
        actor=user_a2,
        category=NotificationCategory.MANAGER_NOTE,
        title='New note on your cycle',
        related_object_type='decision_cycle',
        related_object_id=None,
    )

    assert notif is not None
    assert Notification.objects.count() == 1
    assert notif.recipient_id == user_a.id
    assert str(notif.client_id) == str(client_account_a.id)
    assert notif.category == NotificationCategory.MANAGER_NOTE
    assert notif.read_at is None
    assert notif.created_by_id == user_a2.id  # audit set from actor


@pytest.mark.django_db
def test_emit_accepts_ids(user_a, user_a2, client_account_a):
    """Recipient and actor may be passed as bare ids."""
    notif = NotificationService.emit(
        client_id=client_account_a.id,
        recipient=user_a.id,
        actor=user_a2.id,
        category=NotificationCategory.ACTIVITY_INVITATION,
        title='You were invited',
    )

    assert notif is not None
    assert notif.recipient_id == user_a.id


@pytest.mark.django_db
def test_emit_returns_none_when_recipient_missing(client_account_a, user_a):
    """No recipient => no notification."""
    result = NotificationService.emit(
        client_id=client_account_a.id,
        recipient=None,
        actor=user_a,
        category=NotificationCategory.MANAGER_NOTE,
        title='Orphan note',
    )

    assert result is None
    assert Notification.objects.count() == 0


@pytest.mark.django_db
def test_emit_returns_none_on_self_notify(client_account_a, user_a):
    """recipient == actor => skipped (no self-notification)."""
    result = NotificationService.emit(
        client_id=client_account_a.id,
        recipient=user_a,
        actor=user_a,
        category=NotificationCategory.DECISION_CYCLE_CREATED,
        title='Your own cycle',
    )

    assert result is None
    assert Notification.objects.count() == 0
