# backend/tests/ai_pipelines/test_pipeline_next_steps.py
"""
Orchestration + integration tests for NextStepsPipeline (Sprint B4).

Covers everything that lives at the pipeline-runner boundary:

  * Single stage runs once -- no multi-stage loop.
  * Prompt structure capture per stage (system + context +
    transcript + TASK header) via FakeProvider, including the
    explicit source_quote-as-JUSTIFICATION rule.
  * PROMPT_VERSIONS registry carries the 3 expected keys.
  * AIPipelineRun audit row records pipeline_type = NEXT_STEPS, sub
    call entry, prompt_versions inventory.
  * Return shape is flat: {'run', 'signals'} (not 'signals_by_stage').
  * Final status derivation:
      * happy path                       -> SUCCESS
      * LLMTimeoutError                  -> TIMEOUT
      * LLMRateLimitError                -> LLM_ERROR
      * LLMAuthError                     -> LLM_ERROR
      * PromptParseError after retry     -> PARSE_ERROR
      * Generic LLMProviderError         -> LLM_ERROR
  * Safety filter applies to NextSteps with the shared module
    (confidence < 0.5 -> drop; is_inferred=True -> drop).
  * Regression: QualificationSignalsPipeline still produces signals
    on a happy-path run (the safety_filter refactor did not break it).

End-to-end persistence assertions on the produced NextStepSignal rows
(field mapping, contact-attribution deferral, due-date parsing) live
in test_next_step_extractor.py at the unit-builder level.
"""

import pytest

from app_modules.ai_pipelines.constants import AIPipelineStatus, AIPipelineType
from app_modules.ai_pipelines.providers.base import (
    LLMAuthError,
    LLMProviderError,
    LLMRateLimitError,
    LLMTimeoutError,
)
from app_modules.signals.models import NextStepSignal

from .conftest import CANNED_REPLIES_HAPPY, CANNED_REPLY_NEXT_STEPS_HAPPY


pytestmark = pytest.mark.django_db


# =============================================================================
# PIPELINE TYPE + PROMPT_VERSIONS REGISTRY
# =============================================================================

class TestNextStepsPipelineRegistry:
    """The new pipeline class declares its identity correctly."""

    def test_pipeline_type_is_next_steps_enum(self):
        from app_modules.ai_pipelines.pipelines.next_steps import NextStepsPipeline
        assert NextStepsPipeline.PIPELINE_TYPE == AIPipelineType.NEXT_STEPS

    def test_prompt_versions_full_inventory(self):
        from app_modules.ai_pipelines.pipelines.next_steps import NextStepsPipeline
        assert set(NextStepsPipeline.PROMPT_VERSIONS.keys()) == {
            'system', 'context', 'next_steps',
        }

    def test_safety_thresholds_match_qualification(self):
        from app_modules.ai_pipelines.pipelines.next_steps import NextStepsPipeline
        assert NextStepsPipeline.CONFIDENCE_MIN == 0.5
        assert NextStepsPipeline.DROP_INFERRED is True


# =============================================================================
# HAPPY PATH (single stage)
# =============================================================================

class TestNextStepsPipelineHappyPath:
    """Single-stage happy path persists one NextStepSignal in PENDING."""

    def test_run_returns_flat_envelope_with_signals_key(
        self, account, activity, user_a, fake_provider, patch_active_provider,
    ):
        """
        Single-stage shape: {'run', 'signals'}. NO 'signals_by_stage'
        key (that pattern is reserved for the multi-stage qualification
        pipeline).
        """
        from app_modules.ai_pipelines.pipelines.next_steps import NextStepsPipeline
        fake_provider.replies = {'next_steps': CANNED_REPLY_NEXT_STEPS_HAPPY}

        result = NextStepsPipeline().run(
            transcript='Discovery call with Acme. CFO asked for a pricing recap.',
            activity=activity,
            user=user_a,
            client_id=account.client_id,
        )

        assert set(result.keys()) == {'run', 'signals'}
        assert result['run'].status == AIPipelineStatus.SUCCESS
        assert len(result['signals']) == 1
        assert isinstance(result['signals'][0], NextStepSignal)

    def test_single_stage_runs_once_only(
        self, account, activity, user_a, fake_provider, patch_active_provider,
    ):
        from app_modules.ai_pipelines.pipelines.next_steps import NextStepsPipeline
        fake_provider.replies = {'next_steps': CANNED_REPLY_NEXT_STEPS_HAPPY}

        NextStepsPipeline().run(
            transcript='Single-stage check transcript.',
            activity=activity,
            user=user_a,
            client_id=account.client_id,
        )

        assert fake_provider.stages_in_order() == ['next_steps']

    def test_empty_signals_reply_yields_success_with_zero_persisted(
        self, account, activity, user_a, fake_provider, patch_active_provider,
    ):
        """
        Empty {"signals": []} from the LLM is the expected "no next-step
        evidence" shape -- must NOT mark the run as failed and must
        persist zero rows.
        """
        from app_modules.ai_pipelines.pipelines.next_steps import NextStepsPipeline
        fake_provider.replies = {'next_steps': '{"signals": []}'}

        result = NextStepsPipeline().run(
            transcript='A short transcript with no next step.',
            activity=activity,
            user=user_a,
            client_id=account.client_id,
        )

        assert result['run'].status == AIPipelineStatus.SUCCESS
        assert result['signals'] == []
        assert NextStepSignal.objects.count() == 0


