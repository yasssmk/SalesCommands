# backend/tests/campaigns/test_campaign_new_logos.py
"""
Campaign NEW_LOGOS — an account that BECAME a client through a deal this campaign
carried.

THE RULE (PO, final), two conditions and both are required:

  TRANSITION   the account really went prospect -> client. ``became_client_at``
               is the marker, stamped once by the close hook on the FIRST won
               cycle of a PROSPECT account (decision_cycles/views/views.py:779-788)
               and never set for an account imported as CLIENT.
  ATTRIBUTION  the won cycle that TRIGGERED that transition is attributed to the
               campaign — born-from OR touched-by, the same
               ``campaign_dc_attribution.attributed_cycles`` the money uses.

Counted per ACCOUNT, once per campaign. A logo may count for SEVERAL campaigns —
every campaign that carried the winning deal — so campaign logos are not additive
across campaigns, exactly like the money.

WHAT THIS REPLACES: ``CampaignAccount(status=COMPLETED, account__type='CLIENT')``,
an MVP proxy whose own docstring said so. It counted every account the campaign
finished working that is CURRENTLY typed client — so an account imported as a
client, enrolled and completed, was a "new logo", and no decision cycle was
consulted at all.

WHICH CYCLE "TRIGGERED" THE TRANSITION — a derivation, not a stored link.
``became_client_at`` is a bare timestamp; nothing records WHICH cycle set it. It
is stamped on the first win, so the triggering cycle is derived as the account's
won cycle with the earliest ``outcome_date``. That field is a DateField, so two
cycles won on the SAME DAY both qualify — pinned below rather than left to be
discovered.

DB: Postgres.
"""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from app_modules.accounts.models import AccountType, CompanyAccount
from app_modules.activities.constants import (
    ActivityOutcome, ActivityStatus, ActivityType,
)
from app_modules.activities.models import Activity
from app_modules.campaigns.constants import CampaignType, ObjectiveType
from app_modules.campaigns.models import Campaign, CampaignObjective
from app_modules.campaigns.services.campaign_analytics_service import (
    CampaignAnalyticsService,
)
from app_modules.campaigns.services.campaign_dc_attribution import (
    campaign_new_logos,
)
from app_modules.campaigns.services.campaign_objective_progress import (
    compute_primary_objective_progress_batch,
)
from app_modules.decision_cycles.constants import CycleOutcome
from app_modules.decision_cycles.models import DecisionCycle
from tests.deal_value_helpers import give_deal_value


pytestmark = pytest.mark.django_db


TODAY = timezone.now().date()


# ---------------------------------------------------------------------------
# Factories (mirror tests/campaigns/test_campaign_value_touched_by.py)
# ---------------------------------------------------------------------------

def _campaign(owner, ca, name='A'):
    c = Campaign(name=name, campaign_type=CampaignType.OUTBOUND, owner=owner,
                 executor=owner, planned_start_date=TODAY,
                 planned_end_date=TODAY + timedelta(days=30))
    c.save(user=owner, client_id=ca.id)
    return c


def _objective(campaign, owner, ca, target=10):
    o = CampaignObjective(campaign=campaign, name='logos',
                          objective_type=ObjectiveType.NEW_LOGOS,
                          target_value=target, is_primary=True)
    o.save(user=owner, client_id=ca.id)
    return o


_counter = {'n': 0}


def _prospect(owner, ca, name=None):
    """A PROSPECT account — the only kind that can become a new logo."""
    _counter['n'] += 1
    acc = CompanyAccount(company_name=name or f'Prospect{_counter["n"]}',
                         has_buying_decision=True, account_owner=owner,
                         type=AccountType.PROSPECT)
    acc.save(user=owner, client_id=ca.id)
    return acc


def _converted(owner, ca, name=None, when=None):
    """A prospect that HAS transitioned: typed CLIENT with the stamp set.

    ``became_client_at`` is ``editable=False`` (system-managed), so it is
    assigned in code — the same way tests/bi/test_metrics_canonical.py seeds it
    for the personal metric.
    """
    acc = _prospect(owner, ca, name=name)
    acc.type = AccountType.CLIENT
    acc.became_client_at = when or timezone.now()
    acc.save(user=owner)
    return acc


def _imported_client(owner, ca, name=None):
    """An account that was ALREADY a client — never a new logo, whoever wins on
    it. The stamp stays NULL, which is the definition."""
    _counter['n'] += 1
    acc = CompanyAccount(company_name=name or f'Client{_counter["n"]}',
                         has_buying_decision=True, account_owner=owner,
                         type=AccountType.CLIENT)
    acc.save(user=owner, client_id=ca.id)
    return acc


