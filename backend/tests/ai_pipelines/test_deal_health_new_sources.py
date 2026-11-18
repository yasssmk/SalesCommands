# backend/tests/ai_pipelines/test_deal_health_new_sources.py
"""
Sprint « Deal health v2 », step 3b — the deal health reads ALL the sources,
only the NEW ones since its last snapshot, and the previous diagnostic.

Real path only: POST /module-ai-pipelines/deal-health/run/ with the real
DealHealthPipeline and the fake provider, which captures the system + user
prompts (tests/ai_pipelines/conftest.py).

  (a) a ManagerNote, an email (Activity.transcript), an Impact metric and a
      Competitor without tech row all reach the prompt;
  (b) a second run with nothing new: only the previous diagnostic and the
      static context, no former evidence;
  (c) a ManagerNote added after the snapshot: only it;
  (d) the notes of a NON-analysed activity changed after the snapshot
      (through the real notes endpoint): present;
  (e) above the input bound, the OLDEST transcript is cut first, traced in
      the run's sub_calls;
  (f) the snapshot carries a non-empty sources_cursor;
  (g) « to replace » no longer appears in the deal-health prompt;
  (h) the static context (account, deal description, origin campaign,
      products' description and value proposition) is sent at EVERY run.
"""

import json
from datetime import timedelta

import pytest
from django.utils import timezone

from app_modules.ai_pipelines.constants import (
    DEAL_HEALTH_CURSOR_ACTIVITIES,
    DEAL_HEALTH_CURSOR_MANAGER_NOTES,
    DEAL_HEALTH_CURSOR_SIGNALS,
    DEAL_HEALTH_TRUNCATION_INPUT_BUDGET,
)
from app_modules.ai_pipelines.models import AIPipelineRun
from app_modules.signals.constants import (
    ImpactType,
    ScopeLevel,
    SignalDimension,
    SignalSource,
    SignalStatus,
    SignalWhat,
)

from tests.ai_pipelines.test_deal_health_pipeline import _VALID_DIAGNOSTIC
from tests.decision_cycles.conftest import (  # noqa: F401
    pytest_configure,
    _jwt_only_no_csrf,
    tenant_a_id,
    tenant_b_id,
    client_account_a,
    client_account_b,
    role_individual_a,
    role_individual_b,
    user_a,
    user_b,
    account,
    other_tenant_account,
    activity,
    contact,
    api,
    authenticate,
    authed_api_a,
    authed_api_b,
    cache_invalidation_calls,
    cycle,
    product_catalog_entry,
    deal_product,
)


pytestmark = pytest.mark.django_db

RUN_URL = '/module-ai-pipelines/deal-health/run/'

EMAIL_TEXT = 'Email from the prospect: we need the SOC 2 report before any pilot.'
NOTE_TEXT = 'Push for a meeting with the CFO before the end of the quarter.'
METRIC_TEXT = '12 hours lost every week on manual reconciliation'
IMPACT_SUMMARY = 'Time lost on reconciliation'
IMPACT_QUOTE = 'we lose a day every week reconciling invoices'
COMPETITOR = 'RivalSoft'
PREVIOUS_READING = _VALID_DIAGNOSTIC['global_reading']


# =============================================================================
# FIXTURES / FACTORIES
# =============================================================================

@pytest.fixture
def provider(patch_active_provider):
    patch_active_provider.replies['deal_health'] = json.dumps(_VALID_DIAGNOSTIC)
    return patch_active_provider


def _activity(cycle, user, *, activity_type='CALL', status='COMPLETED', days_ago=1, **fields):
    from app_modules.activities.models import Activity
    now = timezone.now()
    a = Activity(
        title='Activity', activity_type=activity_type, status=status,
        account=cycle.account, owner=user, decision_cycle=cycle,
        scheduled_date=(now - timedelta(days=days_ago)).date(),
        completed_at=(now - timedelta(days=days_ago)) if status == 'COMPLETED' else None,
        **fields,
    )
    a.save(user=user, client_id=cycle.client_id)
    return a


def _manager_note(cycle, user, content):
    from app_modules.decision_cycles.models import ManagerNote
    n = ManagerNote(decision_cycle=cycle, content=content)
    n.save(user=user, client_id=cycle.client_id)
    return n


