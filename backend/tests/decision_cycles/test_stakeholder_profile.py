# backend/tests/decision_cycles/test_stakeholder_profile.py
"""
Sprint « Deal health v2 », step 4 — the stakeholder PROFILE, one write point.

Stakeholder.profile = {field: {value, source, updated_at, updated_by,
original_value}}, written ONLY by
decision_cycles/services/stakeholder_service.apply_ai_profile /
apply_manual_profile. The rule of SignalSource (signals/constants.py),
applied PER FIELD (signals/services/signal_manager.py):

  (a) a manual entry is never overwritten by the AI;
  (b) an AI value not edited is updated by a new AI pass;
  (c) a manual edit of an AI value -> LLM_MODIFIED, original_value kept; a
      later AI pass does not overwrite it;
  (d) an unknown field, a value outside the closed list or an invalid
      language -> standard refusal, nothing written;
  (e) no serializer / endpoint returns the profile (amendment A7);
  (f) strict tenant scoping.

Real service only (no endpoint writes the profile, A7).
"""

import pytest

from app_modules.ai_pipelines.constants import AIPipelineStatus, AIPipelineType
from app_modules.decision_cycles.constants import (
    PROFILE_COMMUNICATION_LANGUAGE,
    PROFILE_CONVICTION_STATE,
    PROFILE_FRUSTRATIONS,
)
from app_modules.decision_cycles.services.stakeholder_service import (
    apply_ai_profile,
    apply_manual_profile,
    get_or_create_contact_stakeholder,
)
from app_modules.signals.constants import SignalSource
from core.exceptions import StandardizedValidationError

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
)


pytestmark = pytest.mark.django_db


def _run(client_id, user):
    from app_modules.ai_pipelines.models import AIPipelineRun
    return AIPipelineRun.objects.create(
        pipeline_type=AIPipelineType.DEAL_HEALTH, prompt_versions={'system': 'v1'},
        provider='openai', model_name='test', temperature=0.0, input_hash='h',
        status=AIPipelineStatus.SUCCESS, sub_calls=[], total_tokens_used=0,
        total_duration_ms=0, error_message='', created_signals_count=0,
        client_id=client_id, created_by=user, updated_by=user,
    )


@pytest.fixture
def stakeholder(cycle, contact, user_a):
    return get_or_create_contact_stakeholder(cycle, contact, user_a)


@pytest.fixture
def ai_run(cycle, user_a):
    return _run(cycle.client_id, user_a)


def _profile(stakeholder):
    stakeholder.refresh_from_db()
    return stakeholder.profile


# =============================================================================
# (a) — a manual entry is never overwritten by the AI
# =============================================================================

def test_a_the_ai_never_overwrites_a_manual_entry(stakeholder, user_a, ai_run):
    apply_manual_profile(stakeholder, PROFILE_COMMUNICATION_LANGUAGE, 'fr', user_a)

    apply_ai_profile(stakeholder, {PROFILE_COMMUNICATION_LANGUAGE: 'en'}, ai_run)

    entry = _profile(stakeholder)[PROFILE_COMMUNICATION_LANGUAGE]
    assert entry['value'] == 'fr'
    assert entry['source'] == SignalSource.MANUAL
    assert entry['updated_by'] == str(user_a.id)
    assert entry['original_value'] is None


# =============================================================================
# (b) — an AI value not edited is refreshed by the AI
# =============================================================================

def test_b_an_unedited_ai_value_is_updated_by_a_new_ai_pass(stakeholder, ai_run):
    apply_ai_profile(stakeholder, {PROFILE_FRUSTRATIONS: 'Month-end close takes 10 days'}, ai_run)
    first = _profile(stakeholder)[PROFILE_FRUSTRATIONS]
    assert first['value'] == 'Month-end close takes 10 days'
    assert first['source'] == SignalSource.LLM_EXTRACTED
    assert first['updated_by'] is None
    assert first['updated_at']
    assert first['run_id'] == str(ai_run.id)      # step 5: the AI run that wrote it

    apply_ai_profile(stakeholder, {PROFILE_FRUSTRATIONS: 'Close takes 10 days; audits are manual'}, ai_run)

    entry = _profile(stakeholder)[PROFILE_FRUSTRATIONS]
    assert entry['value'] == 'Close takes 10 days; audits are manual'
    assert entry['source'] == SignalSource.LLM_EXTRACTED


