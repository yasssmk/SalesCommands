# backend/tests/ai_pipelines/test_deal_health_new_info_sources.py
"""
Sprint 2 Game Plan — sub-step S7 (defect of sprint 1): what counts as NEW
information for a deal health — ONE predicate, read by the freshness (the
DC banner) AND by the « nothing new » guard of a re-run.

Before: both read DealHealthEvidenceBuilder.has_new_sources, whose activity
test is `fresh_activities_qs` — every activity of the cycle with content
whose updated_at moved. A note typed on an activity (outcome_notes) or any
edit of an activity lit the banner (NEW_SOURCES) and let the deal health
run again. A stakeholder removed, added or whose role changed was not seen.

Now (PO decisions, S7 + Q4), counted since the last snapshot:
  * an ANALYSED activity — a successful extraction (analysis_state) of an
    activity of the cycle, after the snapshot's date — NEW_SOURCES;
  * a validated signal — NEW_SOURCES (unchanged);
  * a manager note — NEW_SOURCES (unchanged);
  * the static context of the deal (products, value, step, account…) —
    NEW_SOURCES (unchanged, PO decision);
  * the declared step — STEP_CHANGED (unchanged);
  * the stakeholders of the cycle (ids + the role of their current signal),
    added, removed or role changed — STAKEHOLDERS_CHANGED; a snapshot whose
    cursor has no stakeholders fingerprint (taken before S7) is NOT a
    reason by itself.
NEVER a typed note nor a mere edit of an activity.

Real path: GET /decision_cycles/<id>/health-snapshots/latest/ (`freshness`)
and POST /module-ai-pipelines/deal-health/run/ (real view, real
DealHealthPipeline, fake LLM provider). The first snapshot is written by the
real POST. Seeded through the ORM, for want of a light API path: the
changes themselves (an extraction run row, a signal, a manager note, a
product, stakeholders) and, for the pre-S7 case, the snapshot's cursor
without its stakeholders key. The typed note goes through the real notes
endpoint.

The invariant « a reason is present <=> the re-run is accepted » is checked
on EVERY source.

DB: Postgres.
"""

import copy
import json

import pytest
from django.utils import timezone

from app_modules.ai_pipelines.constants import (
    AIPipelineStatus,
    AIPipelineType,
    DEAL_HEALTH_CURSOR_STAKEHOLDERS,
    DEAL_HEALTH_FRESHNESS_NEW_SOURCES,
    DEAL_HEALTH_FRESHNESS_STAKEHOLDERS_CHANGED,
    DEAL_HEALTH_FRESHNESS_STEP_CHANGED,
    DEAL_HEALTH_NO_NEW_SOURCES_CODE,
)
from app_modules.decision_cycles.models import DealHealthSnapshot
from app_modules.signals.constants import (
    PeopleRole,
    ScopeLevel,
    SignalDimension,
    SignalSource,
    SignalStatus,
    SignalWhat,
)

from tests.ai_pipelines.conftest import fake_provider, patch_active_provider  # noqa: F401
from tests.ai_pipelines.deal_health_fixtures import V2_DIAGNOSTIC
from tests.ai_pipelines.test_deal_health_guards import redis_store  # noqa: F401
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
    five_steps,
    planned_activity_on_step,
    completed_activity_on_step,
)


pytestmark = pytest.mark.django_db

RUN_URL = '/module-ai-pipelines/deal-health/run/'
NEW_SOURCES = DEAL_HEALTH_FRESHNESS_NEW_SOURCES
STEP_CHANGED = DEAL_HEALTH_FRESHNESS_STEP_CHANGED
STAKEHOLDERS_CHANGED = DEAL_HEALTH_FRESHNESS_STAKEHOLDERS_CHANGED
ACCEPTED = 'ACCEPTED'

_keys = iter(range(10_000))


# =============================================================================
# FIXTURES / HELPERS
# =============================================================================

@pytest.fixture
def provider(patch_active_provider):
    patch_active_provider.replies['deal_health'] = json.dumps(copy.deepcopy(V2_DIAGNOSTIC))
    return patch_active_provider


def _people(cycle, user, name, role):
    """A validated PeopleSignal on the cycle (born PENDING, then validated in
    place — no hook)."""
    from app_modules.signals.models import PeopleSignal
    p = PeopleSignal(account=cycle.account, decision_cycle=cycle,
                     source=SignalSource.LLM_EXTRACTED, role=role, full_name=name,
                     source_quote=f'{name} said so', confidence=0.8)
    p.save(user=user, client_id=cycle.client_id)
    PeopleSignal.objects.filter(pk=p.pk).update(status=SignalStatus.VALIDATED)
    return PeopleSignal.objects.get(pk=p.pk)


