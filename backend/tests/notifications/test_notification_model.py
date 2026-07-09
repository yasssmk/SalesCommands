# backend/tests/notifications/test_notification_model.py
"""
Model-level tests for the Notification model.

Covers:
  - default field values (read_at unread, empty body/payload) and the
    ModuleBaseModel save(user=, client_id=) audit/scoping contract;
  - tenant isolation: a notification created for tenant A is never
    surfaced when querying under tenant B's client_id.
"""

import pytest

from app_modules.notifications.models import Notification, NotificationCategory


@pytest.mark.django_db
def test_notification_defaults(user_a, client_account_a):
    """A freshly created notification is unread with empty body/payload."""
    notif = Notification(
        recipient=user_a,
        category=NotificationCategory.MANAGER_NOTE,
        title='New note on Acme cycle',
    )
    notif.save(user=user_a, client_id=client_account_a.id)

    notif.refresh_from_db()
    assert notif.read_at is None            # unread by default
    assert notif.body == ''
    assert notif.payload == {}
    assert notif.related_object_type == ''
    assert notif.related_object_id is None
    assert str(notif.client_id) == str(client_account_a.id)
    assert notif.created_by_id == user_a.id


@pytest.mark.django_db
def test_tenant_scoping_isolates_notifications(user_a, client_account_a, tenant_b_id):
    """A tenant-A notification is invisible to a tenant-B-scoped query."""
    notif = Notification(
        recipient=user_a,
        category=NotificationCategory.DECISION_CYCLE_CREATED,
        title='New decision cycle',
    )
    notif.save(user=user_a, client_id=client_account_a.id)

    # Visible under its own tenant.
    assert Notification.objects.filter(client_id=client_account_a.id).count() == 1
    # Invisible under a different tenant.
    assert Notification.objects.filter(client_id=tenant_b_id).count() == 0
