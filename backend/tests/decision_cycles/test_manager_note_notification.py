# tests/decision_cycles/test_manager_note_notification.py
"""
Emitter test: adding a ManagerNote on a DecisionCycle notifies the cycle
owner (E1). Uses transaction=True so the create view's transaction.on_commit
callback (where the notification is emitted) actually fires.

Covers:
  - a note added by a manager notifies the (distinct) cycle owner;
  - no self-notification when the note author owns the cycle.
"""

import pytest

from app_modules.decision_cycles.models import DecisionCycle
from app_modules.notifications.models import Notification, NotificationCategory


def _notes_url(cycle_id):
    return f'/decision_cycles/{cycle_id}/notes/'


# =============================================================================
# FIXTURES — manager role + user on tenant A (mirror test_manager_note_api.py)
# =============================================================================

@pytest.fixture
def role_manager_a(db, client_account_a):
    from end_users.models import UserRole
    return UserRole.objects.create(
        client_account=client_account_a,
        name='Manager',
        is_admin=False,
        is_manager=True,
        is_individual=False,
        read=True,
        write=True,
        modify=True,
        can_delete=True,
    )


@pytest.fixture
def manager_user_a(db, client_account_a, role_manager_a):
    from end_users.models import User
    return User.objects.create(
        email='manager@tenant-a.test',
        client_account=client_account_a,
        role=role_manager_a,
        is_active=True,
    )


@pytest.fixture
def authed_api_manager(api, authenticate, manager_user_a, client_account_a):
    authenticate(api, manager_user_a, client_account_a.id)
    return api


# =============================================================================
# TESTS
# =============================================================================

@pytest.mark.django_db(transaction=True)
def test_note_notifies_cycle_owner(authed_api_manager, cycle, user_a, manager_user_a):
    """A note by the manager notifies the distinct cycle owner (user_a)."""
    resp = authed_api_manager.post(
        _notes_url(cycle.id),
        {'content': 'Push on technical validation.'},
        format='json',
    )
    assert resp.status_code == 201

    notifs = Notification.objects.filter(recipient=user_a)
    assert notifs.count() == 1
    notif = notifs.first()
    assert notif.category == NotificationCategory.MANAGER_NOTE
    assert str(notif.client_id) == str(cycle.client_id)
    assert str(notif.related_object_id) == str(cycle.id)
    assert notif.related_object_type == 'decision_cycle'
    # The manager (author) must not be notified about their own note.
    assert Notification.objects.filter(recipient=manager_user_a).count() == 0


@pytest.mark.django_db(transaction=True)
def test_no_self_notification_when_author_owns_cycle(
    authed_api_manager, manager_user_a, account
):
    """No notification when the note author also owns the cycle."""
    own_cycle = DecisionCycle(
        account=account,
        owner=manager_user_a,
        name='Manager owned cycle',
        is_active=True,
    )
    own_cycle.save(user=manager_user_a, client_id=account.client_id)

    resp = authed_api_manager.post(
        _notes_url(own_cycle.id),
        {'content': 'Self note.'},
        format='json',
    )
    assert resp.status_code == 201

    assert Notification.objects.count() == 0