def _stakeholder(cycle, user, name, current_signal=None):
    from app_modules.decision_cycles.models import Stakeholder
    s = Stakeholder(decision_cycle=cycle, full_name=name, current_signal=current_signal)
    s.save(user=user, client_id=cycle.client_id)
    return s


@pytest.fixture
def deal(cycle, five_steps, planned_activity_on_step, completed_activity_on_step, user_a):
    """Technical Fit current (Qualification held, a planned meeting), two
    stakeholders, two validated People signals (CHAMPION, ECONOMIC_BUYER):
    everything exists BEFORE the first snapshot."""
    completed_activity_on_step(five_steps[0])
    meeting = planned_activity_on_step(five_steps[1], outcome_notes='First notes.')
    champion = _people(cycle, user_a, 'Marc Durand', PeopleRole.CHAMPION)
    buyer = _people(cycle, user_a, 'Lea Martin', PeopleRole.ECONOMIC_BUYER)
    marc = _stakeholder(cycle, user_a, 'Marc Durand', current_signal=champion)
    lea = _stakeholder(cycle, user_a, 'Lea Martin', current_signal=buyer)
    return {'cycle': cycle, 'steps': five_steps, 'meeting': meeting,
            'champion': champion, 'buyer': buyer, 'marc': marc, 'lea': lea}


def _first_snapshot(api, cycle):
    resp = api.post(RUN_URL, {'decision_cycle_id': str(cycle.id)}, format='json',
                    HTTP_IDEMPOTENCY_KEY=f's7-first-{next(_keys)}')
    assert resp.status_code == 201, resp.content
    return DealHealthSnapshot.objects.get(id=resp.data['data']['snapshot']['id'])


def _reasons(api, cycle):
    resp = api.get(f'/decision_cycles/{cycle.id}/health-snapshots/latest/')
    assert resp.status_code == 200, resp.content
    fresh = resp.data['freshness']
    assert fresh['applies'] is True
    assert fresh['has_new_info'] is bool(fresh['reasons'])
    return fresh['reasons']


def _rerun(api, cycle):
    """ACCEPTED when the deal health ran again, else the INFO code."""
    resp = api.post(RUN_URL, {'decision_cycle_id': str(cycle.id)}, format='json',
                    HTTP_IDEMPOTENCY_KEY=f's7-rerun-{next(_keys)}')
    if resp.status_code == 201:
        return ACCEPTED
    assert resp.status_code == 200, resp.content
    return resp.data['code']


# -- the sources --------------------------------------------------------------

def _typed_note(api, d, user):
    resp = api.post(f"/module-activities/{d['meeting'].id}/notes/",
                    {'outcome_notes': 'Budget owner is the COO.'}, format='json')
    assert resp.status_code == 200, resp.content


def _activity_edited(api, d, user):
    meeting = d['meeting']
    meeting.description = 'Agenda: demo of the reporting module.'
    meeting.save(user=user, client_id=meeting.client_id)


def _analysed_activity(api, d, user):
    from app_modules.ai_pipelines.models import AIPipelineRun
    meeting = d['meeting']
    AIPipelineRun.objects.create(
        pipeline_type=AIPipelineType.TRANSCRIPT_SIGNALS, prompt_versions={'system': 'v1'},
        provider='openai', model_name='gpt-4o-mini', temperature=0.0,
        source_activity=meeting, input_hash='h', status=AIPipelineStatus.SUCCESS,
        sub_calls=[], total_tokens_used=1, total_duration_ms=1, error_message='',
        created_signals_count=0, client_id=meeting.client_id,
        created_by=user, updated_by=user,
    )


def _validated_signal(api, d, user):
    from app_modules.signals.models import PainSignal
    cycle = d['cycle']
    PainSignal(
        account=cycle.account, decision_cycle=cycle,
        source=SignalSource.MANUAL, status=SignalStatus.VALIDATED,
        what=SignalWhat.OPS, dimension=SignalDimension.TIME,
        scope_level=ScopeLevel.DEPARTMENT,
        summary='Manual reporting takes 10h/week',
        source_quote='We spend 10 hours every week on manual reports',
    ).save(user=user, client_id=cycle.client_id)


def _manager_note(api, d, user):
    from app_modules.decision_cycles.models import ManagerNote
    cycle = d['cycle']
    ManagerNote(decision_cycle=cycle, content='Push for the CFO meeting.').save(
        user=user, client_id=cycle.client_id)


