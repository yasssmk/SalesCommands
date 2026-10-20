# backend/tests/ai_pipelines/test_people_role_unknown.py
"""
TD-279 U (PO) -- PeopleRole.UNKNOWN: the person takes part in the deal but
their role is not established yet.

  a) POST /module-signals/people/ with role UNKNOWN -> 201, shown "Unknown".
  b) The choices endpoint exposes UNKNOWN / "Unknown" (choosable at edit).
  c) A VALIDATED PeopleSignal UNKNOWN:
       * readiness unchanged (only DM / EB / CHAMPION count);
       * counted in the DC People view (qualified, "Unknown");
       * prep_call and deal_health receive it as a "role to qualify" --
         never filtered out, never as the bare code.
  d) The People extraction prompt does NOT offer UNKNOWN yet (byte-identical
     context; the prompt change belongs to step M).
"""

import pytest
from django.urls import reverse
from rest_framework import status

from app_modules.ai_pipelines.constants import PEOPLE_ROLE_TO_QUALIFY
from app_modules.signals.constants import PeopleRole, SignalStatus

# Re-export the shared decision-cycle fixtures so pytest discovers them.
from tests.decision_cycles.conftest import (  # noqa: F401
    pytest_configure,
    _jwt_only_no_csrf,
    tenant_a_id,
    client_account_a,
    role_individual_a,
    user_a,
    account,
    activity,
    contact,
    api,
    authenticate,
    authed_api_a,
    cache_invalidation_calls,
    cycle,
)


pytestmark = pytest.mark.django_db

PEOPLE_URL = '/module-signals/people/'


@pytest.fixture
def unknown_person(account, activity, cycle, user_a, contact):
    """A VALIDATED PeopleSignal of role UNKNOWN on the cycle, on `contact`."""
    from app_modules.signals.models import PeopleSignal
    activity.decision_cycle = cycle
    activity.save(user=user_a)
    sig = PeopleSignal(
        account=account,
        source_activity=activity,
        decision_cycle=cycle,
        role=PeopleRole.UNKNOWN,
        target_contact=contact,
        status=SignalStatus.VALIDATED,
    )
    sig.save(user=user_a, client_id=account.client_id)
    return sig


# =============================================================================
# a) + b) — API
# =============================================================================

class TestApi:

    def test_a_post_people_with_role_unknown_is_created(
        self, authed_api_a, account, activity, contact,
    ):
        resp = authed_api_a.post(PEOPLE_URL, {
            'signal_type': 'people',
            'source': 'MANUAL',
            'account': str(account.id),
            'source_activity': str(activity.id),
            'role': 'UNKNOWN',
            'target_contact': str(contact.id),
        }, format='json')
        assert resp.status_code == status.HTTP_201_CREATED, resp.content
        data = resp.json()['data']
        assert data['role'] == 'UNKNOWN'
        assert data['role_display'] == 'Unknown'

    def test_b_choices_endpoint_exposes_unknown(self, authed_api_a):
        resp = authed_api_a.get(reverse('module_signals:choices'))
        assert resp.status_code == 200
        assert {'value': 'UNKNOWN', 'label': 'Unknown'} in resp.json()['data']['people_roles']


# =============================================================================
# c) — consumers
# =============================================================================

class TestConsumers:

    def test_readiness_ignores_unknown(self, cycle, unknown_person):
        from app_modules.decision_cycles.services.readiness_score_service import (
            ReadinessScoreService,
        )
        dims = {d['name']: d for d in ReadinessScoreService().calculate(cycle)['dimensions']}
        assert dims['decision_maker']['filled'] is False
        assert dims['champion']['filled'] is False

    def test_dc_people_counts_unknown_as_qualified(self, cycle, unknown_person, contact):
        from app_modules.decision_cycles.services.people_consolidation_service import (
            PeopleConsolidationService,
        )
        result = PeopleConsolidationService().consolidate(cycle)
        [entry] = result['qualified']
        assert entry['role'] == 'UNKNOWN'
        assert entry['role_display'] == 'Unknown'
        assert entry['target_contact']['id'] == str(contact.id)
        assert result['unqualified'] == []

    def test_c_prep_call_receives_a_role_to_qualify(self, activity, contact, unknown_person):
        from app_modules.ai_pipelines.prompts.prep_call.context import build_context_layer
        from app_modules.ai_pipelines.services.prep_call.input_pack_assembler import (
            PrepInputPackAssembler,
        )
        pack = PrepInputPackAssembler().build(
            activity=activity, target_contact=contact, brief_mode='CONVICTION',
        )
        assert pack['prep_context']['upcoming_activity']['primary_contact']['role'] == (
            PEOPLE_ROLE_TO_QUALIFY)
        assert pack['stakeholder_focus']['role'] == PEOPLE_ROLE_TO_QUALIFY
        context = build_context_layer(pack, 'CONVICTION')
        assert f'Primary contact: role={PEOPLE_ROLE_TO_QUALIFY},' in context
        assert f'Role: {PEOPLE_ROLE_TO_QUALIFY}' in context
        assert 'UNKNOWN' not in context

    def test_deal_health_receives_a_role_to_qualify(self, cycle, unknown_person):
        from app_modules.ai_pipelines.prompts.deal_health.context import build_context_layer
        from app_modules.ai_pipelines.prompts.deal_health.diagnostic_v1 import (
            build_diagnostic_request,
        )
        from app_modules.ai_pipelines.services.deal_health_evidence_builder import (
            DealHealthEvidenceBuilder,
        )
        pack = DealHealthEvidenceBuilder().build(cycle)
        # Not filtered: the person is a qualified stakeholder and a people signal.
        assert len(pack['people']['qualified']) == 1
        assert pack['people']['unqualified_count'] == 0
        assert len(pack['signals']['people']) == 1
        assert f'  - {PEOPLE_ROLE_TO_QUALIFY}' in build_context_layer(pack)
        diagnostic = build_diagnostic_request(pack)
        assert f'Role: {PEOPLE_ROLE_TO_QUALIFY}' in diagnostic
        assert 'UNKNOWN' not in diagnostic

    def test_known_roles_reach_the_prompts_unchanged(self, cycle, unknown_person):
        from app_modules.ai_pipelines.services.deal_health_evidence_builder import (
            DealHealthEvidenceBuilder,
        )
        unknown_person.role = PeopleRole.CHAMPION
        unknown_person.save(update_fields=['role'])
        pack = DealHealthEvidenceBuilder().build(cycle)
        assert pack['people']['qualified'][0]['role_display'] == 'Champion'
        assert pack['signals']['people'][0]['role'] == 'CHAMPION'


# =============================================================================
# d) — extraction prompt not touched in step U
# =============================================================================

class TestExtractionPromptUnchanged:

    def test_people_context_does_not_offer_unknown(self, activity):
        from app_modules.ai_pipelines.prompts.transcript_signals.context import (
            CONTEXT_VERSION, build_context_layer,
        )
        context = build_context_layer(activity, 'people')
        assert '"CHAMPION" (Champion)' in context
        assert '"UNKNOWN"' not in context
        assert CONTEXT_VERSION == 'v8'
