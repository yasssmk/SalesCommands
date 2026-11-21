# backend/tests/ai_pipelines/test_deal_health_context_and_hold.py
"""
Sprint « Deal health v2 », sub-step 6c — two corrections of the step 6 run
guards (A10).

1. A changed STATIC context is new: the description of the deal, its
   products (description / value proposition), its origin campaign, the
   account fields read — fingerprinted in the sources cursor by the SAME
   read as the prompt; another fingerprint → the run happens.
2. PO decision — ON_HOLD is not closed: the deal health runs on a paused
   deal (with the usual « nothing new » guard). Only WON / LOST /
   NOT_QUALIFIED answer DEAL_HEALTH_CYCLE_CLOSED.

Real path: POST /module-ai-pipelines/deal-health/run/, the real view and
pipeline, the fake provider.

  (a) a snapshot, then the product's description changed → the run happens;
  (b) an ON_HOLD deal with something new → the run happens;
  (c) an ON_HOLD deal with nothing new → DEAL_HEALTH_NO_NEW_SOURCES;
  (d) a LOST deal → DEAL_HEALTH_CYCLE_CLOSED.
"""

import copy
import json

import pytest

from app_modules.ai_pipelines.constants import (
    DEAL_HEALTH_CYCLE_CLOSED_CODE,
    DEAL_HEALTH_NO_NEW_SOURCES_CODE,
)
from app_modules.decision_cycles.constants import CycleOutcome
from app_modules.decision_cycles.models import DealHealthSnapshot, DecisionCycle

from tests.ai_pipelines.conftest import fake_provider, patch_active_provider  # noqa: F401
from tests.ai_pipelines.deal_health_fixtures import V2_DIAGNOSTIC
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


def _reply(provider):
    provider.replies['deal_health'] = json.dumps(copy.deepcopy(V2_DIAGNOSTIC))
    return provider


def _post(api, cycle):
    return api.post(RUN_URL, {'decision_cycle_id': str(cycle.id)}, format='json')


def _calls(provider):
    return len(provider.calls_for('deal_health'))


def _snapshots(cycle):
    return DealHealthSnapshot.objects.filter(decision_cycle=cycle).count()


def _outcome(cycle, outcome):
    DecisionCycle.objects.filter(pk=cycle.pk).update(outcome=outcome)
    cycle.refresh_from_db()


def _feed(cycle, activity, user, text):
    activity.decision_cycle = cycle
    activity.transcript = text
    activity.save(user=user, client_id=cycle.client_id)


# =============================================================================
# (a) — a changed static context is new
# =============================================================================

def test_a_a_changed_product_description_makes_the_run_happen(
    authed_api_a, cycle, deal_product, product_catalog_entry, user_a, patch_active_provider,
):
    provider = _reply(patch_active_provider)
    assert _post(authed_api_a, cycle).status_code == 201
    # Nothing changed yet: the usual guard.
    assert _post(authed_api_a, cycle).data['code'] == DEAL_HEALTH_NO_NEW_SOURCES_CODE

    product_catalog_entry.description = 'Now with multi-entity consolidation'
    product_catalog_entry.save(user=user_a, client_id=cycle.client_id)
    resp = _post(authed_api_a, cycle)

    assert resp.status_code == 201, resp.content
    assert _calls(provider) == 2
    assert 'Now with multi-entity consolidation' in provider.calls_for('deal_health')[-1]['user']
    assert _snapshots(cycle) == 2


def test_a_a_changed_deal_description_makes_the_run_happen(
    authed_api_a, cycle, user_a, patch_active_provider,
):
    provider = _reply(patch_active_provider)
    assert _post(authed_api_a, cycle).status_code == 201

    cycle.description = 'Finance automation for the EU entities'
    cycle.save(user=user_a, client_id=cycle.client_id)
    resp = _post(authed_api_a, cycle)

    assert resp.status_code == 201, resp.content
    assert _calls(provider) == 2


# =============================================================================
# (b) / (c) — ON_HOLD is not closed
# =============================================================================

def test_b_an_on_hold_deal_with_something_new_runs(
    authed_api_a, cycle, activity, user_a, patch_active_provider,
):
    provider = _reply(patch_active_provider)
    _outcome(cycle, CycleOutcome.ON_HOLD)
    _feed(cycle, activity, user_a, 'Paused until the budget review in Q3.')

    resp = _post(authed_api_a, cycle)

    assert resp.status_code == 201, resp.content
    assert _calls(provider) == 1
    assert _snapshots(cycle) == 1


def test_c_an_on_hold_deal_with_nothing_new_is_the_usual_info(
    authed_api_a, cycle, activity, user_a, patch_active_provider,
):
    provider = _reply(patch_active_provider)
    _feed(cycle, activity, user_a, 'Paused until the budget review in Q3.')
    assert _post(authed_api_a, cycle).status_code == 201
    _outcome(cycle, CycleOutcome.ON_HOLD)

    resp = _post(authed_api_a, cycle)

    assert resp.status_code == 200, resp.content
    assert resp.data['code'] == DEAL_HEALTH_NO_NEW_SOURCES_CODE
    assert _calls(provider) == 1
    assert _snapshots(cycle) == 1


# =============================================================================
# (d) — a lost deal stays closed
# =============================================================================

@pytest.mark.parametrize('outcome', [
    CycleOutcome.WON, CycleOutcome.LOST, CycleOutcome.NOT_QUALIFIED,
])
def test_d_a_won_lost_or_not_qualified_deal_is_closed(
    authed_api_a, cycle, activity, user_a, patch_active_provider, outcome,
):
    provider = _reply(patch_active_provider)
    _outcome(cycle, outcome)
    _feed(cycle, activity, user_a, 'A late note.')

    resp = _post(authed_api_a, cycle)

    assert resp.status_code == 200, resp.content
    assert resp.data['code'] == DEAL_HEALTH_CYCLE_CLOSED_CODE
    assert _calls(provider) == 0
    assert _snapshots(cycle) == 0
