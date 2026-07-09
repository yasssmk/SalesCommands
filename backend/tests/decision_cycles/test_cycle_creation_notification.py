# tests/decision_cycles/test_cycle_creation_notification.py
"""
Emitter test: creating a DecisionCycle notifies the account owner (E3).

Drives the real create endpoint (POST /decision_cycles/) so the view's
transaction.on_commit callback (where the notification is emitted) fires.
transaction=True is required for on_commit to run.

Covers:
  - a cycle created by a user notifies the (distinct) account owner;
  - no self-notification when the creator is also the account owner.
"""

import pytest

from app_modules.accounts.models import CompanyAccount
from app_modules.notifications.models import Notification, NotificationCategory


CYCLES_URL = '/decision_cycles/'


def _account_owned_by(owner, client_id, creator):
    acc = CompanyAccount(
        company_name=f'Acct owned by {owner.email}',
        has_buying_decision=True,
        account_owner=owner,
    )
    acc.save(user=creator, client_id=client_id)
    return acc


@pytest.mark.django_db(transaction=True)
def test_cycle_creation_notifies_account_owner(
    authed_api_a, user_a, client_account_a
):
    """A cycle created by user_a notifies the distinct account owner."""
    from end_users.models import User
    account_owner = User.objects.create(
        email='owner-a2@tenant-a.test',
        client_account=client_account_a,
        role=user_a.role,
        is_active=True,
    )
    account = _account_owned_by(account_owner, client_account_a.id, creator=user_a)

    resp = authed_api_a.post(
        CYCLES_URL,
        {'account_id': str(account.id), 'name': 'Enterprise deal'},
        format='json',
    )
    assert resp.status_code == 201
    cycle_id = resp.json()['data']['id']

    notifs = Notification.objects.filter(recipient=account_owner)
    assert notifs.count() == 1
    notif = notifs.first()
    assert notif.category == NotificationCategory.DECISION_CYCLE_CREATED
    assert notif.related_object_type == 'decision_cycle'
    assert str(notif.related_object_id) == str(cycle_id)
    # Routing payload for the frontend deep-link (DC workspace), same shape
    # as the manager-note notification (shared decision_cycle resolver).
    assert notif.payload == {
        'account_id': str(account.id),
        'cycle_id': str(cycle_id),
    }
    # Rich title: actor + account.
    actor_label = user_a.get_full_name() or user_a.email
    assert actor_label in notif.title
    assert account.company_name in notif.title
    # The creator (user_a) must not be notified.
    assert Notification.objects.filter(recipient=user_a).count() == 0


@pytest.mark.django_db(transaction=True)
def test_no_self_notification_when_creator_owns_account(
    authed_api_a, user_a, client_account_a
):
    """No notification when the creator is also the account owner."""
    account = _account_owned_by(user_a, client_account_a.id, creator=user_a)

    resp = authed_api_a.post(
        CYCLES_URL,
        {'account_id': str(account.id), 'name': 'Self-owned deal'},
        format='json',
    )
    assert resp.status_code == 201

    assert Notification.objects.count() == 0
