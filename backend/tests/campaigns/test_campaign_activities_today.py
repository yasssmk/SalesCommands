# backend/tests/campaigns/test_campaign_activities_today.py
"""
Campaign list annotation: activities_today — "N activities to do today".

The TARGETED card renders this number, and it must be the SAME number the rep
sees on the playlist's "To do today" chip. Three implementations of one rule now
exist: the JS chip (CampaignPlaylistTab.todayActivities), get_playlist's Python
bucketing, and this SQL annotation (_activities_today on the list queryset). The
JS chip is the reference — it is what the rep actually sees — and the annotation
mirrors it verbatim.

An Activity counts as "today" iff:
  - status = PLANNED (ON_HOLD is bucketed separately, never counts),
  - date-eligible: scheduled_date IS NULL OR <= today (overdue included; the
    max(scheduled_date, today) clamp is display-only), and
  - first-planned for its contact: campaign_contact IS NULL, OR a callback, OR
    sequence_position IS NULL, OR no earlier PLANNED non-callback step of the
    same contact exists.
Scope: campaign-wide (executor=None), matching the playlist's default view.

Tests:
  1. correctness            — annotation == a hand count over the tricky cases.
  2. parity (drift guard)   — on a dataset where the annotation and get_playlist
                              AGREE, annotation == get_playlist's today_count. Reds
                              if either implementation drifts without the other.
  3+4. documented divergences — two cases where get_playlist lags the JS/annotation
                              reference. Each acted, not circumvented, so a future
                              fix to get_playlist turns exactly one of them green.
  5. anti-fan-out           — accounts_count, targets_total AND activities_today
                              all correct together (three subqueries on one
                              queryset must not multiply each other).

Postgres 5432; Campaign planned dates NOT NULL via the `campaign` fixture.
"""

from datetime import timedelta

import pytest
from django.utils import timezone

from app_modules.activities.constants import ActivityStatus, ActivityType
from app_modules.campaigns.constants import CampaignContactStatus
from app_modules.campaigns.services.campaign_execution_service import (
    CampaignExecutionService,
)

URL = '/campaigns/'

PLANNED = ActivityStatus.PLANNED
ON_HOLD = ActivityStatus.ON_HOLD
COMPLETED = ActivityStatus.COMPLETED


# ---------------------------------------------------------------------------
# Response unwrap helpers (mirror test_campaign_targets_progress.py)
# ---------------------------------------------------------------------------

def _rows(resp):
    body = resp.data
    data = body['data'] if isinstance(body, dict) and 'data' in body else body
    if isinstance(data, dict) and 'results' in data:
        return data['results']
    return data


def _row_for(resp, campaign_id):
    for row in _rows(resp):
        if str(row['id']) == str(campaign_id):
            return row
    raise AssertionError(f'campaign {campaign_id} not found in list payload')


def _playlist_today(campaign, user, account):
    """The size of get_playlist's TODAY bucket — the "To do today" chip count,
    the Python oracle the annotation is parity-checked against."""
    svc = CampaignExecutionService(user=user, client_id=account.client_id)
    return svc.get_playlist(campaign)['today_count']


# ---------------------------------------------------------------------------
# Dataset builder — the AGREEING cases (annotation and get_playlist concur)
# ---------------------------------------------------------------------------