def _impact(cycle, user):
    from app_modules.signals.models import ImpactSignal
    i = ImpactSignal(
        account=cycle.account, decision_cycle=cycle,
        source=SignalSource.MANUAL, status=SignalStatus.VALIDATED,
        what=SignalWhat.OPS, dimension=SignalDimension.TIME,
        scope_level=ScopeLevel.BUSINESS, impact_type=ImpactType.FINANCIAL,
        summary=IMPACT_SUMMARY, source_quote=IMPACT_QUOTE,
        metric_text=METRIC_TEXT,
    )
    i.save(user=user, client_id=cycle.client_id)
    return i


def _competitor(cycle, user, name=COMPETITOR):
    from app_modules.signals.models import CompetitorSignal
    c = CompetitorSignal(
        account=cycle.account, decision_cycle=cycle,
        source=SignalSource.MANUAL, status=SignalStatus.VALIDATED,
        competitor_name=name, summary='Also evaluated by the prospect',
    )
    c.save(user=user, client_id=cycle.client_id)
    return c


def _tech(cycle, user, name='LegacyERP', **flags):
    from app_modules.signals.models import TechStackSignal
    t = TechStackSignal(
        account=cycle.account, decision_cycle=cycle,
        source=SignalSource.MANUAL, status=SignalStatus.VALIDATED,
        tech_name=name, source_quote=f'They run on {name}', **flags,
    )
    t.save(user=user, client_id=cycle.client_id)
    return t


@pytest.fixture
def rich_cycle(cycle, user_a):
    """A ManagerNote, an email, an Impact with a metric, a lone Competitor."""
    _manager_note(cycle, user_a, NOTE_TEXT)
    _activity(cycle, user_a, activity_type='EMAIL', transcript=EMAIL_TEXT)
    _impact(cycle, user_a)
    _competitor(cycle, user_a)
    return cycle


def _run(api, cycle, provider):
    """One deal-health run → (prompt sent, response snapshot)."""
    before = len(provider.calls_for('deal_health'))
    resp = api.post(RUN_URL, {'decision_cycle_id': str(cycle.id)}, format='json')
    assert resp.status_code == 201, resp.content
    calls = provider.calls_for('deal_health')
    assert len(calls) == before + 1
    return calls[-1]['system'] + '\n' + calls[-1]['user'], resp.data['data']['snapshot']


# =============================================================================
# (a) — all the sources reach the prompt
# =============================================================================

def test_a_every_source_reaches_the_prompt(authed_api_a, rich_cycle, provider):
    prompt, _ = _run(authed_api_a, rich_cycle, provider)

    assert NOTE_TEXT in prompt
    assert EMAIL_TEXT in prompt
    assert METRIC_TEXT in prompt
    assert COMPETITOR in prompt


# =============================================================================
# (b) / (c) / (d) — only what is new since the snapshot
# =============================================================================

def test_b_a_second_run_without_news_sends_no_former_evidence(
    authed_api_a, rich_cycle, provider,
):
    _run(authed_api_a, rich_cycle, provider)
    prompt, _ = _run(authed_api_a, rich_cycle, provider)

    # The validated signals were re-sent at every run before step 3b.
    for former in (NOTE_TEXT, EMAIL_TEXT, METRIC_TEXT, COMPETITOR,
                   IMPACT_SUMMARY, IMPACT_QUOTE):
        assert former not in prompt
    assert PREVIOUS_READING in prompt          # the previous diagnostic
    assert rich_cycle.name in prompt           # the static context


def test_c_only_the_new_manager_note(authed_api_a, rich_cycle, user_a, provider):
    _run(authed_api_a, rich_cycle, provider)
    _manager_note(rich_cycle, user_a, 'New note: the champion is moving to another team.')

    prompt, _ = _run(authed_api_a, rich_cycle, provider)

    assert 'New note: the champion is moving to another team.' in prompt
    assert NOTE_TEXT not in prompt


def test_d_notes_of_a_non_analysed_activity_changed_after_the_snapshot(
    authed_api_a, cycle, user_a, provider,
):
    meeting = _activity(cycle, user_a, activity_type='MEETING', status='PLANNED',
                        days_ago=-2, outcome_notes='First notes.')
    _run(authed_api_a, cycle, provider)

    resp = authed_api_a.post(
        f'/module-activities/{meeting.id}/notes/',
        {'outcome_notes': 'Updated notes: budget owner is the COO.'}, format='json',
    )
    assert resp.status_code == 200, resp.content

    prompt, _ = _run(authed_api_a, cycle, provider)
    assert 'Updated notes: budget owner is the COO.' in prompt


