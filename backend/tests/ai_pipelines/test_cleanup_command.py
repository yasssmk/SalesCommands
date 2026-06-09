# tests/ai_pipelines/test_cleanup_command.py
"""
Tests for the cleanup_pipeline_runs management command.

Coverage:
  - Marks old RUNNING runs as LLM_ERROR.
  - Ignores recent RUNNING runs (below threshold).
  - Ignores non-RUNNING runs regardless of age.
  - Dry-run mode reports but does not mutate.
  - --run-ids targets only the specified UUIDs.
"""

from datetime import timedelta

import pytest
from django.core.management import call_command
from django.utils import timezone

from app_modules.ai_pipelines.constants import AIPipelineStatus, AIPipelineType
from app_modules.ai_pipelines.models.pipeline_run import AIPipelineRun


# =============================================================================
# HELPERS
# =============================================================================

def _create_run(*, client_id, user, status=AIPipelineStatus.RUNNING):
    """Create an AIPipelineRun with the minimal required fields."""
    return AIPipelineRun.objects.create(
        client_id=client_id,
        created_by=user,
        updated_by=user,
        status=status,
        pipeline_type=AIPipelineType.TRANSCRIPT_SIGNALS,
        prompt_versions={'system': 'v1'},
        provider='openai',
        model_name='gpt-4o-mini',
        temperature=0.0,
        input_hash='a' * 64,
        sub_calls=[],
        total_tokens_used=0,
        total_duration_ms=0,
        error_message='',
        created_signals_count=0,
    )


def _age_run(run, minutes_ago):
    """Set created_at to `minutes_ago` minutes in the past (bypasses auto_now_add)."""
    past = timezone.now() - timedelta(minutes=minutes_ago)
    AIPipelineRun.objects.filter(id=run.id).update(created_at=past)


# =============================================================================
# TESTS
# =============================================================================

@pytest.mark.django_db
class TestCleanupPipelineRuns:

    def test_cleanup_marks_old_running_as_error(self, tenant_a_id, user_a):
        run = _create_run(client_id=tenant_a_id, user=user_a)
        _age_run(run, minutes_ago=60)

        call_command('cleanup_pipeline_runs')

        run.refresh_from_db()
        assert run.status == AIPipelineStatus.LLM_ERROR
        assert run.error_message != ''

    def test_cleanup_ignores_recent_running(self, tenant_a_id, user_a):
        run = _create_run(client_id=tenant_a_id, user=user_a)
        _age_run(run, minutes_ago=5)

        call_command('cleanup_pipeline_runs')

        run.refresh_from_db()
        assert run.status == AIPipelineStatus.RUNNING

    def test_cleanup_ignores_non_running(self, tenant_a_id, user_a):
        run = _create_run(client_id=tenant_a_id, user=user_a, status=AIPipelineStatus.SUCCESS)
        _age_run(run, minutes_ago=60)

        call_command('cleanup_pipeline_runs')

        run.refresh_from_db()
        assert run.status == AIPipelineStatus.SUCCESS

    def test_cleanup_dry_run_no_changes(self, tenant_a_id, user_a):
        run = _create_run(client_id=tenant_a_id, user=user_a)
        _age_run(run, minutes_ago=60)

        call_command('cleanup_pipeline_runs', '--dry-run')

        run.refresh_from_db()
        assert run.status == AIPipelineStatus.RUNNING

    def test_cleanup_specific_run_ids(self, tenant_a_id, user_a):
        run_target = _create_run(client_id=tenant_a_id, user=user_a)
        run_other = _create_run(client_id=tenant_a_id, user=user_a)
        _age_run(run_target, minutes_ago=60)
        _age_run(run_other, minutes_ago=60)

        call_command('cleanup_pipeline_runs', '--run-ids', str(run_target.id))

        run_target.refresh_from_db()
        run_other.refresh_from_db()
        assert run_target.status == AIPipelineStatus.LLM_ERROR
        assert run_other.status == AIPipelineStatus.RUNNING
