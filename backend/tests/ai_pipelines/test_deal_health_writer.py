# tests/ai_pipelines/test_deal_health_writer.py
"""
Tests for DealHealthWriter.

Validates structural validation logic (accepts valid diagnostics,
rejects malformed ones with PromptParseError) and snapshot creation.
"""

import pytest

from app_modules.ai_pipelines.prompts.base import PromptParseError
from app_modules.ai_pipelines.services.deal_health_writer import DealHealthWriter


# Re-export shared fixtures.
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
    five_steps,
)


# =========================================================================
# FIXTURES
# =========================================================================

@pytest.fixture
def writer():
    return DealHealthWriter()


@pytest.fixture
def pipeline_run(db, user_a, client_account_a):
    """A minimal AIPipelineRun for linking to the snapshot."""
    from app_modules.ai_pipelines.constants import (
        AIPipelineStatus,
        AIPipelineType,
    )
    from app_modules.ai_pipelines.models import AIPipelineRun

    run = AIPipelineRun(
        pipeline_type=AIPipelineType.DEAL_HEALTH,
        prompt_versions={'system': 'v1', 'context': 'v1', 'diagnostic': 'v1'},
        provider='test',
        model_name='test-model',
        temperature=0.2,
        source_activity=None,
        input_hash='a' * 64,
        status=AIPipelineStatus.RUNNING,
        sub_calls=[],
        total_tokens_used=0,
        total_duration_ms=0,
        error_message='',
        created_signals_count=0,
        client_id=client_account_a.id,
        created_by=user_a,
        updated_by=user_a,
    )
    run.save()
    return run


def _valid_diagnostic():
    """Return a minimal valid diagnostic JSON."""
    return {
        'global_reading': 'The client recognizes an operational problem.',
        'dimensions': [
            {'key': 'problem_recognized', 'status': 'confirmed', 'evidence': 'Quote A', 'missing': ''},
            {'key': 'felt_pain', 'status': 'missing_evidence', 'evidence': '', 'missing': 'Not explored'},
            {'key': 'impact_understood', 'status': 'unclear', 'evidence': 'Partial data', 'missing': 'Quantification'},
            {'key': 'desired_gain', 'status': 'suggested', 'evidence': 'Mentioned goal', 'missing': ''},
            {'key': 'urgency', 'status': 'missing_evidence', 'evidence': '', 'missing': 'No timeline'},
            {'key': 'willingness_to_act', 'status': 'unclear', 'evidence': '', 'missing': 'Budget unclear'},
            {'key': 'solution_trust', 'status': 'suggested', 'evidence': 'Positive demo feedback', 'missing': ''},
        ],
        'discovery_gaps': [
            {
                'kind': 'qualification',
                'dimension': 'felt_pain',
                'public_text': 'Pain depth not yet qualified.',
                'suggested_questions': ['How does this impact your daily work?'],
            },
            {
                'kind': 'procedural',
                'dimension': 'decision_process',
                'public_text': 'Validation process unknown.',
                'suggested_questions': ['What are the approval steps?'],
                'related_actor': 'Finance',
            },
        ],
        'levers': {
            'desires': [{'summary': 'Better reporting visibility', 'theme': 'OPS:TIME'}],
            'value': [{'summary': '10h/week recoverable', 'theme': 'OPS:TIME'}],
            'cost': [{'summary': 'Budget not owned by champion'}],
            'constraints': [{'summary': 'ROI > 20% in 18 months', 'rigidity': 'FIRM', 'is_metric': True}],
        },
        'themes': [{'label': 'Operations efficiency', 'summary': 'Operational pain recognized but depth not proven.'}],
        'evidence_scope': {'validated_signals_count': 5, 'note': 'Based on captured evidence.'},
    }


# =========================================================================
# HAPPY PATH
# =========================================================================

@pytest.mark.django_db
class TestWriterHappyPath:

    def test_valid_diagnostic_creates_snapshot(self, writer, cycle, pipeline_run, user_a):
        parsed = _valid_diagnostic()
        snapshot = writer.write(
            parsed=parsed,
            decision_cycle=cycle,
            run=pipeline_run,
            user=user_a,
            client_id=cycle.client_id,
        )

        assert snapshot.id is not None
        assert snapshot.decision_cycle_id == cycle.id
        assert snapshot.pipeline_run_id == pipeline_run.id
        assert snapshot.diagnostic == parsed
        assert snapshot.client_id == cycle.client_id

    def test_snapshot_linked_to_run(self, writer, cycle, pipeline_run, user_a):
        parsed = _valid_diagnostic()
        snapshot = writer.write(
            parsed=parsed,
            decision_cycle=cycle,
            run=pipeline_run,
            user=user_a,
            client_id=cycle.client_id,
        )

        from app_modules.decision_cycles.models import DealHealthSnapshot
        reloaded = DealHealthSnapshot.objects.get(id=snapshot.id)
        assert reloaded.pipeline_run_id == pipeline_run.id


# =========================================================================
# VALIDATION FAILURES
# =========================================================================

