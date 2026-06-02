# backend/tests/ai_pipelines/test_pipeline_extractor_blocker.py
"""
Unit tests for TranscriptSignalExtractor._build_blocker_data (Sprint B3).

The Blocker stage is the only new stage added by Sprint B3. Its
SignalManager.create() data-dict builder lives in
services/transcript_signal_extractor.py and is exercised end-to-end by
test_pipeline_blocker_stage.py. This file zooms in on the BUILDER
itself, with no LLM provider involved, to assert:

  * Required fields present -> well-formed dict ready for
    SignalManager.create().
  * Missing required field -> returns None (drop signal).
  * Empty / whitespace-only required field -> returns None.
  * Optional fields default to the documented values.
  * Safety filter (confidence + is_inferred) is independent of the
    builder -- but persist_stage chains both and the integration is
    asserted here too on a minimal raw_signals input.
  * Stage dispatcher routes 'blocker' -> _build_blocker_data.

Why unit-level coverage matters
-------------------------------
The integration tests in test_pipeline_blocker_stage.py exercise the
happy path and one variant per scenario. They are slow (full pipeline
run with provider mock) and would obscure regression diagnostics when
a builder-side rule changes. The unit tests here run in milliseconds
against the builder directly and pinpoint the failure inside the
builder when one rule drifts.
"""

import pytest

from app_modules.ai_pipelines.services.transcript_signal_extractor import (
    TranscriptSignalExtractor,
)
from app_modules.signals.constants import SignalSource, SignalStatus
from app_modules.signals.models import BlockerSignal


pytestmark = pytest.mark.django_db


# =============================================================================
# BUILDER -- happy path
# =============================================================================

class TestBuildBlockerDataHappyPath:
    """A well-formed raw LLM signal yields a complete data dict."""

    def test_builder_returns_complete_data_dict(self, account, activity):
        extractor = TranscriptSignalExtractor()
        raw = {
            'summary':      'No Q4 budget',
            'source_quote': 'We have no budget for this in Q4',
            'confidence':   0.85,
            'is_inferred':  False,
        }
        data = extractor._build_blocker_data(raw, activity)

        assert data['signal_type']     == 'blocker'
        assert data['account']         == account
        assert data['source_activity'] == activity
        assert data['source']          == SignalSource.LLM_EXTRACTED
        assert data['status']          == SignalStatus.PENDING
        assert data['summary']         == 'No Q4 budget'
        assert data['source_quote']    == 'We have no budget for this in Q4'
        assert data['confidence']      == pytest.approx(0.85)
        assert data['is_inferred']     is False
        # contact attribution deferred to validation UI -- TD-6. The
        # builder must not set the field (model default = None).
        assert 'contact' not in data


# =============================================================================
# BUILDER -- defensive drops
# =============================================================================

class TestBuildBlockerDataDefensiveDrops:
    """Malformed LLM payloads return None so the safety net counts them as drops."""

    def test_builder_drops_when_summary_missing(self, activity):
        extractor = TranscriptSignalExtractor()
        raw = {
            'source_quote': 'We have no budget for this in Q4',
            'confidence':   0.85,
            'is_inferred':  False,
        }
        assert extractor._build_blocker_data(raw, activity) is None

    def test_builder_drops_when_source_quote_missing(self, activity):
        extractor = TranscriptSignalExtractor()
        raw = {
            'summary':     'No Q4 budget',
            'confidence':  0.85,
            'is_inferred': False,
        }
        assert extractor._build_blocker_data(raw, activity) is None

    def test_builder_drops_when_summary_empty_whitespace(self, activity):
        extractor = TranscriptSignalExtractor()
        raw = {
            'summary':      '   ',
            'source_quote': 'We have no budget for this in Q4',
            'confidence':   0.85,
            'is_inferred':  False,
        }
        assert extractor._build_blocker_data(raw, activity) is None

    def test_builder_drops_when_source_quote_empty_whitespace(self, activity):
        extractor = TranscriptSignalExtractor()
        raw = {
            'summary':      'No Q4 budget',
            'source_quote': '',
            'confidence':   0.85,
            'is_inferred':  False,
        }
        assert extractor._build_blocker_data(raw, activity) is None

    def test_builder_drops_when_summary_is_none(self, activity):
        extractor = TranscriptSignalExtractor()
        raw = {
            'summary':      None,
            'source_quote': 'We have no budget for this in Q4',
            'confidence':   0.85,
            'is_inferred':  False,
        }
        assert extractor._build_blocker_data(raw, activity) is None


