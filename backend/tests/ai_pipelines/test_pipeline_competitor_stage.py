# backend/tests/ai_pipelines/test_pipeline_competitor_stage.py
"""
Competitor-stage integration tests for QualificationSignalsPipeline
(Competitors sprint, sub-step 2 -- EXTRACTION).

Covers the Competitor stage end-to-end through the pipeline:

  * LLM JSON is parsed, safety-filtered, and persisted as a
    CompetitorSignal row in PENDING status: summary + competitor_name +
    source_quote, source=LLM_EXTRACTED.
  * competitor_name_normalized is derived in save(); canonical_key stays
    None (detached, sub-step 1).
  * Non-confusion: a tool merely USED (tech-stack) or mentioned as an
    INTEGRATION requirement (constraint) does NOT become a
    CompetitorSignal -- the competitor stage only emits competitors.

Cloned on test_pipeline_constraint_stage.py.
"""

import pytest

from app_modules.signals.constants import (
    SignalSource,
    SignalStatus,
)
from app_modules.signals.models import CompetitorSignal


pytestmark = pytest.mark.django_db


# =============================================================================
# HELPERS
# =============================================================================

def _competitor_reply(objs):
    import json
    return json.dumps({'signals': objs})


def _competitor_obj(*, summary, competitor_name,
                    source_quote='we are also evaluating it instead of you',
                    confidence=0.9, is_inferred=False):
    return {
        'summary': summary,
        'competitor_name': competitor_name,
        'source_quote': source_quote,
        'confidence': confidence,
        'is_inferred': is_inferred,
    }


def _run(account, activity, user_a, transcript='A transcript about Acme.'):
    from app_modules.ai_pipelines.pipelines.transcript_signals import (
        QualificationSignalsPipeline,
    )
    return QualificationSignalsPipeline().run(
        transcript=transcript,
        activity=activity,
        user=user_a,
        client_id=account.client_id,
    )


# =============================================================================
# PERSISTENCE
# =============================================================================

class TestCompetitorStagePersistence:

    def test_competitor_persisted_with_derived_normalized_name(
        self, account, activity, user_a,
        fake_provider, patch_active_provider,
    ):
        fake_provider.replies = {
            'competitor': _competitor_reply([_competitor_obj(
                summary='Prospect is weighing Intercom instead of our tool',
                competitor_name='Intercom',
                source_quote="we're also evaluating Intercom instead of you",
            )]),
        }

        result = _run(account, activity, user_a)

        competitors = result['signals_by_stage']['competitor']
        assert len(competitors) == 1
        sig = competitors[0]
        assert isinstance(sig, CompetitorSignal)
        assert sig.competitor_name == 'Intercom'
        assert sig.summary == 'Prospect is weighing Intercom instead of our tool'
        assert sig.source_quote == "we're also evaluating Intercom instead of you"
        assert sig.status == SignalStatus.PENDING
        assert sig.source == SignalSource.LLM_EXTRACTED
        assert sig.source_activity_id == activity.id
        # Detached: no canonical_key.
        assert sig.canonical_key is None
        # Normalised key derived in save().
        assert sig.competitor_name_normalized == 'intercom'

    def test_empty_reply_creates_no_competitor(
        self, account, activity, user_a,
        fake_provider, patch_active_provider,
    ):
        # Default empty reply for the competitor stage -> zero rows.
        result = _run(account, activity, user_a)
        assert result['signals_by_stage']['competitor'] == []
        assert CompetitorSignal.objects.count() == 0


# =============================================================================
# NON-CONFUSION -- a USED tool / an INTEGRATION requirement is NOT a competitor
# =============================================================================

class TestCompetitorNonConfusion:
    """
    The competitor stage only ever emits competitors. A tool the prospect
    merely uses, or names only as an integration requirement, yields no
    CompetitorSignal -- the stage returns the default empty reply.
    """

    def test_used_tool_does_not_become_competitor(
        self, account, activity, user_a,
        fake_provider, patch_active_provider,
    ):
        # A run whose techstack names a merely-used tool, and whose
        # competitor stage emits nothing, must yield ZERO competitors.
        fake_provider.replies = {
            'techstack': (
                '{"signals": [{'
                '"tech_name": "Zendesk", '
                '"is_competitor": false, '
                '"is_to_replace": false, '
                '"usage_scope": "COMPANY", '
                '"source_quote": "we currently use Zendesk for support", '
                '"confidence": 0.9, "is_inferred": false}]}'
            ),
            # competitor stage: nothing framed as an alternative.
            'competitor': _competitor_reply([]),
        }

        result = _run(account, activity, user_a)

        assert result['signals_by_stage'].get('competitor', []) == []
        assert CompetitorSignal.objects.count() == 0
