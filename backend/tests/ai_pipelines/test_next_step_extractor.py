# backend/tests/ai_pipelines/test_next_step_extractor.py
"""
Unit tests for NextStepExtractor (Sprint B4).

Zooms in on services/next_step_extractor.py without the LLM provider:

  * `_build_next_step_data` happy path and defensive drops.
  * `_parse_iso_date` lenient ISO date parsing (valid / null / invalid).
  * Activity-type defense in depth (invalid value -> drop).
  * v1 deferred fields: suggested_contacts never populated (TD-7).
  * Safety filter chain inside `persist_extracted` on a mixed batch.

End-to-end pipeline tests live in test_pipeline_next_steps.py.
"""

import datetime
import pytest

from app_modules.activities.constants import ActivityType
from app_modules.ai_pipelines.services.next_step_extractor import (
    NextStepExtractor,
)
from app_modules.signals.constants import SignalSource, SignalStatus
from app_modules.signals.models import NextStepSignal


pytestmark = pytest.mark.django_db


# =============================================================================
# BUILDER -- happy path
# =============================================================================

class TestBuildNextStepDataHappyPath:
    """A well-formed raw LLM signal yields a complete data dict."""

    def test_builder_returns_complete_data_dict(self, account, activity):
        extractor = NextStepExtractor()
        raw = {
            'suggested_title':         'Send pricing recap to CFO',
            'suggested_activity_type': 'EMAIL',
            'suggested_due_date':      '2026-12-15',
            'source_quote':            'The CFO asked for a pricing recap by mid-December',
            'confidence':              0.9,
            'is_inferred':             False,
        }
        data = extractor._build_next_step_data(raw, activity)

        assert data['signal_type']             == 'next_step'
        assert data['account']                 == account
        assert data['source_activity']         == activity
        assert data['source']                  == SignalSource.LLM_EXTRACTED
        assert data['status']                  == SignalStatus.PENDING
        assert data['suggested_title']         == 'Send pricing recap to CFO'
        assert data['suggested_activity_type'] == 'EMAIL'
        assert data['suggested_due_date']      == datetime.date(2026, 12, 15)
        assert data['source_quote']            == (
            'The CFO asked for a pricing recap by mid-December'
        )
        assert data['confidence']              == pytest.approx(0.9)
        assert data['is_inferred']             is False

        # v1: contacts attribution deferred to validation UI -- TD-7.
        # The builder must NOT include the M2M key (SignalManager's
        # M2M-aware path treats a missing key as "no relations").
        assert 'suggested_contacts' not in data


# =============================================================================
# BUILDER -- defensive drops on required fields
# =============================================================================

class TestBuildNextStepDataDefensiveDrops:
    """Malformed LLM payloads return None so the safety net counts them."""

    @pytest.mark.parametrize('missing_field', [
        'suggested_title',
        'suggested_activity_type',
        'source_quote',
    ])
    def test_builder_drops_when_required_field_missing(self, activity, missing_field):
        extractor = NextStepExtractor()
        raw = {
            'suggested_title':         'Send recap',
            'suggested_activity_type': 'EMAIL',
            'source_quote':            'The CFO asked for a recap',
            'confidence':              0.9,
            'is_inferred':             False,
        }
        del raw[missing_field]
        assert extractor._build_next_step_data(raw, activity) is None

    @pytest.mark.parametrize('blank_field', [
        'suggested_title',
        'source_quote',
    ])
    def test_builder_drops_when_required_field_blank(self, activity, blank_field):
        """Empty / whitespace-only required strings drop the signal."""
        extractor = NextStepExtractor()
        raw = {
            'suggested_title':         'Send recap',
            'suggested_activity_type': 'EMAIL',
            'source_quote':            'The CFO asked for a recap',
            'confidence':              0.9,
            'is_inferred':             False,
        }
        raw[blank_field] = '   '
        assert extractor._build_next_step_data(raw, activity) is None

    def test_builder_drops_when_required_field_is_none(self, activity):
        extractor = NextStepExtractor()
        raw = {
            'suggested_title':         None,
            'suggested_activity_type': 'EMAIL',
            'source_quote':            'The CFO asked for a recap',
            'confidence':              0.9,
            'is_inferred':             False,
        }
        assert extractor._build_next_step_data(raw, activity) is None


