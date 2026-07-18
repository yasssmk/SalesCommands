# backend/tests/bi/test_kpi_todo_campaign.py
"""
TD-89 — campaign sequence activities in the rep todo (Home windows).

Product rule (validated with the PO):
  A campaign step is OUTBOUND chasing, not a client commitment. Its scheduled
  date is our own effort cadence, so a passed step is NOT late — it is "still
  to do today". Therefore, for a PENDING (PLANNED) campaign step the Home
  buckets on an *actionable* date = max(scheduled_date, today), computed at
  READ time (zero write, Q6-native):

    - step date in the future  -> normal forward window (today / 7d / 4w),
    - step date today or past  -> TODAY,
    - a campaign step is NEVER in the OVERDUE window (callback or not).

  Only the NEXT pending step per contact surfaces (a chain is sequential —
  step 2 is not actionable before step 1), so a neglected chain does not flood
  the todo with its cascaded past-dated later steps.

Decision-cycle / non-campaign activities are ISO: they keep
COALESCE(due_date, scheduled_date) and a real OVERDUE bucket (guarded here and
by the untouched tests/bi/test_kpi_todo.py).

These tests are RED before the fix and GREEN after it.
"""

from datetime import timedelta

import pytest
from django.core.cache import cache
from django.utils import timezone

from app_modules.accounts.models import CompanyAccount
from app_modules.activities.constants import ActivityStatus, ActivityType
from app_modules.activities.models import Activity
from app_modules.bi import registry
from app_modules.bi.cache import cached_run
from app_modules.bi.definitions import load_all
from app_modules.bi.definitions.activities import TodoWindow, todo_my_windows
from app_modules.bi.signals import cache_invalidation as ci
from app_modules.campaigns.constants import CampaignContactStatus, CampaignType
from app_modules.campaigns.models import Campaign, CampaignAccount, CampaignContact
from app_modules.contacts.models import Contact
from permissions.compat import AuthContext


TODAY = timezone.now().date()


# ---------------------------------------------------------------------------
# helpers (local, mirroring tests/bi/test_kpi_todo.py)
# ---------------------------------------------------------------------------

def _ctx(user, client_account):
    return AuthContext(user_id=str(user.id), client_id=str(client_account.id),
                       is_authenticated=True)


def _mk_user(email, client_account, role, **extra):
    from end_users.models import User
    return User.objects.create(email=email, client_account=client_account,
                               role=role, is_active=True, **extra)


def _mk_account(name, owner, client_account):
    acc = CompanyAccount(company_name=name, has_buying_decision=True,
                         account_owner=owner)
    acc.save(user=owner, client_id=client_account.id)
    return acc


def _mk_chain(owner, account, client_account, planned_end):
    """Return (campaign, campaign_account) ready to hang steps on."""
    campaign = Campaign(
        name='Q3 Outbound', campaign_type=CampaignType.OUTBOUND, owner=owner,
        planned_start_date=TODAY, planned_end_date=planned_end,
    )
    campaign.save(user=owner, client_id=client_account.id)
    ca = CampaignAccount(campaign=campaign, account=account)
    ca.save(user=owner, client_id=client_account.id)
    return campaign, ca


def _mk_contact(account, owner, client_account, n):
    c = Contact(account=account, first_name=f'C{n}', last_name='T')
    c.save(user=owner, client_id=client_account.id)
    return c


def _mk_campaign_contact(campaign_account, contact, owner, client_account,
                         status=CampaignContactStatus.IN_PROGRESS):
    cc = CampaignContact(campaign_account=campaign_account, contact=contact,
                         status=status)
    cc.save(user=owner, client_id=client_account.id)
    return cc