# =============================================================================
# BUILDER -- defaults
# =============================================================================

class TestBuildBlockerDataDefaults:
    """Optional fields get safe defaults."""

    def test_builder_treats_missing_is_inferred_as_false(self, activity):
        extractor = TranscriptSignalExtractor()
        raw = {
            'summary':      'No Q4 budget',
            'source_quote': 'We have no budget for this in Q4',
            'confidence':   0.85,
        }
        data = extractor._build_blocker_data(raw, activity)
        assert data['is_inferred'] is False

    def test_builder_safe_floats_missing_confidence_to_zero(self, activity):
        """
        _safe_float defaults to 0.0 when confidence is missing or
        non-numeric. The safety filter applied UPSTREAM will drop the
        signal (0.0 < CONFIDENCE_MIN=0.5), but the builder itself
        must not crash on the missing key -- ensures the builder is
        robust enough for the safety filter to do its job.
        """
        extractor = TranscriptSignalExtractor()
        raw = {
            'summary':      'No Q4 budget',
            'source_quote': 'We have no budget for this in Q4',
            # confidence missing
        }
        data = extractor._build_blocker_data(raw, activity)
        assert data['confidence'] == 0.0


# =============================================================================
# DISPATCHER ROUTING
# =============================================================================

class TestBuildSignalDataDispatcherRoutesBlocker:
    """_build_signal_data must route stage='blocker' to _build_blocker_data."""

    def test_dispatcher_routes_blocker_stage_to_builder(self, account, activity):
        extractor = TranscriptSignalExtractor()
        raw = {
            'summary':      'No Q4 budget',
            'source_quote': 'We have no budget for this in Q4',
            'confidence':   0.85,
            'is_inferred':  False,
        }
        data = extractor._build_signal_data(
            stage='blocker',
            raw=raw,
            activity=activity,
            client_id=account.client_id,
        )
        assert data is not None
        assert data['signal_type'] == 'blocker'


# =============================================================================
# INTEGRATION via persist_stage
# =============================================================================

class TestPersistStageBlocker:
    """
    persist_stage(stage='blocker', ...) is the integration surface that
    the pipeline orchestrator actually calls. Asserts the safety filter
    + builder chain produce the expected persisted rows + dropped count.
    """

    def test_persist_stage_persists_blocker_and_counts_drops(
        self, account, activity, user_a,
    ):
        extractor = TranscriptSignalExtractor()
        raw_signals = [
            # Should persist.
            {
                'summary':      'No Q4 budget',
                'source_quote': 'We have no budget for this in Q4',
                'confidence':   0.85,
                'is_inferred':  False,
            },
            # Dropped by safety filter (confidence < 0.5).
            {
                'summary':      'low-conf blocker',
                'source_quote': 'maybe a budget issue',
                'confidence':   0.3,
                'is_inferred':  False,
            },
            # Dropped by safety filter (is_inferred=True).
            {
                'summary':      'inferred blocker',
                'source_quote': 'hinted at a competing project',
                'confidence':   0.9,
                'is_inferred':  True,
            },
            # Dropped by builder (missing source_quote).
            {
                'summary':     'malformed blocker',
                'confidence':  0.9,
                'is_inferred': False,
            },
        ]

        persisted, dropped = extractor.persist_stage(
            stage='blocker',
            raw_signals=raw_signals,
            activity=activity,
            user=user_a,
            client_id=account.client_id,
            confidence_min=0.5,
            drop_inferred=True,
        )

        assert len(persisted) == 1
        assert dropped == 3
        assert isinstance(persisted[0], BlockerSignal)
        assert persisted[0].summary == 'No Q4 budget'
        assert persisted[0].status == SignalStatus.PENDING
