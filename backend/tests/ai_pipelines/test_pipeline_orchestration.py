# backend/tests/ai_pipelines/test_pipeline_orchestration.py
"""
Orchestration-level tests for QualificationSignalsPipeline (Sprint B3).

Covers everything that lives at the pipeline-runner boundary:

  * 5 stages run in the canonical order
    (pain -> objective -> impact -> techstack -> blocker).
  * Prompt structure per stage: system + context + transcript marker
    + stage-specific TASK header. Driven via FakeProvider.calls which
    captures every kwarg passed to provider.call().
  * AIPipelineRun.PROMPT_VERSIONS contains all 6 keys, including the
    new 'blocker' entry.
  * Final status derivation:
      * all 5 stages succeed -> SUCCESS
      * any stage raises -> PARTIAL (provided at least one succeeded)
  * Safety filter still applies to the Blocker stage:
      * confidence < 0.5 -> drop
      * is_inferred = True -> drop
  * Back-compat alias TranscriptSignalsPipeline resolves to the same
    class as QualificationSignalsPipeline.

Regression coverage for the 4 pre-existing stages lives in
test_pipeline_blocker_stage.py (which exercises a full 5-stage run on
canned happy-path replies for all stages including blocker).
"""

import pytest

from app_modules.ai_pipelines.constants import AIPipelineStatus, AIPipelineType
from app_modules.ai_pipelines.providers.base import LLMTimeoutError
from app_modules.signals.models import BlockerSignal

from .conftest import CANNED_REPLIES_HAPPY


pytestmark = pytest.mark.django_db


# =============================================================================
# CLASS RENAME + BACK-COMPAT ALIAS
# =============================================================================

class TestQualificationPipelineNaming:
    """The class was renamed in B3; the legacy name must still resolve."""

    def test_qualification_pipeline_is_default_class(self):
        from app_modules.ai_pipelines.pipelines.transcript_signals import (
            QualificationSignalsPipeline,
        )
        assert QualificationSignalsPipeline.__name__ == 'QualificationSignalsPipeline'

    def test_transcript_signals_pipeline_alias_resolves_to_same_class(self):
        from app_modules.ai_pipelines.pipelines.transcript_signals import (
            QualificationSignalsPipeline,
            TranscriptSignalsPipeline,
        )
        # The legacy name is preserved as an alias -- identity assertion
        # ensures both names point at the exact same class object.
        assert TranscriptSignalsPipeline is QualificationSignalsPipeline


# =============================================================================
# PROMPT VERSIONS REGISTRY
# =============================================================================

class TestPromptVersionsRegistry:
    """PROMPT_VERSIONS gains a `blocker` entry in B3."""

    def test_prompt_versions_contains_blocker_entry(self):
        from app_modules.ai_pipelines.pipelines.transcript_signals import (
            QualificationSignalsPipeline,
        )
        assert 'blocker' in QualificationSignalsPipeline.PROMPT_VERSIONS

    def test_prompt_versions_full_inventory(self):
        from app_modules.ai_pipelines.pipelines.transcript_signals import (
            QualificationSignalsPipeline,
        )
        # All 6 keys must be present (system + context + 5 stage versions).
        # Use a set comparison to keep the assertion order-agnostic.
        assert set(QualificationSignalsPipeline.PROMPT_VERSIONS.keys()) == {
            'system', 'context', 'pain', 'objective', 'impact',
            'techstack', 'blocker',
        }


# =============================================================================
# STAGE ORDER (HAPPY PATH)
# =============================================================================

class TestPipelineStageOrder:
    """The 5 stages must run in the canonical order."""

    def test_five_stages_run_in_canonical_order(
        self, account, activity, user_a, fake_provider, patch_active_provider,
    ):
        from app_modules.ai_pipelines.pipelines.transcript_signals import (
            QualificationSignalsPipeline,
        )
        # Configure happy replies for all 5 stages so each stage persists
        # 1 signal -- baseline scenario for ordering assertions.
        fake_provider.replies = dict(CANNED_REPLIES_HAPPY)

        result = QualificationSignalsPipeline().run(
            transcript='Acme reporting takes 3 weeks. We use Salesforce.',
            activity=activity,
            user=user_a,
            client_id=account.client_id,
        )

        assert fake_provider.stages_in_order() == [
            'pain', 'objective', 'impact', 'techstack', 'blocker',
        ]
        assert result['run'].status == AIPipelineStatus.SUCCESS


# =============================================================================
# PROMPT STRUCTURE PER STAGE (captured payloads)
# =============================================================================