def _mk_step(owner, account, client_account, campaign, campaign_account,
             campaign_contact, sched, position=1, status=ActivityStatus.PLANNED,
             is_callback=False, due=None):
    """A campaign step Activity, born (like production) with
    due_date = campaign.planned_end_date."""
    a = Activity(
        title=f'Step {position}',
        activity_type=ActivityType.CALL,
        status=status,
        account=account,
        owner=owner,
        campaign=campaign,
        campaign_account=campaign_account,
        campaign_contact=campaign_contact,
        sequence_position=position,
        scheduled_date=sched,
        due_date=due if due is not None else campaign.planned_end_date,
        is_callback_followup=is_callback,
    )
    a.save(user=owner, client_id=client_account.id)
    return a


def _mk_plain_activity(owner, account, client_account, status=ActivityStatus.PLANNED,
                       due=None, sched=None):
    a = Activity(title='dc', activity_type=ActivityType.CALL, status=status,
                 account=account, owner=owner, due_date=due, scheduled_date=sched)
    a.save(user=owner, client_id=client_account.id)
    return a


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _flush_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def windows_kpi(db):
    load_all()
    ci.connect_invalidation_receivers()
    yield todo_my_windows
    ci.disconnect_invalidation_receivers()
    registry.clear()


@pytest.fixture
def user_a(db, client_account_a, role_individual_a):
    return _mk_user('rep-a@a.test', client_account_a, role_individual_a)


@pytest.fixture
def account_a(db, client_account_a, user_a):
    return _mk_account('A Corp', user_a, client_account_a)


def _windows(windows_kpi, user_a, client_account_a):
    res = cached_run(windows_kpi, _ctx(user_a, client_account_a), scope='mine')
    return res.value


# ---------------------------------------------------------------------------
# tests
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestCampaignStepSurfaces:

    def test_overdue_step_surfaces_in_today_not_overdue(
        self, windows_kpi, user_a, account_a, client_account_a
    ):
        """A step whose date passed, in a still-running campaign, must show in
        TODAY (still to chase) and NEVER in OVERDUE. Today it vanishes: its
        due_date = planned_end_date (TODAY+30) buckets it beyond every window."""
        campaign, ca = _mk_chain(user_a, account_a, client_account_a,
                                 planned_end=TODAY + timedelta(days=30))
        contact = _mk_contact(account_a, user_a, client_account_a, 1)
        cc = _mk_campaign_contact(ca, contact, user_a, client_account_a)
        _mk_step(user_a, account_a, client_account_a, campaign, ca, cc,
                 sched=TODAY - timedelta(days=3), position=1)

        w = _windows(windows_kpi, user_a, client_account_a)
        assert w[TodoWindow.TODAY] == 1
        assert w[TodoWindow.OVERDUE] == 0

    def test_future_step_uses_normal_forward_window(
        self, windows_kpi, user_a, account_a, client_account_a
    ):
        """Step date in 3 days -> next_7_days, not clamped to today."""
        campaign, ca = _mk_chain(user_a, account_a, client_account_a,
                                 planned_end=TODAY + timedelta(days=30))
        contact = _mk_contact(account_a, user_a, client_account_a, 1)
        cc = _mk_campaign_contact(ca, contact, user_a, client_account_a)
        _mk_step(user_a, account_a, client_account_a, campaign, ca, cc,
                 sched=TODAY + timedelta(days=3), position=1)

        w = _windows(windows_kpi, user_a, client_account_a)
        assert w[TodoWindow.TODAY] == 0
        assert w[TodoWindow.OVERDUE] == 0
        assert w[TodoWindow.NEXT_7_DAYS] == 1

    def test_only_next_pending_step_per_contact_surfaces(
        self, windows_kpi, user_a, account_a, client_account_a
    ):
        """A neglected chain: step1 & step2 both past-dated. Only step1 (the
        next pending) surfaces in TODAY — step2 must not flood the todo."""
        campaign, ca = _mk_chain(user_a, account_a, client_account_a,
                                 planned_end=TODAY + timedelta(days=30))
        contact = _mk_contact(account_a, user_a, client_account_a, 1)
        cc = _mk_campaign_contact(ca, contact, user_a, client_account_a)
        _mk_step(user_a, account_a, client_account_a, campaign, ca, cc,
                 sched=TODAY - timedelta(days=3), position=1)
        _mk_step(user_a, account_a, client_account_a, campaign, ca, cc,
                 sched=TODAY - timedelta(days=1), position=2)

        w = _windows(windows_kpi, user_a, client_account_a)
        assert w[TodoWindow.TODAY] == 1
        assert w[TodoWindow.OVERDUE] == 0


