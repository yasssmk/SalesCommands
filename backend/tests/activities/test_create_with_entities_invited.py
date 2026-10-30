# backend/tests/activities/test_create_with_entities_invited.py
"""
Sprint Next steps 5.8h (1) -- POST /module-activities/create-with-entities/
applies the invited teammates (invited_user_ids) exactly as the standard
create path (POST /module-activities/, ActivityCreateSerializer):

  * the invited users are set on the activity (invited_users M2M);
  * same validation: an id that is not a user of the tenant -> 400, the SAME
    error as the standard path, and nothing is created (atomic: no inline
    contact either);
  * same notification: one ACTIVITY_INVITATION per invited user, on commit,
    the inviter skipped (notify_invited_users).

Before 5.8h the service ignored invited_user_ids: the activity creation drawer
(5.8d) sends them, and an activity created with an inline contact silently
lost its teammates.
"""

import pytest
from rest_framework import status

from app_modules.activities.constants import ActivityStatus, ActivityType
from app_modules.activities.models import Activity
from app_modules.contacts.models import Contact
from app_modules.notifications.models import Notification, NotificationCategory


_URL = '/module-activities/create-with-entities/'
_STANDARD_URL = '/module-activities/'


@pytest.fixture
def user_a2(db, client_account_a, role_individual_a):
    """A second active user on tenant A (an invited teammate)."""
    from end_users.models import User
    return User.objects.create(
        email='teammate-a2@tenant-a.test',
        first_name='Tess',
        last_name='Mate',
        client_account=client_account_a,
        role=role_individual_a,
        is_active=True,
    )


def _activity(account, invited_ids, title='Security review'):
    return {
        'title': title,
        'activity_type': ActivityType.MEETING,
        'status': ActivityStatus.PLANNED,
        'account_id': str(account.id),
        'scheduled_date': '2026-11-03',
        'contact_ids': [],
        'invited_user_ids': [str(i) for i in invited_ids],
    }


def _with_inline_contact(account, invited_ids, title='Security review'):
    """The creation drawer's payload with a contact created on the fly."""
    return {
        'activity': _activity(account, invited_ids, title=title),
        'inline_contact': {'first_name': 'Isabelle', 'last_name': 'Roux'},
        'inline_cycle': None,
        'inline_step_stage': None,
    }


def _invitations():
    return Notification.objects.filter(category=NotificationCategory.ACTIVITY_INVITATION)


@pytest.mark.django_db(transaction=True)
class TestInvitedAppliedLikeTheStandardCreate:

    def test_the_invited_users_are_set(self, authed_api_a, account, user_a2):
        resp = authed_api_a.post(_URL, _with_inline_contact(account, [user_a2.id]), format='json')
        assert resp.status_code == status.HTTP_201_CREATED, resp.content
        activity = Activity.objects.get(id=resp.json()['data']['activity']['id'])
        assert list(activity.invited_users.values_list('id', flat=True)) == [user_a2.id]
        # The inline contact is still created and linked.
        assert activity.contacts.filter(first_name='Isabelle').exists()

    def test_each_invited_user_is_notified_the_inviter_skipped(
        self, authed_api_a, account, user_a, user_a2,
    ):
        resp = authed_api_a.post(
            _URL, _with_inline_contact(account, [user_a2.id, user_a.id]), format='json',
        )
        assert resp.status_code == status.HTTP_201_CREATED, resp.content
        activity_id = resp.json()['data']['activity']['id']
        notified = [(r, str(o)) for r, o in
                    _invitations().values_list('recipient_id', 'related_object_id')]
        assert notified == [(user_a2.id, str(activity_id))]

    def test_the_notification_is_the_standard_paths(self, authed_api_a, account, user_a, user_a2):
        """Same title / payload as POST /module-activities/ for the same activity."""
        standard = authed_api_a.post(
            _STANDARD_URL,
            {**_activity(account, [user_a2.id], title='Standard'),
             'contact_ids': [str(_contact(account, user_a).id)]},
            format='json',
        )
        assert standard.status_code == status.HTTP_201_CREATED, standard.content
        entities = authed_api_a.post(
            _URL, _with_inline_contact(account, [user_a2.id], title='Standard'), format='json',
        )
        assert entities.status_code == status.HTTP_201_CREATED, entities.content
        titles = list(_invitations().order_by('created_at').values_list('title', flat=True))
        assert len(titles) == 2
        assert titles[0] == titles[1]

    def test_an_unknown_user_is_the_standard_400_and_nothing_is_created(
        self, authed_api_a, account, user_a, user_b,
    ):
        """user_b belongs to ANOTHER tenant: same refusal as the standard path."""
        standard = authed_api_a.post(
            _STANDARD_URL,
            {**_activity(account, [user_b.id], title='Refused'),
             'contact_ids': [str(_contact(account, user_a).id)]},
            format='json',
        )
        assert standard.status_code == status.HTTP_400_BAD_REQUEST, standard.content
        contacts_before = Contact.objects.count()

        resp = authed_api_a.post(_URL, _with_inline_contact(account, [user_b.id], title='Refused'),
                                 format='json')
        assert resp.status_code == status.HTTP_400_BAD_REQUEST, resp.content
        # The SAME message (each view keeps its own error envelope).
        message = 'Invalid value: Some invited users not found'
        assert message in str(standard.json())
        assert message in str(resp.json())
        assert not Activity.objects.filter(title='Refused').exists()
        assert Contact.objects.count() == contacts_before      # atomic: no inline contact
        assert not _invitations().exists()


def _contact(account, user):
    c = Contact(account=account, first_name='Std', last_name='Contact', job_title='')
    c.save(user=user, client_id=account.client_id)
    return c

