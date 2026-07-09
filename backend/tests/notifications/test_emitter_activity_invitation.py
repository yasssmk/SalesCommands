# backend/tests/notifications/test_emitter_activity_invitation.py
"""
Emitter test: inviting a user to an Activity notifies the invited user (E2).

Exercises the ActivityCreate/Update serializers directly (that is where the
invited_users M2M is set and, for updates, where the newly-invited delta is
computed). transaction=True so the serializers' transaction.on_commit
callback (where the notifications are emitted) actually fires.

Covers:
  - create: one notification per invited user, inviter skipped;
  - update: only the newly-added invitees are notified;
  - update that does not change the invitees emits nothing (non-negotiable).
"""

from types import SimpleNamespace

import pytest

from app_modules.activities.constants import ActivityType
from app_modules.activities.models import Activity
from app_modules.activities.serializers import (
    ActivityCreateSerializer,
    ActivityUpdateSerializer,
)
from app_modules.notifications.models import Notification, NotificationCategory


def _request(user):
    """Minimal request-like context object (serializers only read .user)."""
    return SimpleNamespace(user=user)


def _invitation_qs():
    return Notification.objects.filter(category=NotificationCategory.ACTIVITY_INVITATION)


def _make_activity(account, owner, client_id, invited=None):
    activity = Activity(
        title='Discovery call',
        activity_type=ActivityType.MEETING,
        account=account,
        owner=owner,
    )
    activity.save(user=owner, client_id=client_id)
    if invited:
        activity.invited_users.set(invited)
    return activity


@pytest.mark.django_db(transaction=True)
def test_create_notifies_each_invited_user(account, user_a, user_a2, client_account_a):
    """On create every invited user is notified; the inviter is skipped."""
    serializer = ActivityCreateSerializer(context={'request': _request(user_a)})
    activity = serializer.create({
        'title': 'Discovery call',
        'activity_type': ActivityType.MEETING,
        'account': account,
        # user_a is the actor -> must be skipped by the self-notify guard.
        '_invited_users': [user_a2, user_a],
        'client_id': client_account_a.id,
    })

    invitations = _invitation_qs()
    assert invitations.count() == 1
    notif = invitations.first()
    assert notif.recipient_id == user_a2.id
    assert notif.related_object_type == 'activity'
    assert str(notif.related_object_id) == str(activity.id)
    # Routing payload for the frontend deep-link (activity page).
    assert notif.payload == {'activity_id': str(activity.id)}
    # Rich title: actor + activity + account.
    actor_label = user_a.get_full_name() or user_a.email
    assert actor_label in notif.title
    assert activity.title in notif.title
    assert account.company_name in notif.title
    assert _invitation_qs().filter(recipient=user_a).count() == 0


@pytest.mark.django_db(transaction=True)
def test_update_notifies_only_new_invitees(account, user_a, user_a2, client_account_a):
    """On update only the newly-added invitees are notified."""
    from end_users.models import User

    activity = _make_activity(account, user_a, client_account_a.id, invited=[user_a2])
    user_a3 = User.objects.create(
        email='rep-a3@tenant-a.test',
        client_account=client_account_a,
        role=user_a.role,
        is_active=True,
    )

    serializer = ActivityUpdateSerializer(instance=activity, context={'request': _request(user_a)})
    serializer.update(activity, {'_invited_users': [user_a2, user_a3]})

    invitations = _invitation_qs()
    assert invitations.count() == 1
    notif = invitations.first()
    assert notif.recipient_id == user_a3.id  # only the new one
    assert notif.payload == {'activity_id': str(activity.id)}


@pytest.mark.django_db(transaction=True)
def test_update_without_invite_change_emits_nothing(account, user_a, user_a2, client_account_a):
    """An update that does not change the invited set emits nothing."""
    activity = _make_activity(account, user_a, client_account_a.id, invited=[user_a2])

    serializer = ActivityUpdateSerializer(instance=activity, context={'request': _request(user_a)})
    serializer.update(activity, {'_invited_users': [user_a2]})  # unchanged

    assert _invitation_qs().count() == 0