@pytest.mark.django_db
class TestNeverOverdueInvariant:
    """The pure negative invariant: NO campaign activity — ordinary step or
    callback, whatever its dates — ever lands in the OVERDUE window."""

    def _one_step(self, user_a, account_a, client_account_a, sched, planned_end,
                  is_callback):
        campaign, ca = _mk_chain(user_a, account_a, client_account_a,
                                 planned_end=planned_end)
        contact = _mk_contact(account_a, user_a, client_account_a, 1)
        cc = _mk_campaign_contact(ca, contact, user_a, client_account_a)
        _mk_step(user_a, account_a, client_account_a, campaign, ca, cc,
                 sched=sched, position=1, is_callback=is_callback)

    @pytest.mark.parametrize('is_callback', [False, True])
    @pytest.mark.parametrize('sched_offset,end_offset', [
        (-3, 30),    # step passed, campaign still running
        (-10, -1),   # step passed, campaign end also passed
        (-3, 10),    # step passed, campaign ends within 4 weeks
    ])
    def test_campaign_step_never_overdue(
        self, windows_kpi, user_a, account_a, client_account_a,
        is_callback, sched_offset, end_offset,
    ):
        self._one_step(
            user_a, account_a, client_account_a,
            sched=TODAY + timedelta(days=sched_offset),
            planned_end=TODAY + timedelta(days=end_offset),
            is_callback=is_callback,
        )
        w = _windows(windows_kpi, user_a, client_account_a)
        assert w[TodoWindow.OVERDUE] == 0


@pytest.mark.django_db
class TestIsoBehaviour:

    def test_paused_on_hold_step_not_in_today_or_overdue(
        self, windows_kpi, user_a, account_a, client_account_a
    ):
        """ON_HOLD (paused campaign) steps are out of scope: the clamp is
        PLANNED-only. They must not appear in TODAY/OVERDUE (accepted: they may
        sit in a forward window by planned_end_date — logged as a TD)."""
        campaign, ca = _mk_chain(user_a, account_a, client_account_a,
                                 planned_end=TODAY + timedelta(days=10))
        contact = _mk_contact(account_a, user_a, client_account_a, 1)
        cc = _mk_campaign_contact(ca, contact, user_a, client_account_a)
        _mk_step(user_a, account_a, client_account_a, campaign, ca, cc,
                 sched=TODAY - timedelta(days=3), position=1,
                 status=ActivityStatus.ON_HOLD)

        w = _windows(windows_kpi, user_a, client_account_a)
        assert w[TodoWindow.TODAY] == 0
        assert w[TodoWindow.OVERDUE] == 0

    def test_non_campaign_activity_overdue_unchanged(
        self, windows_kpi, user_a, account_a, client_account_a
    ):
        """DC / non-campaign activity keeps COALESCE(due, sched) and a real
        OVERDUE bucket — iso-behaviour."""
        _mk_plain_activity(user_a, account_a, client_account_a,
                           due=TODAY - timedelta(days=2))

        w = _windows(windows_kpi, user_a, client_account_a)
        assert w[TodoWindow.OVERDUE] == 1


# ---------------------------------------------------------------------------
# manager parity — the count KPI and the team-todo rows must agree on a
# campaign chain (both count only the next pending step), so the manager's tile
# never shows a number its table can't back with rows.
# ---------------------------------------------------------------------------

@pytest.fixture
def manager(db, client_account_a, role_individual_a):
    return _mk_user('mgr@a.test', client_account_a, role_individual_a)


@pytest.fixture
def team_x(db, client_account_a, manager):
    from end_users.models import Team
    return Team.objects.create(name='Team X', client_account=client_account_a,
                               manager=manager)