# =============================================================================
# BUILDER -- activity_type defense in depth
# =============================================================================

class TestBuildNextStepDataActivityTypeValidation:
    """suggested_activity_type must be a valid ActivityType DB value."""

    def test_builder_drops_unknown_activity_type(self, activity):
        extractor = NextStepExtractor()
        raw = {
            'suggested_title':         'Send recap',
            'suggested_activity_type': 'PIGEON',  # not in ActivityType
            'source_quote':            'The CFO asked for a recap',
            'confidence':              0.9,
            'is_inferred':             False,
        }
        assert extractor._build_next_step_data(raw, activity) is None

    @pytest.mark.parametrize('valid_type', list(ActivityType.values))
    def test_builder_accepts_every_activity_type_value(self, activity, valid_type):
        extractor = NextStepExtractor()
        raw = {
            'suggested_title':         f'Next step for {valid_type}',
            'suggested_activity_type': valid_type,
            'source_quote':            'The CFO asked for a recap',
            'confidence':              0.9,
            'is_inferred':             False,
        }
        data = extractor._build_next_step_data(raw, activity)
        assert data is not None
        assert data['suggested_activity_type'] == valid_type


# =============================================================================
# DUE DATE PARSING -- lenient
# =============================================================================

class TestParseIsoDate:
    """Lenient ISO YYYY-MM-DD parsing: invalid format -> None, no drop."""

    def test_valid_iso_date_parses(self):
        assert NextStepExtractor._parse_iso_date('2026-12-15') == datetime.date(2026, 12, 15)

    def test_none_returns_none(self):
        assert NextStepExtractor._parse_iso_date(None) is None

    def test_empty_string_returns_none(self):
        assert NextStepExtractor._parse_iso_date('') is None

    def test_whitespace_only_returns_none(self):
        assert NextStepExtractor._parse_iso_date('   ') is None

    def test_invalid_format_returns_none_no_raise(self):
        """Lenient policy: bad date does NOT raise."""
        assert NextStepExtractor._parse_iso_date('not a date') is None
        assert NextStepExtractor._parse_iso_date('15/12/2026') is None
        assert NextStepExtractor._parse_iso_date('2026-13-01') is None

    def test_non_string_returns_none(self):
        assert NextStepExtractor._parse_iso_date(12345) is None
        assert NextStepExtractor._parse_iso_date(['2026-12-15']) is None


class TestBuilderDueDateBehavior:
    """The builder integrates _parse_iso_date with the lenient policy."""

    def test_builder_persists_null_due_date(self, activity):
        extractor = NextStepExtractor()
        raw = {
            'suggested_title':         'Send recap',
            'suggested_activity_type': 'EMAIL',
            'suggested_due_date':      None,
            'source_quote':            'The CFO asked for a recap',
            'confidence':              0.9,
            'is_inferred':             False,
        }
        data = extractor._build_next_step_data(raw, activity)
        assert data is not None
        assert data['suggested_due_date'] is None

    def test_builder_does_not_drop_on_invalid_due_date(self, activity):
        """
        Lenient: invalid date format coerces to None but the signal
        still persists -- the rep refines at validation time.
        """
        extractor = NextStepExtractor()
        raw = {
            'suggested_title':         'Send recap',
            'suggested_activity_type': 'EMAIL',
            'suggested_due_date':      'tuesday-ish',
            'source_quote':            'The CFO asked for a recap',
            'confidence':              0.9,
            'is_inferred':             False,
        }
        data = extractor._build_next_step_data(raw, activity)
        assert data is not None  # signal NOT dropped
        assert data['suggested_due_date'] is None


# =============================================================================
# DEFAULTS
# =============================================================================

class TestBuilderDefaults:
    """Optional fields get safe defaults."""

    def test_missing_is_inferred_defaults_to_false(self, activity):
        extractor = NextStepExtractor()
        raw = {
            'suggested_title':         'Send recap',
            'suggested_activity_type': 'EMAIL',
            'source_quote':            'The CFO asked for a recap',
            'confidence':              0.9,
        }
        data = extractor._build_next_step_data(raw, activity)
        assert data['is_inferred'] is False

    def test_missing_confidence_coerces_to_zero(self, activity):
        """
        safe_float defaults to 0.0 on missing confidence. The upstream
        safety filter would have rejected the signal already (0.0 <
        CONFIDENCE_MIN), but the builder itself must not crash.
        """
        extractor = NextStepExtractor()
        raw = {
            'suggested_title':         'Send recap',
            'suggested_activity_type': 'EMAIL',
            'source_quote':            'The CFO asked for a recap',
        }
        data = extractor._build_next_step_data(raw, activity)
        assert data['confidence'] == 0.0