# =============================================================================
# (e) — input bound: the oldest transcript is cut first, traced
# =============================================================================

def test_e_the_oldest_transcript_is_cut_first_and_traced(
    authed_api_a, cycle, user_a, provider, monkeypatch,
):
    from app_modules.ai_pipelines.services.deal_health_evidence_builder import (
        DealHealthEvidenceBuilder,
    )
    monkeypatch.setattr(DealHealthEvidenceBuilder, 'MAX_INPUT_CHARS', 4000, raising=False)

    old = _activity(cycle, user_a, days_ago=10, transcript='O' * 3000)
    _activity(cycle, user_a, days_ago=1, transcript='N' * 3000)

    prompt, _ = _run(authed_api_a, cycle, provider)

    assert 'N' * 3000 in prompt            # the recent one, whole
    assert 'O' * 3000 not in prompt        # the oldest one, cut
    assert 'truncated' in prompt

    run = AIPipelineRun.objects.filter(source_decision_cycle=cycle).latest('created_at')
    trace = run.sub_calls[-1]['input_truncation']
    assert trace['cuts'][0]['activity_id'] == str(old.id)
    assert trace['cuts'][0]['reason'] == DEAL_HEALTH_TRUNCATION_INPUT_BUDGET
    assert trace['cuts'][0]['original_chars'] == 3000
    assert trace['cuts'][0]['kept_chars'] < 3000


# =============================================================================
# (f) — the snapshot carries the cursor
# =============================================================================

def test_f_the_snapshot_carries_a_sources_cursor(authed_api_a, rich_cycle, provider):
    _, snapshot = _run(authed_api_a, rich_cycle, provider)

    cursor = snapshot['sources_cursor']
    assert set(cursor) == {
        DEAL_HEALTH_CURSOR_ACTIVITIES, DEAL_HEALTH_CURSOR_SIGNALS,
        DEAL_HEALTH_CURSOR_MANAGER_NOTES,
    }


# =============================================================================
# (g) — « to replace » is no longer read by the deal health
# =============================================================================

def test_g_to_replace_is_not_in_the_prompt(authed_api_a, cycle, user_a, provider):
    _tech(cycle, user_a, name='LegacyERP', is_to_replace=True)

    prompt, _ = _run(authed_api_a, cycle, provider)

    assert 'LegacyERP' in prompt               # the tool is still evidence
    assert 'to replace' not in prompt.lower()


# =============================================================================
# (h) — the static context is sent at every run
# =============================================================================

def test_h_the_static_context_is_sent_at_every_run(
    authed_api_a, cycle, user_a, deal_product, product_catalog_entry, provider,
):
    from app_modules.campaigns.constants import CampaignType
    from app_modules.campaigns.models import Campaign

    today = timezone.now().date()
    campaign = Campaign(
        name='Q3 Outbound', campaign_type=CampaignType.TARGETED, owner=user_a,
        planned_start_date=today, planned_end_date=today + timedelta(days=30),
        activity_objective='Book a discovery call with the finance lead',
    )
    campaign.save(user=user_a, client_id=cycle.client_id)
    product_catalog_entry.value_proposition = 'Close the books in two days'
    product_catalog_entry.save(user=user_a, client_id=cycle.client_id)
    cycle.description = 'Finance automation for the EU entities'
    cycle.source_campaign = campaign
    cycle.save(user=user_a, client_id=cycle.client_id)
    from core.constants import INDUSTRIES
    industry_value, industry_label = INDUSTRIES[0]
    cycle.account.industry = industry_value
    cycle.account.company_size = '200-500'
    cycle.account.save(user=user_a, client_id=cycle.client_id)

    for _ in range(2):                     # first run, then a run with no news
        prompt, _snapshot = _run(authed_api_a, cycle, provider)
        assert 'Annual enterprise subscription' in prompt      # product description
        assert 'Close the books in two days' in prompt         # value proposition
        assert 'Finance automation for the EU entities' in prompt
        assert 'Book a discovery call with the finance lead' in prompt
        assert 'Targeted Campaign' in prompt
        # Format-agnostic (the v2 context is compact JSON, step 5).
        assert '200-500' in prompt                              # company size
        assert str(industry_label) in prompt                    # industry