def _cycle(owner, account, ca, *, source_campaign=None, amount=None,
           outcome=None, outcome_date=None, name='dc'):
    dc = DecisionCycle(account=account, owner=owner, name=name,
                       source_campaign=source_campaign, outcome=outcome,
                       outcome_date=outcome_date)
    dc.save(user=owner, client_id=ca.id)
    give_deal_value(dc, amount, user=owner)
    return dc


def _won(owner, account, ca, *, source_campaign=None, on=None, name='won'):
    return _cycle(owner, account, ca, source_campaign=source_campaign,
                  amount=Decimal('40000'), outcome=CycleOutcome.WON,
                  outcome_date=on or TODAY, name=name)


def _activity(owner, account, ca, *, campaign, cycle,
              status=ActivityStatus.COMPLETED,
              outcome=ActivityOutcome.SUCCESSFUL):
    a = Activity(title='a', activity_type=ActivityType.CALL, status=status,
                 outcome=outcome, account=account, owner=owner,
                 campaign=campaign, decision_cycle=cycle, scheduled_date=TODAY)
    a.save(user=owner, client_id=ca.id)
    return a


def _count(ca, campaign):
    return campaign_new_logos(campaign.id, ca.id)


def _all_three(ca, campaign, objective):
    """list == detail == dashboard, or fail naming which drifted. Same guard as
    tests/campaigns/test_campaign_value_touched_by.py uses for the money."""
    service = CampaignAnalyticsService(client_id=ca.id)
    detail = service._calculate_objective_value(campaign, objective)
    dashboard = service.calculate_objective_values(campaign, [objective])[objective.id]
    listed = compute_primary_objective_progress_batch(
        [campaign], ca.id,
    )[campaign.id]['current_value']
    assert listed == detail, f'list {listed} != detail {detail}'
    assert dashboard == detail, f'dashboard {dashboard} != detail {detail}'
    return detail


# ===========================================================================
# ATTRIBUTION — both branches earn the logo
# ===========================================================================

class TestAttribution:

    def test_born_from_earns_the_logo_with_no_activity_at_all(
        self, user_a, client_account_a,
    ):
        """A deal the campaign OPENED, won, converting the account — the campaign
        gets the logo immediately. Nothing was logged on the deal, and nothing
        needs to be: born-from is unconditional."""
        camp_a = _campaign(user_a, client_account_a, name='A')
        obj_a = _objective(camp_a, user_a, client_account_a)
        acc = _converted(user_a, client_account_a)
        _won(user_a, acc, client_account_a, source_campaign=camp_a)

        assert _all_three(client_account_a, camp_a, obj_a) == 1

    def test_touched_by_earns_the_logo_on_a_deal_it_did_not_open(
        self, user_a, client_account_a,
    ):
        """Campaign B did not open the deal but carried it to the win with a
        completed successful activity. B gets the logo too."""
        camp_b = _campaign(user_a, client_account_a, name='B')
        obj_b = _objective(camp_b, user_a, client_account_a)
        acc = _converted(user_a, client_account_a)
        won = _won(user_a, acc, client_account_a, source_campaign=None)
        _activity(user_a, acc, client_account_a, campaign=camp_b, cycle=won)

        assert _all_three(client_account_a, camp_b, obj_b) == 1

    def test_a_non_successful_activity_earns_nothing(
        self, user_a, client_account_a,
    ):
        """Campaign C touched the winning deal but the call went nowhere. The
        touched-by branch keeps its gate; C gets no logo."""
        camp_c = _campaign(user_a, client_account_a, name='C')
        obj_c = _objective(camp_c, user_a, client_account_a)
        acc = _converted(user_a, client_account_a)
        won = _won(user_a, acc, client_account_a, source_campaign=None)
        _activity(user_a, acc, client_account_a, campaign=camp_c, cycle=won,
                  outcome=ActivityOutcome.NO_ANSWER)

        assert _all_three(client_account_a, camp_c, obj_c) == 0

    def test_an_uncompleted_activity_earns_nothing(self, user_a,
                                                   client_account_a):
        camp_c = _campaign(user_a, client_account_a, name='C')
        obj_c = _objective(camp_c, user_a, client_account_a)
        acc = _converted(user_a, client_account_a)
        won = _won(user_a, acc, client_account_a, source_campaign=None)
        _activity(user_a, acc, client_account_a, campaign=camp_c, cycle=won,
                  status=ActivityStatus.PLANNED)

        assert _all_three(client_account_a, camp_c, obj_c) == 0

    def test_one_logo_counts_for_every_campaign_that_carried_the_win(
        self, user_a, client_account_a,
    ):
        """Non-additive across campaigns, deliberately: A opened the deal and B
        closed it, so BOTH earned the logo. Summing campaigns would invent a
        second client."""
        camp_a = _campaign(user_a, client_account_a, name='A')
        camp_b = _campaign(user_a, client_account_a, name='B')
        obj_a = _objective(camp_a, user_a, client_account_a)
        obj_b = _objective(camp_b, user_a, client_account_a)
        acc = _converted(user_a, client_account_a)
        won = _won(user_a, acc, client_account_a, source_campaign=camp_a)
        _activity(user_a, acc, client_account_a, campaign=camp_b, cycle=won)

        assert _all_three(client_account_a, camp_a, obj_a) == 1
        assert _all_three(client_account_a, camp_b, obj_b) == 1
        # ... and the tenant still gained exactly ONE client.
        assert CompanyAccount.objects.filter(
            client_id=client_account_a.id, became_client_at__isnull=False,
        ).count() == 1

    def test_an_unrelated_campaign_earns_nothing(self, user_a,
                                                 client_account_a):
        camp_a = _campaign(user_a, client_account_a, name='A')
        camp_z = _campaign(user_a, client_account_a, name='Z')
        obj_z = _objective(camp_z, user_a, client_account_a)
        acc = _converted(user_a, client_account_a)
        _won(user_a, acc, client_account_a, source_campaign=camp_a)

        assert _all_three(client_account_a, camp_z, obj_z) == 0