def _seed_agreeing_cases(make_campaign_contact, make_campaign_activity, today):
    """Seed the tricky cases on which the annotation and get_playlist AGREE.

    Returns the expected today count for these rows (4). Deliberately EXCLUDES
    the two documented-divergence cases (undated callback, no-campaign_contact
    activity), which have their own tests.
    """
    IN_PROGRESS = CampaignContactStatus.IN_PROGRESS

    # Contact with several PLANNED steps — only the first (min position) counts.
    cc_multi = make_campaign_contact(status=IN_PROGRESS)
    make_campaign_activity(cc_multi, scheduled_date=today, sequence_position=1)  # counts
    make_campaign_activity(cc_multi, scheduled_date=today, sequence_position=2)  # superseded
    make_campaign_activity(cc_multi, scheduled_date=today, sequence_position=3)  # superseded

    # Dated (past) callback — counts regardless of position (here position 2,
    # with no position-1 step, so only the callback exemption can surface it).
    cc_cb = make_campaign_contact(status=IN_PROGRESS)
    make_campaign_activity(
        cc_cb, scheduled_date=today - timedelta(days=3),
        sequence_position=2, is_callback_followup=True,
    )  # counts

    # Regular step dated in the past — counts (overdue included).
    cc_past = make_campaign_contact(status=IN_PROGRESS)
    make_campaign_activity(cc_past, scheduled_date=today - timedelta(days=5),
                           sequence_position=1)  # counts

    # Regular step dated in the future — does NOT count.
    cc_future = make_campaign_contact(status=IN_PROGRESS)
    make_campaign_activity(cc_future, scheduled_date=today + timedelta(days=5),
                           sequence_position=1)

    # ON_HOLD — does NOT count (bucketed separately).
    cc_hold = make_campaign_contact(status=IN_PROGRESS)
    make_campaign_activity(cc_hold, scheduled_date=today, sequence_position=1,
                           status=ON_HOLD)

    # COMPLETED — does NOT count (not PLANNED; outside get_playlist's queryset).
    cc_done = make_campaign_contact(status=IN_PROGRESS)
    make_campaign_activity(cc_done, scheduled_date=today, sequence_position=1,
                           status=COMPLETED)

    # First step with NULL scheduled_date — counts (date-eligible when NULL).
    cc_nulldate = make_campaign_contact(status=IN_PROGRESS)
    make_campaign_activity(cc_nulldate, scheduled_date=None, sequence_position=1)  # counts

    # counts: cc_multi(1) + cc_cb(1) + cc_past(1) + cc_nulldate(1) = 4
    return 4


# ---------------------------------------------------------------------------
# 1. CORRECTNESS — annotation vs a hand count
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_activities_today_correctness(
    authed_api_a, user_a, account, campaign,
    make_campaign_contact, make_campaign_activity,
):
    """Every tricky case, counted by hand. The agreeing cases contribute 4; a
    PLANNED activity with NO campaign_contact contributes 1 more (the annotation
    counts it, matching the JS chip) → 5."""
    today = timezone.now().date()
    agreeing = _seed_agreeing_cases(make_campaign_contact, make_campaign_activity, today)

    # Activity with no campaign_contact — counts (first-planned clause:
    # campaign_contact IS NULL). Built via the factory with campaign_contact=None.
    make_campaign_activity(None, scheduled_date=today, sequence_position=1)

    resp = authed_api_a.get(URL)
    assert resp.status_code == 200
    row = _row_for(resp, campaign.id)

    assert row['activities_today'] == agreeing + 1  # 4 + 1 = 5


# ---------------------------------------------------------------------------
# 2. PARITY — annotation == get_playlist's today bucket (the drift guard)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_activities_today_parity_with_get_playlist(
    authed_api_a, user_a, account, campaign,
    make_campaign_contact, make_campaign_activity,
):
    """On a dataset built from the AGREEING cases only, the list annotation must
    equal get_playlist's today bucket. This is THE guard: it reds if either the
    SQL annotation or the Python bucketing changes without the other."""
    today = timezone.now().date()
    expected = _seed_agreeing_cases(make_campaign_contact, make_campaign_activity, today)

    resp = authed_api_a.get(URL)
    assert resp.status_code == 200
    annotation = _row_for(resp, campaign.id)['activities_today']

    playlist_today = _playlist_today(campaign, user_a, account)

    # Both oracles agree, and both equal the hand-computed count.
    assert annotation == playlist_today == expected  # 4