# =============================================================================
# (c) — a manual edit of an AI value: LLM_MODIFIED, original kept, AI stops
# =============================================================================

def test_c_a_manual_edit_of_an_ai_value_is_kept_against_the_ai(stakeholder, user_a, ai_run):
    apply_ai_profile(stakeholder, {PROFILE_CONVICTION_STATE: 'SKEPTICAL'}, ai_run)

    apply_manual_profile(stakeholder, PROFILE_CONVICTION_STATE, 'NEUTRAL', user_a)
    entry = _profile(stakeholder)[PROFILE_CONVICTION_STATE]
    assert (entry['value'], entry['source']) == ('NEUTRAL', SignalSource.LLM_MODIFIED)
    assert entry['original_value'] == 'SKEPTICAL'

    apply_ai_profile(stakeholder, {PROFILE_CONVICTION_STATE: 'CHAMPION'}, ai_run)
    apply_manual_profile(stakeholder, PROFILE_CONVICTION_STATE, 'SUPPORTIVE', user_a)

    entry = _profile(stakeholder)[PROFILE_CONVICTION_STATE]
    assert entry['value'] == 'SUPPORTIVE'
    assert entry['source'] == SignalSource.LLM_MODIFIED
    assert entry['original_value'] == 'SKEPTICAL'     # the AI's FIRST value


# =============================================================================
# (d) — invalid input: standard refusal, nothing written
# =============================================================================

def test_d_a_value_outside_the_closed_list_is_refused_and_nothing_written(stakeholder, ai_run):
    with pytest.raises(StandardizedValidationError):
        apply_ai_profile(stakeholder, {
            PROFILE_FRUSTRATIONS: 'valid text',
            PROFILE_CONVICTION_STATE: 'HAPPY',
        }, ai_run)
    assert _profile(stakeholder) == {}


def test_d_an_unknown_field_is_refused(stakeholder, user_a, ai_run):
    with pytest.raises(StandardizedValidationError):
        apply_manual_profile(stakeholder, 'salary', '100k', user_a)
    with pytest.raises(StandardizedValidationError):
        apply_ai_profile(stakeholder, {'salary': '100k'}, ai_run)
    assert _profile(stakeholder) == {}


@pytest.mark.parametrize('language', ['french', 'fr_FR', '', 'e', 'en-US-x-toolongsubtag1'])
def test_d_an_invalid_language_is_refused(stakeholder, user_a, language):
    with pytest.raises(StandardizedValidationError):
        apply_manual_profile(stakeholder, PROFILE_COMMUNICATION_LANGUAGE, language, user_a)
    assert _profile(stakeholder) == {}


def test_d_a_valid_bcp47_tag_is_accepted(stakeholder, user_a):
    apply_manual_profile(stakeholder, PROFILE_COMMUNICATION_LANGUAGE, 'pt-BR', user_a)
    assert _profile(stakeholder)[PROFILE_COMMUNICATION_LANGUAGE]['value'] == 'pt-BR'


# =============================================================================
# (e) — the profile is not exposed (amendment A7)
# =============================================================================

def test_e_the_stakeholders_endpoint_does_not_return_the_profile(
    authed_api_a, cycle, stakeholder, user_a, ai_run,
):
    apply_ai_profile(stakeholder, {PROFILE_FRUSTRATIONS: 'SECRET-FRUSTRATION-42'}, ai_run)
    assert _profile(stakeholder)                      # it IS stored

    resp = authed_api_a.get(f'/decision_cycles/{cycle.id}/stakeholders/')

    assert resp.status_code == 200, resp.content
    rows = resp.json()['data']
    assert rows and all('profile' not in row for row in rows)
    assert 'SECRET-FRUSTRATION-42' not in resp.content.decode()


# =============================================================================
# (f) — strict tenant scoping
# =============================================================================

def test_f_another_tenant_cannot_write_the_profile(stakeholder, user_b, client_account_b):
    with pytest.raises(StandardizedValidationError):
        apply_manual_profile(stakeholder, PROFILE_CONVICTION_STATE, 'NEUTRAL', user_b)
    with pytest.raises(StandardizedValidationError):
        apply_ai_profile(stakeholder, {PROFILE_CONVICTION_STATE: 'NEUTRAL'},
                         _run(client_account_b.id, user_b))
    assert _profile(stakeholder) == {}