class TestPromptStructurePerStage:
    """
    Asserts the structure of every prompt sent to the provider, per stage.

    The FakeProvider captures the full kwargs of each call(). This test
    pack verifies (a) the system prompt is non-empty for every stage,
    (b) the user prompt embeds the transcript verbatim, (c) the user
    prompt carries the stage-specific TASK header, (d) the temperature
    is what the pipeline declared. Structural drift on any of these
    (e.g. a refactor that drops the context layer) will fail loudly
    here.
    """

    @pytest.fixture(autouse=True)
    def _run_full_pipeline(
        self, account, activity, user_a, fake_provider, patch_active_provider,
    ):
        """Run the pipeline once with happy replies so all 5 stages fire."""
        from app_modules.ai_pipelines.pipelines.transcript_signals import (
            QualificationSignalsPipeline,
        )
        fake_provider.replies = dict(CANNED_REPLIES_HAPPY)

        self._transcript = 'Acme reports take 3 weeks. We use Salesforce.'
        QualificationSignalsPipeline().run(
            transcript=self._transcript,
            activity=activity,
            user=user_a,
            client_id=account.client_id,
        )
        self._provider = fake_provider

    @pytest.mark.parametrize(
        'stage,expected_marker',
        [
            ('pain',       'Extract PAIN signals'),
            ('objective',  'Extract OBJECTIVE signals'),
            ('impact',     'Extract IMPACT signals'),
            ('techstack',  'Extract TECH STACK signals'),
            ('blocker',    'Extract BLOCKER signals'),
        ],
    )
    def test_user_prompt_contains_stage_task_header(self, stage, expected_marker):
        calls = self._provider.calls_for(stage)
        assert len(calls) == 1
        assert expected_marker in calls[0]['user']

    @pytest.mark.parametrize(
        'stage',
        ['pain', 'objective', 'impact', 'techstack', 'blocker'],
    )
    def test_user_prompt_embeds_transcript_verbatim(self, stage):
        calls = self._provider.calls_for(stage)
        assert self._transcript in calls[0]['user']

    @pytest.mark.parametrize(
        'stage',
        ['pain', 'objective', 'impact', 'techstack', 'blocker'],
    )
    def test_system_prompt_is_non_empty(self, stage):
        calls = self._provider.calls_for(stage)
        assert calls[0]['system'].strip(), (
            f'System prompt must be non-empty for stage {stage!r}.'
        )

    @pytest.mark.parametrize(
        'stage',
        ['pain', 'objective', 'impact', 'techstack', 'blocker'],
    )
    def test_temperature_is_zero_for_extraction(self, stage):
        calls = self._provider.calls_for(stage)
        # The pipeline declares TEMPERATURE = 0.0 for deterministic
        # extraction. Any drift here would change LLM behaviour and is
        # worth catching.
        assert calls[0]['temperature'] == 0.0

    def test_blocker_user_prompt_contains_verbatim_rule(self):
        """
        TD-6 / Q6 contract: the Blocker prompt MUST instruct the LLM
        that source_quote is a verbatim utterance. This rule is the
        single source of truth that the LLM actually reads (docstrings
        are humans-only).
        """
        calls = self._provider.calls_for('blocker')
        # Match the actual rule wording from blocker_v1.py without
        # over-coupling to exact phrasing. Two anchor substrings.
        user_prompt = calls[0]['user']
        assert 'VERBATIM' in user_prompt
        assert 'source_quote' in user_prompt
        assert 'paraphrase' in user_prompt.lower()

    def test_blocker_user_prompt_skips_taxonomy_block(self):
        """
        BlockerSignal has no canonical taxonomy. The context layer must
        skip the TAXONOMY block entirely for the blocker stage; that
        section's header literal must NOT appear in the blocker user
        prompt. The other stages still expose it.
        """
        blocker_user = self._provider.calls_for('blocker')[0]['user']
        pain_user    = self._provider.calls_for('pain')[0]['user']

        assert 'CANONICAL TAXONOMY' not in blocker_user
        assert 'CANONICAL TAXONOMY' in pain_user  # baseline / regression


# =============================================================================
# AUDIT ROW
# =============================================================================

class TestAIPipelineRunAuditRow:
    """The audit row captures the new 'blocker' entry."""

    def test_audit_row_pipeline_type_remains_transcript_signals(
        self, account, activity, user_a, fake_provider, patch_active_provider,
    ):
        """
        Sprint B3 decision: the AIPipelineType.TRANSCRIPT_SIGNALS enum
        value is intentionally NOT renamed (historical runs preserved,
        no data migration). The audit row must reflect that.
        """
        from app_modules.ai_pipelines.pipelines.transcript_signals import (
            QualificationSignalsPipeline,
        )
        result = QualificationSignalsPipeline().run(
            transcript='A short conversation transcript for audit row test.',
            activity=activity,
            user=user_a,
            client_id=account.client_id,
        )
        assert result['run'].pipeline_type == AIPipelineType.TRANSCRIPT_SIGNALS

    def test_audit_row_prompt_versions_contain_blocker(
        self, account, activity, user_a, fake_provider, patch_active_provider,
    ):
        from app_modules.ai_pipelines.pipelines.transcript_signals import (
            QualificationSignalsPipeline,
        )
        result = QualificationSignalsPipeline().run(
            transcript='A short conversation transcript for prompt-versions test.',
            activity=activity,
            user=user_a,
            client_id=account.client_id,
        )
        assert 'blocker' in result['run'].prompt_versions

    def test_audit_row_logs_blocker_sub_call(
        self, account, activity, user_a, fake_provider, patch_active_provider,
    ):
        from app_modules.ai_pipelines.pipelines.transcript_signals import (
            QualificationSignalsPipeline,
        )
        result = QualificationSignalsPipeline().run(
            transcript='A short conversation transcript for sub-call audit.',
            activity=activity,
            user=user_a,
            client_id=account.client_id,
        )
        sub_call_stages = [c['stage'] for c in result['run'].sub_calls]
        assert sub_call_stages == [
            'pain', 'objective', 'impact', 'techstack', 'blocker',
        ]