# ---------------------------------------------------------------------------
# 3. DOCUMENTED DIVERGENCE — callback with no scheduled_date
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_divergence_undated_callback(
    authed_api_a, user_a, account, campaign,
    make_campaign_contact, make_campaign_activity,
):
    """A callback follow-up with NO scheduled_date.

    The JS chip and this annotation count it (date-eligible when scheduled_date
    is NULL) — that is what the rep sees, so it is the reference. get_playlist
    does NOT count it: its callback branch tests `if scheduled and scheduled <=
    today`, so a NULL date falls through to Upcoming. get_playlist should be
    aligned one day; until then this test ACTS the divergence so a future fix
    turns exactly this test green.
    """
    today = timezone.now().date()
    cc = make_campaign_contact(status=CampaignContactStatus.IN_PROGRESS)
    make_campaign_activity(cc, scheduled_date=None, sequence_position=1,
                           is_callback_followup=True)

    resp = authed_api_a.get(URL)
    assert resp.status_code == 200
    annotation = _row_for(resp, campaign.id)['activities_today']

    playlist_today = _playlist_today(campaign, user_a, account)

    assert annotation == 1       # JS/annotation reference: counted
    assert playlist_today == 0    # get_playlist lags: not counted


# ---------------------------------------------------------------------------
# 4. DOCUMENTED DIVERGENCE — activity with no campaign_contact
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_divergence_activity_without_campaign_contact(
    authed_api_a, user_a, account, campaign,
    make_campaign_contact, make_campaign_activity,
):
    """A PLANNED, non-callback activity with NO campaign_contact.

    The JS chip and this annotation count it (first-planned clause:
    campaign_contact IS NULL) — the reference. get_playlist does NOT: its
    regular-step branch computes `is_first_planned = cc_id is not None and
    min_pos_map.get(cc_id) == position`, so a NULL contact is never first-planned
    and drops to Upcoming. Distinct cause from the undated-callback divergence
    (a different branch of the bucketing), hence its own test. get_playlist
    should be aligned one day; this test acts the divergence in the meantime.
    """
    today = timezone.now().date()
    make_campaign_activity(None, scheduled_date=today, sequence_position=1)

    resp = authed_api_a.get(URL)
    assert resp.status_code == 200
    annotation = _row_for(resp, campaign.id)['activities_today']

    playlist_today = _playlist_today(campaign, user_a, account)

    assert annotation == 1       # JS/annotation reference: counted
    assert playlist_today == 0    # get_playlist lags: not counted


# ---------------------------------------------------------------------------
# 5. ANTI-FAN-OUT — three subqueries on one queryset stay independent
# ---------------------------------------------------------------------------

def _mk_account(client_account, user, name):
    from app_modules.accounts.models import CompanyAccount
    a = CompanyAccount(company_name=name, has_buying_decision=True)
    a.save(user=user, client_id=client_account.id)
    return a


def _mk_campaign_account(campaign, account, client_account, user):
    from app_modules.campaigns.models import CampaignAccount
    ca = CampaignAccount(campaign=campaign, account=account)
    ca.save(user=user, client_id=client_account.id)
    return ca


def _mk_contact(account, client_account, user, name):
    from app_modules.contacts.models import Contact
    c = Contact(account=account, first_name=name, last_name='T')
    c.save(user=user, client_id=client_account.id)
    return c


def _enroll(campaign_account, contact, client_account, user, status):
    from app_modules.campaigns.models import CampaignContact
    cc = CampaignContact(campaign_account=campaign_account, contact=contact,
                         status=status)
    cc.save(user=user, client_id=client_account.id)
    return cc