@pytest.fixture
def member1(db, client_account_a, role_individual_a, team_x):
    return _mk_user('alice@a.test', client_account_a, role_individual_a,
                    first_name='Alice', last_name='Martin', team=team_x)


@pytest.mark.django_db
class TestManagerParity:

    def test_campaign_chain_count_equals_team_rows(
        self, windows_kpi, manager, member1, client_account_a
    ):
        """A 3-step pending chain on ONE member: the todo_team_by_owner count for
        that member equals 1 AND equals the number of build_team_todo_population
        rows for them — the tile/table parity invariant, preserved because both
        apply only_next_pending_campaign_steps."""
        from app_modules.bi.definitions.activities import (
            build_team_todo_population, todo_team_by_owner,
        )

        acc = _mk_account('M1 Corp', member1, client_account_a)
        campaign, ca = _mk_chain(member1, acc, client_account_a,
                                 planned_end=TODAY + timedelta(days=30))
        contact = _mk_contact(acc, member1, client_account_a, 1)
        cc = _mk_campaign_contact(ca, contact, member1, client_account_a)
        # 3 pending steps, all past-dated (a neglected chain).
        for pos in (1, 2, 3):
            _mk_step(member1, acc, client_account_a, campaign, ca, cc,
                     sched=TODAY - timedelta(days=4 - pos), position=pos)

        ctx = _ctx(manager, client_account_a)
        count_res = cached_run(todo_team_by_owner, ctx, scope='team')
        rows = build_team_todo_population(ctx, scope='team').filter(
            owner_id=member1.id
        )

        assert count_res.value.get(member1.id) == 1      # only the next step
        assert rows.count() == 1
        assert count_res.value.get(member1.id) == rows.count()

    def test_callback_chain_count_equals_team_rows(
        self, windows_kpi, manager, member1, client_account_a
    ):
        """A callback-inserted chain (CALLBACK_PENDING contact): the callback
        activity collides at the same sequence_position as the original next
        step, and BOTH surface today (the callback is never superseded, the
        original step has no earlier PLANNED non-callback sibling). Parity holds
        by construction — count == rows == 2. The "only the callback should
        surface for a paused contact" semantics is deferred (TD-98); this test
        pins the current, parity-preserving behaviour so TD-98 changes it
        knowingly."""
        from app_modules.bi.definitions.activities import (
            build_team_todo_population, todo_team_by_owner,
        )

        acc = _mk_account('M1 Corp', member1, client_account_a)
        campaign, ca = _mk_chain(member1, acc, client_account_a,
                                 planned_end=TODAY + timedelta(days=30))
        contact = _mk_contact(acc, member1, client_account_a, 1)
        cc = _mk_campaign_contact(ca, contact, member1, client_account_a,
                                  status=CampaignContactStatus.CALLBACK_PENDING)
        # Step 1 done; original steps 2/3/4 planned; a callback inserted at the
        # same position 2 as the original step 2 (the real collision shape).
        _mk_step(member1, acc, client_account_a, campaign, ca, cc,
                 sched=TODAY - timedelta(days=2), position=1,
                 status=ActivityStatus.COMPLETED)
        _mk_step(member1, acc, client_account_a, campaign, ca, cc,
                 sched=TODAY + timedelta(days=5), position=2)
        _mk_step(member1, acc, client_account_a, campaign, ca, cc,
                 sched=TODAY + timedelta(days=7), position=3)
        _mk_step(member1, acc, client_account_a, campaign, ca, cc,
                 sched=TODAY + timedelta(days=9), position=4)
        _mk_step(member1, acc, client_account_a, campaign, ca, cc,
                 sched=TODAY + timedelta(days=5), position=2, is_callback=True)

        ctx = _ctx(manager, client_account_a)
        count_res = cached_run(todo_team_by_owner, ctx, scope='team')
        rows = build_team_todo_population(ctx, scope='team').filter(
            owner_id=member1.id
        )

        assert count_res.value.get(member1.id) == 2      # callback + original step 2
        assert rows.count() == 2
        assert count_res.value.get(member1.id) == rows.count()