# ===========================================================================
# THE TRANSITION IS REQUIRED — winning is not becoming a client
# ===========================================================================

class TestTheTransitionIsRequired:

    def test_an_account_already_a_client_is_not_a_logo(self, user_a,
                                                       client_account_a):
        """The proxy's central error: an account imported as CLIENT has a NULL
        stamp and never transitioned, so winning a deal on it is revenue, not a
        new logo."""
        camp_a = _campaign(user_a, client_account_a, name='A')
        obj_a = _objective(camp_a, user_a, client_account_a)
        acc = _imported_client(user_a, client_account_a)
        _won(user_a, acc, client_account_a, source_campaign=camp_a)

        assert _all_three(client_account_a, camp_a, obj_a) == 0

    def test_an_open_deal_earns_no_logo_yet(self, user_a, client_account_a):
        """A campaign with attributed pipeline but nothing won: the account is
        still a prospect."""
        camp_a = _campaign(user_a, client_account_a, name='A')
        obj_a = _objective(camp_a, user_a, client_account_a)
        acc = _prospect(user_a, client_account_a)
        _cycle(user_a, acc, client_account_a, source_campaign=camp_a,
               amount=Decimal('60000'))

        assert _all_three(client_account_a, camp_a, obj_a) == 0

    def test_a_won_deal_on_a_still_unconverted_account_earns_no_logo(
        self, user_a, client_account_a,
    ):
        """Guards the pair: the win exists and is attributed, but the account
        carries no stamp, so no transition happened. Proves the logo follows the
        TRANSITION and not merely the win."""
        camp_a = _campaign(user_a, client_account_a, name='A')
        obj_a = _objective(camp_a, user_a, client_account_a)
        acc = _prospect(user_a, client_account_a)
        _won(user_a, acc, client_account_a, source_campaign=camp_a)

        assert _all_three(client_account_a, camp_a, obj_a) == 0


# ===========================================================================
# THE TRIGGERING CYCLE — the FIRST win, not any win
# ===========================================================================

class TestOnlyTheTriggeringWinCounts:

    def test_a_later_win_by_another_campaign_earns_no_logo(
        self, user_a, client_account_a,
    ):
        """A became the client's first supplier; B sold them something else a
        year later. The account was already a client by then — B's deal is
        revenue, not a logo."""
        camp_a = _campaign(user_a, client_account_a, name='A')
        camp_b = _campaign(user_a, client_account_a, name='B')
        obj_a = _objective(camp_a, user_a, client_account_a)
        obj_b = _objective(camp_b, user_a, client_account_a)
        acc = _converted(user_a, client_account_a,
                         when=timezone.now() - timedelta(days=365))
        _won(user_a, acc, client_account_a, source_campaign=camp_a,
             on=TODAY - timedelta(days=365), name='first')
        _won(user_a, acc, client_account_a, source_campaign=camp_b,
             on=TODAY, name='later')

        assert _all_three(client_account_a, camp_a, obj_a) == 1
        assert _all_three(client_account_a, camp_b, obj_b) == 0

    def test_two_wins_on_the_same_day_both_count_as_triggering(
        self, user_a, client_account_a,
    ):
        """DOCUMENTED consequence of the derivation: nothing records which cycle
        set ``became_client_at``, so the triggering one is the earliest win by
        ``outcome_date`` — a DateField. Two deals closed the same day tie, and a
        campaign carrying either earns the logo. Pinned so it is a decision, not
        a surprise."""
        camp_a = _campaign(user_a, client_account_a, name='A')
        camp_b = _campaign(user_a, client_account_a, name='B')
        obj_a = _objective(camp_a, user_a, client_account_a)
        obj_b = _objective(camp_b, user_a, client_account_a)
        acc = _converted(user_a, client_account_a)
        _won(user_a, acc, client_account_a, source_campaign=camp_a, name='one')
        _won(user_a, acc, client_account_a, source_campaign=camp_b, name='two')

        assert _all_three(client_account_a, camp_a, obj_a) == 1
        assert _all_three(client_account_a, camp_b, obj_b) == 1