def _mk_activity(campaign, campaign_account, campaign_contact, account,
                 client_account, user, scheduled_date, sequence_position=1,
                 status=PLANNED):
    from app_modules.activities.models import Activity
    a = Activity(
        title=f'Step {sequence_position}',
        activity_type=ActivityType.CALL,
        status=status,
        account=account,
        owner=user,
        campaign=campaign,
        campaign_account=campaign_account,
        campaign_contact=campaign_contact,
        scheduled_date=scheduled_date,
        sequence_position=sequence_position,
    )
    a.save(user=user, client_id=client_account.id)
    return a


@pytest.mark.django_db
def test_activities_today_no_fanout(
    authed_api_a, user_a, client_account_a, account, campaign, campaign_account,
):
    """One campaign, 3 accounts / 6 contacts / 5 PLANNED activities (4 due-and-
    first). accounts_count, targets_total, targets_worked AND activities_today
    must ALL be correct together — the three correlated subqueries on the list
    queryset must not multiply one another.
    """
    today = timezone.now().date()
    IN_PROGRESS = CampaignContactStatus.IN_PROGRESS
    DONE = CampaignContactStatus.COMPLETED
    STOPPED = CampaignContactStatus.STOPPED

    # Account 1 (fixture account + fixture campaign_account): 2 contacts.
    cA = _enroll(campaign_account, _mk_contact(account, client_account_a, user_a, 'A'),
                 client_account_a, user_a, IN_PROGRESS)
    cB = _enroll(campaign_account, _mk_contact(account, client_account_a, user_a, 'B'),
                 client_account_a, user_a, IN_PROGRESS)
    _mk_activity(campaign, campaign_account, cA, account, client_account_a, user_a,
                 scheduled_date=today, sequence_position=1)                 # counts
    _mk_activity(campaign, campaign_account, cB, account, client_account_a, user_a,
                 scheduled_date=today, sequence_position=1)                 # counts
    _mk_activity(campaign, campaign_account, cB, account, client_account_a, user_a,
                 scheduled_date=today, sequence_position=2)                 # superseded

    # Account 2: 2 contacts.
    acc2 = _mk_account(client_account_a, user_a, 'Acc Two')
    ca2 = _mk_campaign_account(campaign, acc2, client_account_a, user_a)
    cC = _enroll(ca2, _mk_contact(acc2, client_account_a, user_a, 'C'),
                 client_account_a, user_a, IN_PROGRESS)
    cD = _enroll(ca2, _mk_contact(acc2, client_account_a, user_a, 'D'),
                 client_account_a, user_a, DONE)
    _mk_activity(campaign, ca2, cC, acc2, client_account_a, user_a,
                 scheduled_date=today, sequence_position=1)                 # counts
    # cD is COMPLETED — its chain is cancelled, so no PLANNED activity.

    # Account 3: 2 contacts.
    acc3 = _mk_account(client_account_a, user_a, 'Acc Three')
    ca3 = _mk_campaign_account(campaign, acc3, client_account_a, user_a)
    cE = _enroll(ca3, _mk_contact(acc3, client_account_a, user_a, 'E'),
                 client_account_a, user_a, STOPPED)
    cF = _enroll(ca3, _mk_contact(acc3, client_account_a, user_a, 'F'),
                 client_account_a, user_a, IN_PROGRESS)
    _mk_activity(campaign, ca3, cF, acc3, client_account_a, user_a,
                 scheduled_date=today - timedelta(days=2), sequence_position=1)  # counts
    # cE is STOPPED — no PLANNED activity.

    resp = authed_api_a.get(URL)
    assert resp.status_code == 200
    row = _row_for(resp, campaign.id)

    # Three accounts — NOT 3 × contacts nor 3 × activities.
    assert row['accounts_count'] == 3
    # Six enrolled contacts — NOT multiplied by accounts or activities.
    assert row['targets_total'] == 6
    # Two contacts in a final state (COMPLETED + STOPPED).
    assert row['targets_worked'] == 2
    # Four due-and-first PLANNED activities (cA, cB step1, cC, cF); cB step2 is
    # superseded, cD/cE have no PLANNED activity.
    assert row['activities_today'] == 4