# =============================================================================
# PROMPT STRUCTURE CAPTURE
# =============================================================================

class TestPromptStructureCapture:
    """Asserts the prompt sent to the provider for the next-steps stage."""

    @pytest.fixture(autouse=True)
    def _run_pipeline(
        self, account, activity, user_a, fake_provider, patch_active_provider,
    ):
        from app_modules.ai_pipelines.pipelines.next_steps import NextStepsPipeline
        fake_provider.replies = {'next_steps': CANNED_REPLY_NEXT_STEPS_HAPPY}

        self._transcript = (
            'Discovery call with Acme. CFO asked for a pricing recap '
            'by mid-December.'
        )
        NextStepsPipeline().run(
            transcript=self._transcript,
            activity=activity,
            user=user_a,
            client_id=account.client_id,
        )
        self._provider = fake_provider

    def test_user_prompt_contains_task_header(self):
        calls = self._provider.calls_for('next_steps')
        assert len(calls) == 1
        assert 'Extract NEXT-STEP signals' in calls[0]['user']

    def test_user_prompt_embeds_transcript_verbatim(self):
        calls = self._provider.calls_for('next_steps')
        assert self._transcript in calls[0]['user']

    def test_system_prompt_is_non_empty_meddpicc_voice(self):
        """Reuses the MEDDPICC system prompt from transcript_signals."""
        calls = self._provider.calls_for('next_steps')
        sys_prompt = calls[0]['system']
        assert sys_prompt.strip()
        assert 'MEDDPICC' in sys_prompt

    def test_temperature_is_zero(self):
        calls = self._provider.calls_for('next_steps')
        assert calls[0]['temperature'] == 0.0

    def test_user_prompt_contains_source_quote_justification_rule(self):
        """
        TD-5 contract enforced AT PROMPT TIME: source_quote is the
        JUSTIFICATION, not a verbatim of the speaker proposing the
        action. The rule must appear in the prompt the LLM actually
        reads.
        """
        calls = self._provider.calls_for('next_steps')
        user_prompt = calls[0]['user']
        # Whitespace-normalised view to tolerate newlines inside the
        # rule wording (the prompt is hand-wrapped; the rule may break
        # across lines).
        normalised = ' '.join(user_prompt.split())
        assert 'JUSTIFICATION' in normalised
        # The rule explicitly distinguishes "evidence" from "act of
        # proposing it" -- match both anchors to catch any future
        # weakening of the wording.
        assert 'EVIDENCE' in normalised
        assert 'NOT a verbatim' in normalised

    def test_user_prompt_contains_concrete_source_quote_example(self):
        """
        The abstract JUSTIFICATION rule is reinforced by a concrete
        EXAMPLE block that shows BOTH the correct shape and a
        counter-example labelled INCORRECT. The example anchors the
        LLM in the difference between "the justification" and "the
        act of proposing", which the abstract wording alone does not
        always disambiguate -- especially when a single speaker's
        turn contains both the motivation and the proposal.

        Asserting on two distinct anchors:
          * "15 hours per week" -- the verbatim justification quote.
          * "INCORRECT"         -- the counter-example label.

        Removing either side of the contrast (the positive example or
        the negative one) weakens the contract. Catching such a
        regression at the prompt-capture level is the whole point of
        the FakeProvider payload capture.
        """
        calls = self._provider.calls_for('next_steps')
        user_prompt = calls[0]['user']
        assert 'EXAMPLE' in user_prompt
        # Positive example anchor (the justification verbatim).
        assert '15 hours per week' in user_prompt
        # Negative example anchor (counter-example label).
        assert 'INCORRECT' in user_prompt

    def test_user_prompt_carries_activity_type_taxonomy(self):
        """
        The ACTIVITY TYPE TAXONOMY block must list every ActivityType
        value the LLM is allowed to emit. Future enum additions should
        propagate automatically (single source of truth from
        app_modules.activities.constants).
        """
        from app_modules.activities.constants import ActivityType
        user_prompt = self._provider.calls_for('next_steps')[0]['user']
        assert 'ACTIVITY TYPE TAXONOMY' in user_prompt
        for value in ActivityType.values:
            assert f'"{value}"' in user_prompt

    def test_user_prompt_skips_taxonomy_block(self):
        """
        NextStepSignal has no canonical taxonomy (no `what` /
        `dimension`). The context layer must skip the
        "CANONICAL TAXONOMY" block (used by qualification stages).
        """
        user_prompt = self._provider.calls_for('next_steps')[0]['user']
        assert 'CANONICAL TAXONOMY' not in user_prompt

    def test_user_prompt_skips_techcatalog_block(self):
        """NextSteps does not consume the TechCatalog."""
        user_prompt = self._provider.calls_for('next_steps')[0]['user']
        assert 'TECH CATALOG' not in user_prompt