# ===========================================================================
# ONCE PER CAMPAIGN — the account is the unit, not the deal or the activity
# ===========================================================================

class TestCountedOncePerCampaign:

    def test_two_attributed_wins_on_one_account_are_one_logo(
        self, user_a, client_account_a,
    ):
        """Both won the same day and both attributed to A: A gained ONE client,
        not two. A join-shaped attribution would have said two."""
        camp_a = _campaign(user_a, client_account_a, name='A')
        obj_a = _objective(camp_a, user_a, client_account_a)
        acc = _converted(user_a, client_account_a)
        _won(user_a, acc, client_account_a, source_campaign=camp_a, name='one')
        _won(user_a, acc, client_account_a, source_campaign=camp_a, name='two')

        assert _all_three(client_account_a, camp_a, obj_a) == 1

    def test_several_successful_activities_are_one_logo(
        self, user_a, client_account_a,
    ):
        """The touched-by branch is an Exists, so three successful activities on
        the winning deal read the same as one."""
        camp_b = _campaign(user_a, client_account_a, name='B')
        obj_b = _objective(camp_b, user_a, client_account_a)
        acc = _converted(user_a, client_account_a)
        won = _won(user_a, acc, client_account_a, source_campaign=None)
        for _ in range(3):
            _activity(user_a, acc, client_account_a, campaign=camp_b, cycle=won)

        assert _all_three(client_account_a, camp_b, obj_b) == 1

    def test_born_from_and_touched_by_together_are_one_logo(
        self, user_a, client_account_a,
    ):
        """Both branches match the same deal. The union must not double it."""
        camp_a = _campaign(user_a, client_account_a, name='A')
        obj_a = _objective(camp_a, user_a, client_account_a)
        acc = _converted(user_a, client_account_a)
        won = _won(user_a, acc, client_account_a, source_campaign=camp_a)
        _activity(user_a, acc, client_account_a, campaign=camp_a, cycle=won)

        assert _all_three(client_account_a, camp_a, obj_a) == 1

    def test_two_converted_accounts_are_two_logos(self, user_a,
                                                  client_account_a):
        """Anti-over-correction: the dedup is per ACCOUNT, not per campaign."""
        camp_a = _campaign(user_a, client_account_a, name='A')
        obj_a = _objective(camp_a, user_a, client_account_a)
        for index in range(2):
            acc = _converted(user_a, client_account_a, name=f'Conv{index}')
            _won(user_a, acc, client_account_a, source_campaign=camp_a,
                 name=f'won{index}')

        assert _all_three(client_account_a, camp_a, obj_a) == 2


# ===========================================================================
# Isolation + query bound
# ===========================================================================

class TestIsolationAndQueryBound:

    def test_another_tenants_logo_never_leaks(self, user_a, client_account_a):
        """The transition set is bounded by ``client_id`` BEFORE any campaign
        filter, so a converted account in another tenant cannot reach this
        campaign's count — not even through the born-from branch, which is a
        plain column comparison and would otherwise happily match across
        tenants.

        Tenant B is built inline: tests/campaigns/conftest.py re-exports the
        tenant A fixtures only.
        """
        from end_users.models import ClientAccount

        other_tenant = ClientAccount.objects.create(
            name='Tenant B Co', is_b2b=True, max_users=20,
        )
        camp_a = _campaign(user_a, client_account_a, name='A')
        obj_a = _objective(camp_a, user_a, client_account_a)
        other_acc = _converted(user_a, other_tenant, name='OtherTenant')
        # ...and it is even born from THIS campaign, so only the tenant bound
        # keeps it out.
        _won(user_a, other_acc, other_tenant, source_campaign=camp_a)

        assert _all_three(client_account_a, camp_a, obj_a) == 0
        assert campaign_new_logos(camp_a.id, other_tenant.id) == 1

    def test_the_count_is_one_query_whatever_the_volume(
        self, user_a, client_account_a, django_assert_num_queries,
    ):
        camp_a = _campaign(user_a, client_account_a, name='A')
        for index in range(4):
            acc = _converted(user_a, client_account_a, name=f'Bulk{index}')
            won = _won(user_a, acc, client_account_a, source_campaign=camp_a,
                       name=f'won{index}')
            for _ in range(2):
                _activity(user_a, acc, client_account_a, campaign=camp_a,
                          cycle=won)

        with django_assert_num_queries(1):
            assert campaign_new_logos(camp_a.id, client_account_a.id) == 4
