# backend/tests/ai_pipelines/test_inferred_signals_kept.py
"""
TD-279 C1 (PO decision, audit "atelier business case"): a signal the LLM
self-declares `is_inferred: true` is KEPT for EVERY transcript_signals stage
(like People since S1). Only the confidence floor
(PIPELINE_CONFIDENCE_MIN, 0.5) still drops a weak deduction.

Through the REAL pipeline path (FakeProvider -> persist_stage):
  * Impact / Blocker / TechStack, is_inferred=true, confidence 0.6 -> persisted;
  * témoin: the same with confidence 0.4 -> still dropped.
"""

import json

import pytest

from app_modules.ai_pipelines.constants import (
    AIPipelineType,
    PIPELINE_CONFIDENCE_MIN,
)


pytestmark = pytest.mark.django_db

KEPT = PIPELINE_CONFIDENCE_MIN[AIPipelineType.TRANSCRIPT_SIGNALS] + 0.1
DROPPED = PIPELINE_CONFIDENCE_MIN[AIPipelineType.TRANSCRIPT_SIGNALS] - 0.1


def _replies(confidence):
    epistemic = {'confidence': confidence, 'is_inferred': True}
    return {
        'pain_impact': json.dumps({'pains': [], 'impacts': [{
            'what': 'OPS', 'dimension': 'TIME', 'impact_type': 'TIME',
            'scope_level': 'BUSINESS', 'target_departments': [],
            'summary': 'About two full-time equivalents lost on data entry',
            'source_quote': 'Twenty reps at four hours a week each',
            **epistemic,
        }]}),
        'blocker': json.dumps({'signals': [{
            'summary': 'Adoption by the field reps is not secured',
            'source_quote': 'If the reps do not use it, it is useless',
            'raised_by_name': None,
            **epistemic,
        }]}),
        'techstack': json.dumps({'signals': [{
            'tech_name': 'Pipedrive', 'usage_scope': 'UNKNOWN',
            'usage_departments': [],
            'source_quote': 'the pipeline lives in Pipedrive I believe',
            **epistemic,
        }]}),
    }


def _run(account, activity, user_a, fake_provider, confidence):
    from app_modules.ai_pipelines.pipelines.transcript_signals import (
        QualificationSignalsPipeline,
    )
    fake_provider.replies = _replies(confidence)
    return QualificationSignalsPipeline().run(
        transcript='A transcript for the inferred-signals test.',
        activity=activity, user=user_a, client_id=account.client_id,
    )['signals_by_stage']


class TestInferredSignalsKept:

    @pytest.mark.parametrize('stage', ['impact', 'blocker', 'techstack'])
    def test_inferred_signal_above_the_floor_is_persisted(
        self, stage, account, activity, user_a, fake_provider, patch_active_provider,
    ):
        stages = _run(account, activity, user_a, fake_provider, KEPT)
        [signal] = stages[stage]
        signal.refresh_from_db()
        assert signal.is_inferred is True
        assert signal.confidence == pytest.approx(KEPT)

    @pytest.mark.parametrize('stage', ['impact', 'blocker', 'techstack'])
    def test_temoin_inferred_signal_below_the_floor_is_still_dropped(
        self, stage, account, activity, user_a, fake_provider, patch_active_provider,
    ):
        stages = _run(account, activity, user_a, fake_provider, DROPPED)
        assert stages[stage] == []
