# backend/tests/campaigns/test_contacts_reached.py
"""
CONTACTS_REACHED — "we got through to this person", declared once.

THE RULE (PO truth table, final): a campaign contact is REACHED when the campaign
carries at least one COMPLETED activity on them whose outcome says a conversation
actually happened.

    REACHED      SUCCESSFUL, MEETING_SCHEDULED, NOT_INTERESTED,
                 FOLLOW_UP_NEEDED, UNSUBSCRIBE_OPTOUT
    NOT REACHED  NO_ANSWER, CALLBACK_REQUESTED, WRONG_CONTACT, WRONG_EMAIL,
                 INVALID_PHONE_NUMBER, OTHER

The split is about CONTACT, not about outcome. "Not interested" and "unsubscribe"
are reached — someone picked up and said no, which is a result. CALLBACK_REQUESTED
is NOT (an assistant or a voicemail promising a call back is not the person), and
neither is OTHER, which carries no information at all. All eleven outcomes are
enumerated below, one assertion each, so a future outcome added to the enum
without a decision here shows up as an uncovered value rather than a silent
default.

WHAT THIS REPLACES: "distinct contacts with at least one COMPLETED activity" —
no outcome filter whatever. Dialling a number and reaching voicemail counted as
reaching the contact, so the metric measured dialling effort, not conversations.

COUNTED PER CONTACT, ONCE: three completed successful calls on one person is one
contact reached.

DB: Postgres.
"""

from datetime import timedelta

import pytest
from django.utils import timezone

from app_modules.activities.constants import (
    ActivityOutcome, ActivityStatus, ActivityType,
)
from app_modules.activities.models import Activity
from app_modules.campaigns.constants import (
    CampaignAccountStatus, CampaignContactStatus, CampaignType, ObjectiveType,
)
from app_modules.campaigns.models import (
    Campaign, CampaignAccount, CampaignContact, CampaignObjective,
)
from app_modules.campaigns.services.campaign_analytics_service import (
    CampaignAnalyticsService,
)
from app_modules.campaigns.services.campaign_contact_reach import (
    REACHED_OUTCOMES,
    contacts_reached_by_campaign,
    contacts_reached_count,
)
from app_modules.campaigns.services.campaign_objective_progress import (
    compute_primary_objective_progress_batch,
)
from app_modules.contacts.models import Contact


pytestmark = pytest.mark.django_db


TODAY = timezone.now().date()


# The PO's table, transcribed. Every member of ActivityOutcome appears exactly
# once — asserted below — so this list IS the specification, not a sample of it.
REACHED = [
    ActivityOutcome.SUCCESSFUL,
    ActivityOutcome.MEETING_SCHEDULED,
    ActivityOutcome.NOT_INTERESTED,
    ActivityOutcome.FOLLOW_UP_NEEDED,
    ActivityOutcome.UNSUBSCRIBE_OPTOUT,
]
NOT_REACHED = [
    ActivityOutcome.NO_ANSWER,
    ActivityOutcome.CALLBACK_REQUESTED,
    ActivityOutcome.WRONG_CONTACT,
    ActivityOutcome.WRONG_EMAIL,
    ActivityOutcome.INVALID_PHONE_NUMBER,
    ActivityOutcome.OTHER,
]


# ---------------------------------------------------------------------------
# Factories (mirror tests/campaigns/test_activities_count.py + conftest.py)
# ---------------------------------------------------------------------------

def _campaign(account, user, name='Camp'):
    c = Campaign(name=name, campaign_type=CampaignType.OUTBOUND, owner=user,
                 executor=user, planned_start_date=TODAY,
                 planned_end_date=TODAY + timedelta(days=30))
    c.save(user=user, client_id=account.client_id)
    return c


def _campaign_account(campaign, account, user):
    ca = CampaignAccount(campaign=campaign, account=account,
                         status=CampaignAccountStatus.IN_PROGRESS)
    ca.save(user=user, client_id=account.client_id)
    return ca


_counter = {'n': 0}


def _campaign_contact(campaign_account, account, user):
    _counter['n'] += 1
    contact = Contact(account=account, first_name=f'C{_counter["n"]}',
                      last_name='Reach')
    contact.save(user=user, client_id=account.client_id)
    cc = CampaignContact(campaign_account=campaign_account, contact=contact,
                         status=CampaignContactStatus.IN_PROGRESS)
    cc.save(user=user, client_id=account.client_id)
    return cc


def _activity(campaign, campaign_account, campaign_contact, account, user, *,
              outcome, status=ActivityStatus.COMPLETED, title='a'):
    a = Activity(title=title, activity_type=ActivityType.CALL, status=status,
                 outcome=outcome, account=account, owner=user,
                 campaign=campaign, campaign_account=campaign_account,
                 campaign_contact=campaign_contact, scheduled_date=TODAY)
    a.save(user=user, client_id=account.client_id)
    return a


@pytest.fixture
def world(db, account, user_a):
    campaign = _campaign(account, user_a)
    return {
        'campaign': campaign,
        'campaign_account': _campaign_account(campaign, account, user_a),
        'account': account,
        'user': user_a,
        'client_id': account.client_id,
    }


