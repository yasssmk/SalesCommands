# backend/tests/ai_pipelines/test_competitor_dedup.py
"""
Sprint Competitor C3 — a competitor cited several times in ONE transcript is
ONE signal.

PO rule:
  * in-extraction only: the candidates of ONE extraction batch (one
    transcript, one competitor sub-call) sharing the same normalised
    competitor name are merged — the FIRST wins, the later source_quotes go
    to metadata.additional_quotes (shared _deduplicate_candidates, as
    TechStack);
  * NEVER a filter between activities (nor between two runs): the grouping
    across activities is the DC cluster's job (read-time, on
    competitor_name_normalized).

Grouping key = CompetitorSignal._normalize_competitor_name, the very rule
save() uses to fill competitor_name_normalized.
"""

import json

import pytest

from app_modules.signals.models import CompetitorSignal
from app_modules.signals.services import SignalClusterService
from app_modules.ai_pipelines.services.transcript_signal_extractor import (
    TranscriptSignalExtractor,
)
from tests.signals.conftest import decision_cycle  # noqa: F401


pytestmark = pytest.mark.django_db


def _raw(name, quote, summary=None):
    return {
        'competitor_name': name,
        'summary': summary or f'The prospect is weighing {name} against us.',
        'source_quote': quote,
        'confidence': 0.9,
        'is_inferred': False,
    }


def _persist(activity, account, user, raw_signals):
    return TranscriptSignalExtractor().persist_stage(
        stage='competitor',
        raw_signals=raw_signals,
        activity=activity,
        user=user,
        client_id=account.client_id,
        confidence_min=0.5,
        drop_inferred=True,
    )


def _second_activity(account, user, decision_cycle):  # noqa: F811
    from app_modules.activities.constants import ActivityStatus, ActivityType
    from app_modules.activities.models import Activity
    a = Activity(
        title='Follow-up call with Acme',
        activity_type=ActivityType.MEETING,
        status=ActivityStatus.COMPLETED,
        account=account,
        owner=user,
        decision_cycle=decision_cycle,
    )
    a.save(user=user, client_id=account.client_id)
    return a


# =============================================================================
# A — one batch (one transcript): duplicates merged
# =============================================================================

class TestSameTranscriptIsOneSignal:

    def test_same_competitor_twice_is_one_signal_with_the_second_quote_kept(
        self, account, activity, user_a,
    ):
        persisted, dropped = _persist(activity, account, user_a, [
            _raw('Intercom', "We're also looking at Intercom.",
                 summary='The prospect is evaluating Intercom instead of us.'),
            _raw('intercom', 'Intercom came up again in the demo.'),
        ])

        assert len(persisted) == 1
        assert dropped == 1
        sig = persisted[0]
        sig.refresh_from_db()
        # The FIRST candidate wins (its name, summary and quote).
        assert sig.competitor_name == 'Intercom'
        assert sig.summary == 'The prospect is evaluating Intercom instead of us.'
        assert sig.source_quote == "We're also looking at Intercom."
        assert sig.metadata['additional_quotes'] == ['Intercom came up again in the demo.']
        assert CompetitorSignal.objects.filter(source_activity=activity).count() == 1

    def test_spacing_and_casing_variants_are_one_competitor(
        self, account, activity, user_a,
    ):
        persisted, _ = _persist(activity, account, user_a, [
            _raw('Acme Corp', 'q1'),
            _raw('  acme   CORP ', 'q2'),
            _raw('ACME corp', 'q3'),
        ])

        assert len(persisted) == 1
        persisted[0].refresh_from_db()
        assert persisted[0].metadata['additional_quotes'] == ['q2', 'q3']

    def test_different_competitors_stay_separate(self, account, activity, user_a):
        persisted, dropped = _persist(activity, account, user_a, [
            _raw('Intercom', 'q1'),
            _raw('HubSpot', 'q2'),
            _raw('intercom', 'q3'),
        ])

        assert dropped == 1
        assert sorted(s.competitor_name for s in persisted) == ['HubSpot', 'Intercom']

    def test_through_the_pipeline_one_transcript_citing_a_competitor_twice(
        self, account, activity, user_a, fake_provider, patch_active_provider,
    ):
        from app_modules.ai_pipelines.pipelines.transcript_signals import (
            QualificationSignalsPipeline,
        )
        fake_provider.replies = {
            'competitor': json.dumps({'signals': [
                _raw('Intercom', "We're also looking at Intercom."),
                _raw('intercom', 'Intercom came up again in the demo.'),
            ]}),
        }

        QualificationSignalsPipeline().run(
            transcript="We're also looking at Intercom. Intercom came up again in the demo.",
            activity=activity, user=user_a, client_id=account.client_id,
        )

        signals = CompetitorSignal.objects.filter(source_activity=activity)
        assert signals.count() == 1
        assert signals.get().metadata['additional_quotes'] == [
            'Intercom came up again in the demo.',
        ]


# =============================================================================
# B — guards: NEVER a filter outside the batch; the DC cluster groups
# =============================================================================

class TestNoFilterOutsideTheBatch:

    def test_two_activities_of_one_dc_keep_two_signals_and_the_dc_cluster_groups_them(
        self, account, activity, user_a, decision_cycle,  # noqa: F811
    ):
        from app_modules.activities.models import Activity
        Activity.objects.filter(id=activity.id).update(decision_cycle=decision_cycle)
        activity.refresh_from_db()
        other = _second_activity(account, user_a, decision_cycle)

        _persist(activity, account, user_a, [_raw('Intercom', 'First call quote.')])
        _persist(other, account, user_a, [_raw('intercom', 'Second call quote.')])

        # Two activities → two signals (no inter-activity filter)...
        signals = CompetitorSignal.objects.filter(decision_cycle=decision_cycle)
        assert signals.count() == 2
        assert {s.source_activity_id for s in signals} == {activity.id, other.id}

        # ...grouped into ONE competitor cluster at the DC level.
        clusters = SignalClusterService.list_clusters_for_account(
            account_id=account.id,
            signal_type='competitor',
            decision_cycle_id=decision_cycle.id,
        )
        assert len(clusters) == 1
        assert clusters[0]['canonical_key'] == 'intercom'
        assert clusters[0]['signal_count'] == 2

    def test_two_batches_on_the_same_activity_are_not_filtered(
        self, account, activity, user_a,
    ):
        # A re-extraction is a new batch: the dedup is in-batch only (PO: the
        # re-extraction is left as is, noted for the fine-tuning).
        _persist(activity, account, user_a, [_raw('Intercom', 'q1')])
        _persist(activity, account, user_a, [_raw('Intercom', 'q2')])

        assert CompetitorSignal.objects.filter(source_activity=activity).count() == 2