# =============================================================================
# INTEGRATION via persist_extracted
# =============================================================================

class TestPersistExtractedIntegration:
    """
    persist_extracted is the integration surface that NextStepsPipeline
    actually calls. Asserts safety filter + builder chain produce the
    expected persisted rows + dropped count + field mapping on the DB.
    """

    def test_persist_extracted_persists_and_counts_drops(
        self, account, activity, user_a,
    ):
        extractor = NextStepExtractor()
        raw_signals = [
            # Persists.
            {
                'suggested_title':         'Send pricing recap',
                'suggested_activity_type': 'EMAIL',
                'suggested_due_date':      '2026-12-15',
                'source_quote':            'The CFO asked for a pricing recap',
                'confidence':              0.9,
                'is_inferred':             False,
            },
            # Drop -- safety filter (low confidence).
            {
                'suggested_title':         'low-conf next step',
                'suggested_activity_type': 'CALL',
                'source_quote':            'maybe a call',
                'confidence':              0.3,
                'is_inferred':             False,
            },
            # Drop -- safety filter (is_inferred).
            {
                'suggested_title':         'inferred next step',
                'suggested_activity_type': 'MEETING',
                'source_quote':            'hinted at a follow-up',
                'confidence':              0.95,
                'is_inferred':             True,
            },
            # Drop -- invalid activity_type.
            {
                'suggested_title':         'bad type',
                'suggested_activity_type': 'PIGEON',
                'source_quote':            'send a pigeon',
                'confidence':              0.95,
                'is_inferred':             False,
            },
            # Drop -- missing source_quote.
            {
                'suggested_title':         'no quote',
                'suggested_activity_type': 'EMAIL',
                'confidence':              0.95,
                'is_inferred':             False,
            },
        ]

        persisted, dropped = extractor.persist_extracted(
            raw_signals=raw_signals,
            activity=activity,
            user=user_a,
            client_id=account.client_id,
            confidence_min=0.5,
            drop_inferred=True,
        )

        assert len(persisted) == 1
        assert dropped == 4

        signal = persisted[0]
        assert isinstance(signal, NextStepSignal)
        assert signal.suggested_title         == 'Send pricing recap'
        assert signal.suggested_activity_type == 'EMAIL'
        assert signal.suggested_due_date      == datetime.date(2026, 12, 15)
        assert signal.source                  == SignalSource.LLM_EXTRACTED
        assert signal.status                  == SignalStatus.PENDING
        assert signal.canonical_key           is None  # never clusters

        # v1: suggested_contacts deferred -- TD-7.
        assert signal.suggested_contacts.count() == 0

    def test_persist_extracted_handles_non_list_input_gracefully(
        self, account, activity, user_a,
    ):
        """A malformed (non-list) input must not raise -- empty result."""
        extractor = NextStepExtractor()
        persisted, dropped = extractor.persist_extracted(
            raw_signals=None,  # malformed
            activity=activity,
            user=user_a,
            client_id=account.client_id,
            confidence_min=0.5,
            drop_inferred=True,
        )
        assert persisted == []
        assert dropped == 0

    def test_persist_extracted_skips_non_dict_entries(
        self, account, activity, user_a,
    ):
        """Each non-dict entry in the list is counted as a drop."""
        extractor = NextStepExtractor()
        raw_signals = [
            'not a dict',
            42,
            None,
            {
                'suggested_title':         'Real signal',
                'suggested_activity_type': 'EMAIL',
                'source_quote':            'The CFO asked',
                'confidence':              0.9,
                'is_inferred':             False,
            },
        ]
        persisted, dropped = extractor.persist_extracted(
            raw_signals=raw_signals,
            activity=activity,
            user=user_a,
            client_id=account.client_id,
            confidence_min=0.5,
            drop_inferred=True,
        )
        assert len(persisted) == 1
        assert dropped == 3