@pytest.mark.django_db
class TestWriterValidation:

    def test_not_a_dict_raises(self, writer, cycle, pipeline_run, user_a):
        with pytest.raises(PromptParseError, match='JSON object'):
            writer.write(
                parsed='not a dict',
                decision_cycle=cycle,
                run=pipeline_run,
                user=user_a,
                client_id=cycle.client_id,
            )

    def test_missing_global_reading_raises(self, writer, cycle, pipeline_run, user_a):
        parsed = _valid_diagnostic()
        del parsed['global_reading']
        with pytest.raises(PromptParseError, match='global_reading'):
            writer.write(
                parsed=parsed,
                decision_cycle=cycle,
                run=pipeline_run,
                user=user_a,
                client_id=cycle.client_id,
            )

    def test_wrong_dimension_count_raises(self, writer, cycle, pipeline_run, user_a):
        parsed = _valid_diagnostic()
        parsed['dimensions'] = parsed['dimensions'][:5]
        with pytest.raises(PromptParseError, match='7 dimensions'):
            writer.write(
                parsed=parsed,
                decision_cycle=cycle,
                run=pipeline_run,
                user=user_a,
                client_id=cycle.client_id,
            )

    def test_invalid_dimension_key_raises(self, writer, cycle, pipeline_run, user_a):
        parsed = _valid_diagnostic()
        parsed['dimensions'][0]['key'] = 'bogus_key'
        with pytest.raises(PromptParseError, match='Unknown or missing dimension key'):
            writer.write(
                parsed=parsed,
                decision_cycle=cycle,
                run=pipeline_run,
                user=user_a,
                client_id=cycle.client_id,
            )

    def test_invalid_dimension_status_raises(self, writer, cycle, pipeline_run, user_a):
        parsed = _valid_diagnostic()
        parsed['dimensions'][0]['status'] = 'weak'
        with pytest.raises(PromptParseError, match='Invalid status'):
            writer.write(
                parsed=parsed,
                decision_cycle=cycle,
                run=pipeline_run,
                user=user_a,
                client_id=cycle.client_id,
            )

    def test_dimensions_wrong_order_raises(self, writer, cycle, pipeline_run, user_a):
        parsed = _valid_diagnostic()
        parsed['dimensions'][0], parsed['dimensions'][1] = (
            parsed['dimensions'][1], parsed['dimensions'][0]
        )
        with pytest.raises(PromptParseError, match='order'):
            writer.write(
                parsed=parsed,
                decision_cycle=cycle,
                run=pipeline_run,
                user=user_a,
                client_id=cycle.client_id,
            )

    def test_invalid_gap_kind_raises(self, writer, cycle, pipeline_run, user_a):
        parsed = _valid_diagnostic()
        parsed['discovery_gaps'] = [{'kind': 'tactical', 'dimension': 'x', 'public_text': 'y'}]
        with pytest.raises(PromptParseError, match='Invalid gap kind'):
            writer.write(
                parsed=parsed,
                decision_cycle=cycle,
                run=pipeline_run,
                user=user_a,
                client_id=cycle.client_id,
            )

    def test_missing_levers_raises(self, writer, cycle, pipeline_run, user_a):
        parsed = _valid_diagnostic()
        del parsed['levers']
        with pytest.raises(PromptParseError, match='levers'):
            writer.write(
                parsed=parsed,
                decision_cycle=cycle,
                run=pipeline_run,
                user=user_a,
                client_id=cycle.client_id,
            )

    def test_missing_lever_group_raises(self, writer, cycle, pipeline_run, user_a):
        parsed = _valid_diagnostic()
        del parsed['levers']['desires']
        with pytest.raises(PromptParseError, match='desires'):
            writer.write(
                parsed=parsed,
                decision_cycle=cycle,
                run=pipeline_run,
                user=user_a,
                client_id=cycle.client_id,
            )

    def test_missing_discovery_gaps_raises(self, writer, cycle, pipeline_run, user_a):
        parsed = _valid_diagnostic()
        del parsed['discovery_gaps']
        with pytest.raises(PromptParseError, match='discovery_gaps'):
            writer.write(
                parsed=parsed,
                decision_cycle=cycle,
                run=pipeline_run,
                user=user_a,
                client_id=cycle.client_id,
            )

    def test_no_snapshot_created_on_validation_failure(self, writer, cycle, pipeline_run, user_a):
        """Ensure no snapshot is persisted when validation fails."""
        from app_modules.decision_cycles.models import DealHealthSnapshot

        initial_count = DealHealthSnapshot.objects.filter(decision_cycle=cycle).count()

        parsed = _valid_diagnostic()
        parsed['dimensions'] = 'not a list'
        with pytest.raises(PromptParseError):
            writer.write(
                parsed=parsed,
                decision_cycle=cycle,
                run=pipeline_run,
                user=user_a,
                client_id=cycle.client_id,
            )

        assert DealHealthSnapshot.objects.filter(decision_cycle=cycle).count() == initial_count