# =============================================================================
# AUDIT ROW
# =============================================================================

class TestAIPipelineRunAuditRow:
    """The audit row captures pipeline_type, prompt_versions, sub_calls."""

    def test_audit_row_pipeline_type_is_next_steps(
        self, account, activity, user_a, fake_provider, patch_active_provider,
    ):
        from app_modules.ai_pipelines.pipelines.next_steps import NextStepsPipeline
        fake_provider.replies = {'next_steps': CANNED_REPLY_NEXT_STEPS_HAPPY}

        result = NextStepsPipeline().run(
            transcript='Audit row test transcript.',
            activity=activity,
            user=user_a,
            client_id=account.client_id,
        )
        assert result['run'].pipeline_type == AIPipelineType.NEXT_STEPS

    def test_audit_row_prompt_versions_contain_next_steps(
        self, account, activity, user_a, fake_provider, patch_active_provider,
    ):
        from app_modules.ai_pipelines.pipelines.next_steps import NextStepsPipeline
        fake_provider.replies = {'next_steps': CANNED_REPLY_NEXT_STEPS_HAPPY}

        result = NextStepsPipeline().run(
            transcript='Prompt-versions test transcript.',
            activity=activity,
            user=user_a,
            client_id=account.client_id,
        )
        assert 'next_steps' in result['run'].prompt_versions

    def test_audit_row_logs_single_sub_call_entry(
        self, account, activity, user_a, fake_provider, patch_active_provider,
    ):
        from app_modules.ai_pipelines.pipelines.next_steps import NextStepsPipeline
        fake_provider.replies = {'next_steps': CANNED_REPLY_NEXT_STEPS_HAPPY}

        result = NextStepsPipeline().run(
            transcript='Sub-call audit test transcript.',
            activity=activity,
            user=user_a,
            client_id=account.client_id,
        )
        sub_calls = result['run'].sub_calls
        assert len(sub_calls) == 1
        assert sub_calls[0]['stage'] == 'next_steps'
        assert sub_calls[0]['error'] is None

    def test_input_hash_matches_for_same_transcript(
        self, account, activity, user_a, fake_provider, patch_active_provider,
    ):
        """
        Same transcript -> same sha256 input_hash on the audit row.
        Two runs (with their own AIPipelineRun) carry the SAME hash,
        which is the substrate for the (deferred) view-layer dedup
        once it disambiguates by pipeline_type (TD-8).
        """
        from app_modules.ai_pipelines.pipelines.next_steps import NextStepsPipeline
        fake_provider.replies = {'next_steps': CANNED_REPLY_NEXT_STEPS_HAPPY}

        transcript = 'Deterministic input-hash test transcript.'
        result_1 = NextStepsPipeline().run(
            transcript=transcript, activity=activity,
            user=user_a, client_id=account.client_id,
        )
        result_2 = NextStepsPipeline().run(
            transcript=transcript, activity=activity,
            user=user_a, client_id=account.client_id,
        )
        assert result_1['run'].input_hash == result_2['run'].input_hash
        assert result_1['run'].id != result_2['run'].id


# =============================================================================
# FAILURE MODES
# =============================================================================

