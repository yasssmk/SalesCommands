# backend/tests/ai_pipelines/test_pipeline_thresholds_constants.py
"""
S5 — the safety-filter thresholds of the LLM pipelines live in ONE place,
ai_pipelines/constants.py (project rule: every business value lives in the
module's constants.py), and the pipelines read them from there.

  * PIPELINE_CONFIDENCE_MIN / PIPELINE_DROP_INFERRED — one entry per
    pipeline type (mirror of PIPELINE_TEMPERATURES), current values pinned.
  * TRANSCRIPT_SIGNALS no longer drops is_inferred (TD-279 C1, every stage,
    so the People exemption set is gone); NEXT_STEPS keeps its own policy.
  * The pipeline class attributes ARE these constants (same objects), so the
    `self.X` reads and any subclass override keep working unchanged.
"""

from app_modules.ai_pipelines.constants import (
    AIPipelineType,
    PIPELINE_CONFIDENCE_MIN,
    PIPELINE_DROP_INFERRED,
)
from app_modules.ai_pipelines.pipelines.next_steps import NextStepsPipeline
from app_modules.ai_pipelines.pipelines.transcript_signals import (
    QualificationSignalsPipeline,
)


class TestThresholdConstantsValues:

    def test_confidence_min_per_pipeline(self):
        assert PIPELINE_CONFIDENCE_MIN == {
            AIPipelineType.TRANSCRIPT_SIGNALS: 0.5,
            AIPipelineType.NEXT_STEPS: 0.5,
        }

    def test_drop_inferred_per_pipeline(self):
        assert PIPELINE_DROP_INFERRED == {
            AIPipelineType.TRANSCRIPT_SIGNALS: False,
            AIPipelineType.NEXT_STEPS: True,
        }


class TestPipelinesReadTheConstants:

    def test_qualification_pipeline_reads_its_constants(self):
        assert QualificationSignalsPipeline.CONFIDENCE_MIN == (
            PIPELINE_CONFIDENCE_MIN[AIPipelineType.TRANSCRIPT_SIGNALS]
        )
        assert QualificationSignalsPipeline.DROP_INFERRED is (
            PIPELINE_DROP_INFERRED[AIPipelineType.TRANSCRIPT_SIGNALS]
        )

    def test_next_steps_pipeline_reads_its_constants(self):
        assert NextStepsPipeline.CONFIDENCE_MIN == (
            PIPELINE_CONFIDENCE_MIN[AIPipelineType.NEXT_STEPS]
        )
        assert NextStepsPipeline.DROP_INFERRED is (
            PIPELINE_DROP_INFERRED[AIPipelineType.NEXT_STEPS]
        )