# =============================================================================
# PARTIAL STATUS WHEN BLOCKER STAGE FAILS
# =============================================================================

class TestPipelinePartialOnBlockerFailure:
    """
    A failure of the Blocker stage must leave the 4 prior stages
    persisted and finalise the run as PARTIAL. Cohérent with the
    pattern existing for the 4 prior stages.
    """

    def test_blocker_timeout_yields_partial_run_with_other_stages_persisted(
        self, account, activity, user_a, fake_provider, patch_active_provider,
    ):
        from app_modules.ai_pipelines.pipelines.transcript_signals import (
            QualificationSignalsPipeline,
        )

        # 4 prior stages return happy replies; Blocker raises a timeout.
        fake_provider.replies = {
            k: v for k, v in CANNED_REPLIES_HAPPY.items() if k != 'blocker'
        }
        fake_provider.raise_per_stage = {
            'blocker': LLMTimeoutError('blocker stage timed out'),
        }

        result = QualificationSignalsPipeline().run(
            transcript='Acme reports take 3 weeks. We use Salesforce.',
            activity=activity,
            user=user_a,
            client_id=account.client_id,
        )

        run = result['run']
        assert run.status == AIPipelineStatus.PARTIAL

        # The 4 prior stages each persisted 1 signal.
        assert len(result['signals_by_stage']['pain'])      == 1
        assert len(result['signals_by_stage']['objective']) == 1
        assert len(result['signals_by_stage']['impact'])    == 1
        assert len(result['signals_by_stage']['techstack']) == 1

        # The Blocker stage failed -- 0 signals, 0 BlockerSignal rows in DB.
        assert result['signals_by_stage']['blocker'] == []
        assert BlockerSignal.objects.count() == 0

        # The sub_calls entry for blocker records the timeout.
        blocker_sub = next(
            c for c in run.sub_calls if c['stage'] == 'blocker'
        )
        assert blocker_sub['error'] is not None
        assert 'timeout' in blocker_sub['error']


# =============================================================================
# SAFETY FILTER ON BLOCKER
# =============================================================================

class TestSafetyFilterAppliesToBlocker:
    """
    CONFIDENCE_MIN = 0.5 and DROP_INFERRED = True must apply to the
    Blocker stage with the same rigor as the 4 prior stages.
    """

    def test_blocker_low_confidence_signal_dropped(
        self, account, activity, user_a, fake_provider, patch_active_provider,
    ):
        from app_modules.ai_pipelines.pipelines.transcript_signals import (
            QualificationSignalsPipeline,
        )
        fake_provider.replies = {
            'blocker': (
                '{"signals": ['
                '{"summary": "low-confidence blocker", '
                '"source_quote": "maybe a budget issue", '
                '"confidence": 0.3, '
                '"is_inferred": false}'
                ']}'
            ),
        }

        result = QualificationSignalsPipeline().run(
            transcript='A short conversation transcript for low-conf drop test.',
            activity=activity,
            user=user_a,
            client_id=account.client_id,
        )
        assert result['signals_by_stage']['blocker'] == []
        assert BlockerSignal.objects.count() == 0

        # And the dropped count is logged in the audit row.
        blocker_sub = next(
            c for c in result['run'].sub_calls if c['stage'] == 'blocker'
        )
        assert blocker_sub['dropped_by_safety_filter'] == 1

    def test_blocker_inferred_signal_dropped(
        self, account, activity, user_a, fake_provider, patch_active_provider,
    ):
        from app_modules.ai_pipelines.pipelines.transcript_signals import (
            QualificationSignalsPipeline,
        )
        fake_provider.replies = {
            'blocker': (
                '{"signals": ['
                '{"summary": "inferred blocker", '
                '"source_quote": "hinted at a competing project", '
                '"confidence": 0.9, '
                '"is_inferred": true}'
                ']}'
            ),
        }

        result = QualificationSignalsPipeline().run(
            transcript='A short conversation transcript for inferred drop test.',
            activity=activity,
            user=user_a,
            client_id=account.client_id,
        )
        assert result['signals_by_stage']['blocker'] == []
        assert BlockerSignal.objects.count() == 0

        blocker_sub = next(
            c for c in result['run'].sub_calls if c['stage'] == 'blocker'
        )
        assert blocker_sub['dropped_by_safety_filter'] == 1