def _reach(world, *, outcome, status=ActivityStatus.COMPLETED, contact=None):
    """One campaign contact carrying one activity. Returns the CampaignContact."""
    cc = contact or _campaign_contact(world['campaign_account'], world['account'],
                                      world['user'])
    _activity(world['campaign'], world['campaign_account'], cc,
              world['account'], world['user'], outcome=outcome, status=status)
    return cc


def _count(world):
    return contacts_reached_count(world['campaign'].id)


# ===========================================================================
# The outcome table — all eleven, one assertion each
# ===========================================================================

class TestTheOutcomeTable:

    def test_the_table_covers_every_declared_outcome_exactly_once(self):
        """Guards the guard: if a twelfth outcome is added to the enum, this
        fails and forces a REACHED / NOT-REACHED decision instead of letting it
        fall silently into 'not reached'."""
        listed = REACHED + NOT_REACHED
        assert len(listed) == len(set(listed))
        assert set(listed) == set(ActivityOutcome.values)

    def test_the_constant_is_exactly_the_reached_half(self):
        """REACHED_OUTCOMES is the declaration; this pins it to the PO's table
        so the two cannot drift with the constant quietly widened."""
        assert set(REACHED_OUTCOMES) == set(REACHED)
        assert set(REACHED_OUTCOMES).isdisjoint(NOT_REACHED)

    @pytest.mark.parametrize('outcome', REACHED)
    def test_a_reached_outcome_counts(self, world, outcome):
        _reach(world, outcome=outcome)
        assert _count(world) == 1, outcome

    @pytest.mark.parametrize('outcome', NOT_REACHED)
    def test_a_not_reached_outcome_does_not_count(self, world, outcome):
        _reach(world, outcome=outcome)
        assert _count(world) == 0, outcome

    def test_a_contact_with_no_outcome_at_all_does_not_count(self, world):
        _reach(world, outcome=None)
        assert _count(world) == 0


# ===========================================================================
# COMPLETED is required — an outcome on an unfinished row means nothing
# ===========================================================================

class TestCompletionIsRequired:

    @pytest.mark.parametrize(
        'status', [ActivityStatus.PLANNED, ActivityStatus.CANCELLED],
    )
    def test_a_reached_outcome_on_an_unfinished_activity_does_not_count(
        self, world, status,
    ):
        """``Activity.outcome`` is only meaningful once the activity is
        completed, so a stray outcome on a PLANNED row must not reach anybody —
        and a CANCELLED call never happened."""
        _reach(world, outcome=ActivityOutcome.SUCCESSFUL, status=status)
        assert _count(world) == 0

    def test_completing_the_same_contact_later_makes_them_reached(self, world):
        """The pair, on ONE contact: planned -> 0, completed -> 1. Proves the
        status filter is what moved the number, not the fixture."""
        cc = _reach(world, outcome=ActivityOutcome.SUCCESSFUL,
                    status=ActivityStatus.PLANNED)
        assert _count(world) == 0

        _activity(world['campaign'], world['campaign_account'], cc,
                  world['account'], world['user'],
                  outcome=ActivityOutcome.SUCCESSFUL,
                  status=ActivityStatus.COMPLETED, title='done')
        assert _count(world) == 1


# ===========================================================================
# Distinct CONTACTS, not activities
# ===========================================================================

class TestCountedOncePerContact:

    def test_three_activities_on_one_contact_is_one(self, world):
        cc = _campaign_contact(world['campaign_account'], world['account'],
                               world['user'])
        for index in range(3):
            _activity(world['campaign'], world['campaign_account'], cc,
                      world['account'], world['user'],
                      outcome=ActivityOutcome.SUCCESSFUL, title=f'call{index}')

        assert _count(world) == 1

    def test_a_mix_of_reached_and_not_reached_on_one_contact_is_one(self, world):
        """Two dials that went nowhere and one that connected: the contact was
        reached. The unreached attempts neither add to nor cancel the count."""
        cc = _campaign_contact(world['campaign_account'], world['account'],
                               world['user'])
        for outcome in (ActivityOutcome.NO_ANSWER,
                        ActivityOutcome.CALLBACK_REQUESTED,
                        ActivityOutcome.SUCCESSFUL):
            _activity(world['campaign'], world['campaign_account'], cc,
                      world['account'], world['user'], outcome=outcome,
                      title=str(outcome))

        assert _count(world) == 1

    def test_three_contacts_reached_are_three(self, world):
        """Anti-over-correction: the dedup is per contact, not per campaign."""
        for _ in range(3):
            _reach(world, outcome=ActivityOutcome.SUCCESSFUL)

        assert _count(world) == 3

    def test_an_activity_with_no_campaign_contact_reaches_nobody(self, world):
        """A campaign activity not attached to a campaign contact cannot say
        which person was reached. It must not become a phantom +1 — which is
        exactly what a ``.values(...).distinct().count()`` over a nullable link
        produces, because NULL forms a group of its own."""
        _activity(world['campaign'], world['campaign_account'], None,
                  world['account'], world['user'],
                  outcome=ActivityOutcome.SUCCESSFUL, title='orphan')

        assert _count(world) == 0

        # ... and it does not inflate a real count either.
        _reach(world, outcome=ActivityOutcome.SUCCESSFUL)
        assert _count(world) == 1