def _step_changed(api, d, user):
    from app_modules.activities.constants import ActivityStatus
    meeting = d['meeting']
    meeting.status = ActivityStatus.COMPLETED      # the Technical Fit meeting is held
    meeting.completed_at = timezone.now()
    meeting.save(user=user, client_id=meeting.client_id)
    from app_modules.activities.models import Activity
    from app_modules.activities.constants import ActivityType
    nxt = Activity(title='Solution review', activity_type=ActivityType.MEETING,
                   status=ActivityStatus.PLANNED, account=meeting.account, owner=user,
                   decision_cycle=d['cycle'], decision_step=d['steps'][2],
                   scheduled_date=timezone.now().date() + timezone.timedelta(days=7))
    nxt.save(user=user, client_id=meeting.client_id)


def _stakeholder_removed(api, d, user):
    d['lea'].delete()


def _stakeholder_role_changed(api, d, user):
    marc = d['marc']
    marc.current_signal = d['buyer']                # CHAMPION -> ECONOMIC_BUYER
    marc.save(user=user, client_id=marc.client_id)


def _stakeholder_added(api, d, user):
    _stakeholder(d['cycle'], user, 'Hugo Petit')


def _product_added(api, d, user):
    from app_modules.decision_cycles.models import DealProduct
    from app_modules.product_catalog.models import ProductCatalog
    cycle = d['cycle']
    product = ProductCatalog(name='Reporting suite', description='Automated reporting.',
                             value_proposition='Closes the month in two days.')
    product.save(user=user, client_id=cycle.client_id)
    DealProduct(decision_cycle=cycle, product_catalog_entry=product, quantity=1).save(
        user=user, client_id=cycle.client_id)


def _nothing(api, d, user):
    pass


SOURCES = [
    # (source, the reasons expected after it)
    (_typed_note,               []),
    (_activity_edited,          []),
    (_nothing,                  []),
    (_analysed_activity,        [NEW_SOURCES]),
    (_validated_signal,         [NEW_SOURCES]),
    (_manager_note,             [NEW_SOURCES]),
    (_product_added,            [NEW_SOURCES]),
    (_step_changed,             [NEW_SOURCES, STEP_CHANGED]),
    (_stakeholder_removed,      [STAKEHOLDERS_CHANGED]),
    (_stakeholder_role_changed, [STAKEHOLDERS_CHANGED]),
    (_stakeholder_added,        [STAKEHOLDERS_CHANGED]),
]


# =============================================================================
# EVERY SOURCE — its reasons, and the invariant reason <=> re-run accepted
# =============================================================================

@pytest.mark.parametrize('source, expected', SOURCES, ids=[s.__name__.strip('_') for s, _ in SOURCES])
def test_each_source_and_the_invariant(
    source, expected, authed_api_a, deal, user_a, provider, redis_store,
):
    cycle = deal['cycle']
    _first_snapshot(authed_api_a, cycle)
    assert _reasons(authed_api_a, cycle) == []      # nothing new right after it

    source(authed_api_a, deal, user_a)
    reasons = _reasons(authed_api_a, cycle)
    outcome = _rerun(authed_api_a, cycle)

    assert reasons == expected
    # THE invariant: a reason <=> the re-run is accepted.
    if reasons:
        assert outcome == ACCEPTED
    else:
        assert outcome == DEAL_HEALTH_NO_NEW_SOURCES_CODE


# =============================================================================
# A SNAPSHOT TAKEN BEFORE S7 — no stakeholders fingerprint, no reason by itself
# =============================================================================

def test_a_snapshot_without_stakeholders_fingerprint_is_no_reason_by_itself(
    authed_api_a, deal, user_a, provider, redis_store,
):
    cycle = deal['cycle']
    snapshot = _first_snapshot(authed_api_a, cycle)
    # A pre-S7 snapshot: its cursor has no stakeholders key (ORM — no API path).
    cursor = dict(snapshot.sources_cursor)
    assert DEAL_HEALTH_CURSOR_STAKEHOLDERS in cursor   # S7 stores it on every run
    cursor.pop(DEAL_HEALTH_CURSOR_STAKEHOLDERS)
    DealHealthSnapshot.objects.filter(pk=snapshot.pk).update(sources_cursor=cursor)

    assert _reasons(authed_api_a, cycle) == []         # the absence is no reason
    _stakeholder_removed(authed_api_a, deal, user_a)    # nothing to compare with
    assert _reasons(authed_api_a, cycle) == []
    assert _rerun(authed_api_a, cycle) == DEAL_HEALTH_NO_NEW_SOURCES_CODE