class TestNextStepsPipelineFailureModes:
    """Each exception path maps to the right AIPipelineStatus."""

    @pytest.mark.parametrize(
        'exception_cls,expected_status,label_in_error',
        [
            (LLMTimeoutError,   AIPipelineStatus.TIMEOUT,     'timeout'),
            (LLMRateLimitError, AIPipelineStatus.LLM_ERROR,   'rate_limit'),
            (LLMAuthError,      AIPipelineStatus.LLM_ERROR,   'auth_error'),
            (LLMProviderError,  AIPipelineStatus.LLM_ERROR,   'provider_error'),
        ],
    )
    def test_exception_maps_to_status(
        self, account, activity, user_a, fake_provider, patch_active_provider,
        exception_cls, expected_status, label_in_error,
    ):
        from app_modules.ai_pipelines.pipelines.next_steps import NextStepsPipeline
        fake_provider.raise_per_stage = {'next_steps': exception_cls('boom')}

        result = NextStepsPipeline().run(
            transcript='Failure mode test transcript.',
            activity=activity,
            user=user_a,
            client_id=account.client_id,
        )
        assert result['run'].status == expected_status
        assert result['signals'] == []
        sub_call = result['run'].sub_calls[0]
        assert label_in_error in sub_call['error']

    def test_parse_error_yields_parse_error_status(
        self, account, activity, user_a, fake_provider, patch_active_provider,
    ):
        """
        Two malformed replies in a row trigger PromptParseError after
        the corrective retry (BasePipeline._call_llm policy). The
        pipeline finalises as PARSE_ERROR.
        """
        from app_modules.ai_pipelines.pipelines.next_steps import NextStepsPipeline
        # Return non-JSON for both attempts. _call_llm retries once,
        # then propagates PromptParseError.
        fake_provider.replies = {'next_steps': 'not a valid JSON payload at all'}

        result = NextStepsPipeline().run(
            transcript='Parse-error test transcript.',
            activity=activity,
            user=user_a,
            client_id=account.client_id,
        )
        assert result['run'].status == AIPipelineStatus.PARSE_ERROR
        assert result['signals'] == []


# =============================================================================
# SAFETY FILTER
# =============================================================================

class TestSafetyFilterAppliesToNextSteps:
    """Shared safety filter must drop weak signals at the NextSteps stage."""

    def test_low_confidence_signal_dropped(
        self, account, activity, user_a, fake_provider, patch_active_provider,
    ):
        from app_modules.ai_pipelines.pipelines.next_steps import NextStepsPipeline
        fake_provider.replies = {
            'next_steps': (
                '{"signals": ['
                '{"suggested_title": "low-conf next step", '
                '"suggested_activity_type": "EMAIL", '
                '"suggested_due_date": null, '
                '"source_quote": "the CFO asked for a recap", '
                '"confidence": 0.3, '
                '"is_inferred": false}'
                ']}'
            ),
        }

        result = NextStepsPipeline().run(
            transcript='Low-confidence drop test transcript.',
            activity=activity,
            user=user_a,
            client_id=account.client_id,
        )
        assert result['signals'] == []
        sub = result['run'].sub_calls[0]
        assert sub['dropped_by_safety_filter'] == 1

    def test_inferred_signal_dropped(
        self, account, activity, user_a, fake_provider, patch_active_provider,
    ):
        from app_modules.ai_pipelines.pipelines.next_steps import NextStepsPipeline
        fake_provider.replies = {
            'next_steps': (
                '{"signals": ['
                '{"suggested_title": "inferred next step", '
                '"suggested_activity_type": "CALL", '
                '"suggested_due_date": null, '
                '"source_quote": "the discussion drifted to competitors", '
                '"confidence": 0.9, '
                '"is_inferred": true}'
                ']}'
            ),
        }

        result = NextStepsPipeline().run(
            transcript='Inferred drop test transcript.',
            activity=activity,
            user=user_a,
            client_id=account.client_id,
        )
        assert result['signals'] == []
        sub = result['run'].sub_calls[0]
        assert sub['dropped_by_safety_filter'] == 1


# =============================================================================
# REGRESSION - QualificationSignalsPipeline still works
# =============================================================================

class TestQualificationRegression:
    """
    Sub-step 2 of Sprint B4 refactored TranscriptSignalExtractor's
    safety filter to delegate to the shared services/safety_filter.py
    module. This test re-exercises a full 5-stage Qualification run to
    confirm no regression.
    """

    def test_qualification_pipeline_still_persists_one_signal_per_stage(
        self, account, activity, user_a, fake_provider, patch_active_provider,
    ):
        from app_modules.ai_pipelines.pipelines.transcript_signals import (
            QualificationSignalsPipeline,
        )
        fake_provider.replies = dict(CANNED_REPLIES_HAPPY)

        result = QualificationSignalsPipeline().run(
            transcript='Acme reports take 3 weeks. We use Salesforce. No Q4 budget.',
            activity=activity,
            user=user_a,
            client_id=account.client_id,
        )
        assert result['run'].status == AIPipelineStatus.SUCCESS
        # Each stage persisted exactly 1 signal in the happy-path setup.
        for stage in ('pain', 'objective', 'impact', 'techstack', 'blocker'):
            assert len(result['signals_by_stage'][stage]) == 1, (
                f'Qualification stage {stage} regressed after the '
                'safety_filter refactor.'
            )