# ===========================================================================
# Isolation — another campaign's work is not this campaign's
# ===========================================================================

class TestCampaignIsolation:

    def test_another_campaigns_activity_does_not_count(self, world, account,
                                                       user_a):
        other = _campaign(account, user_a, name='Other')
        other_ca = _campaign_account(other, account, user_a)
        other_cc = _campaign_contact(other_ca, account, user_a)
        _activity(other, other_ca, other_cc, account, user_a,
                  outcome=ActivityOutcome.SUCCESSFUL, title='other')

        assert _count(world) == 0
        assert contacts_reached_count(other.id) == 1


# ===========================================================================
# ONE declaration — the detail path and the list batch must agree
# ===========================================================================

class TestTheTwoSurfacesAgree:
    """Before this, CONTACTS_REACHED was computed twice:
    ``CampaignAnalyticsService._count_contacts_reached`` used
    ``.values('contacts').distinct().count()`` and the list batch used
    ``Count('contacts', distinct=True)``. Those two do NOT agree — a plain
    ``distinct()`` counts the NULL group as a value while ``Count(distinct=True)``
    drops it — so a campaign activity without a contact made the detail page read
    one higher than the card. Both now call the same function."""

    def _objective(self, world, target=10):
        o = CampaignObjective(campaign=world['campaign'],
                              name='reached',
                              objective_type=ObjectiveType.CONTACTS_REACHED,
                              target_value=target, is_primary=True)
        o.save(user=world['user'], client_id=world['client_id'])
        return o

    def test_detail_list_and_helper_return_the_same_number(self, world):
        self._objective(world)
        for _ in range(2):
            _reach(world, outcome=ActivityOutcome.SUCCESSFUL)
        _reach(world, outcome=ActivityOutcome.NO_ANSWER)          # not reached
        _activity(world['campaign'], world['campaign_account'], None,
                  world['account'], world['user'],
                  outcome=ActivityOutcome.SUCCESSFUL, title='orphan')

        service = CampaignAnalyticsService(world['client_id'])
        detail = service._count_contacts_reached(world['campaign'])
        batch = compute_primary_objective_progress_batch(
            [world['campaign']], world['client_id'],
        )[world['campaign'].id]['current_value']

        assert detail == batch == _count(world) == 2

    def test_the_grouped_form_matches_the_per_campaign_form(self, world, account,
                                                            user_a):
        """The batch groups many campaigns in one query; the helper answers for
        one. They must not diverge, whatever the shape of the data."""
        other = _campaign(account, user_a, name='Other')
        other_ca = _campaign_account(other, account, user_a)
        for _ in range(2):
            cc = _campaign_contact(other_ca, account, user_a)
            _activity(other, other_ca, cc, account, user_a,
                      outcome=ActivityOutcome.MEETING_SCHEDULED, title='m')
        _reach(world, outcome=ActivityOutcome.NOT_INTERESTED)

        grouped = contacts_reached_by_campaign(
            [world['campaign'].id, other.id],
        )

        assert grouped[world['campaign'].id] == contacts_reached_count(
            world['campaign'].id) == 1
        assert grouped[other.id] == contacts_reached_count(other.id) == 2

    def test_a_campaign_with_no_reach_reports_zero_not_a_missing_key(
        self, world, account, user_a,
    ):
        empty = _campaign(account, user_a, name='Empty')

        grouped = contacts_reached_by_campaign([empty.id])

        assert grouped[empty.id] == 0


# ===========================================================================
# Query bound
# ===========================================================================

class TestQueryBound:

    def test_the_count_is_one_query_whatever_the_volume(
        self, world, django_assert_num_queries,
    ):
        for _ in range(4):
            cc = _campaign_contact(world['campaign_account'], world['account'],
                                   world['user'])
            for index in range(3):
                _activity(world['campaign'], world['campaign_account'], cc,
                          world['account'], world['user'],
                          outcome=ActivityOutcome.SUCCESSFUL, title=f'a{index}')

        with django_assert_num_queries(1):
            assert contacts_reached_count(world['campaign'].id) == 4

    def test_the_batch_is_one_query_for_many_campaigns(
        self, world, account, user_a, django_assert_num_queries,
    ):
        ids = [world['campaign'].id]
        for index in range(3):
            other = _campaign(account, user_a, name=f'C{index}')
            other_ca = _campaign_account(other, account, user_a)
            cc = _campaign_contact(other_ca, account, user_a)
            _activity(other, other_ca, cc, account, user_a,
                      outcome=ActivityOutcome.SUCCESSFUL, title='a')
            ids.append(other.id)

        with django_assert_num_queries(1):
            grouped = contacts_reached_by_campaign(ids)

        assert sum(grouped.values()) == 3
