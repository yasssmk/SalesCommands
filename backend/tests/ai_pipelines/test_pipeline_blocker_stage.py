# backend/tests/ai_pipelines/test_pipeline_blocker_stage.py
"""
Blocker-stage integration tests for QualificationSignalsPipeline (Sprint B3).

Covers the Blocker stage end-to-end through the pipeline:

  * LLM JSON output is parsed, safety-filtered, and persisted as a
    BlockerSignal row in PENDING status with the expected field
    mapping (summary, source_quote, confidence, is_inferred, source =
    LLM_EXTRACTED).
  * `contact` stays None when the LLM emits no participant reference
    (`raised_by`); a valid reference is resolved -- see
    TestBlockerRaisedByAttribution (Objection S3).
  * `canonical_key` stays None (BlockerSignal does not cluster).
  * Multiple distinct blockers on the same transcript persist as
    separate rows (no clustering / dedup at this layer).
  * Regression: the 4 pre-existing stages still emit Pain / Objective /
    Impact / TechStack PENDING signals in the same run.

Pure unit-level coverage of the persistence-service Blocker builder
lives in test_pipeline_extractor_blocker.py.
"""

import pytest

from app_modules.ai_pipelines.constants import AIPipelineStatus
from app_modules.signals.constants import SignalSource, SignalStatus
from app_modules.signals.models import (
    BlockerSignal,
    ImpactSignal,
    ObjectiveSignal,
    PainSignal,
    TechStackSignal,
)

from .conftest import CANNED_REPLIES_HAPPY

# Cross-account fixtures (tenant A, second account) -- re-used from the
# signals conftest, same re-export pattern as tests/ai_pipelines/conftest.py.
from tests.signals.conftest import (  # noqa: F401
    other_account,
    other_account_contact,
)


pytestmark = pytest.mark.django_db


# =============================================================================
# BLOCKER PERSISTENCE
# =============================================================================

class TestBlockerStagePersistence:
    """LLM Blocker JSON -> persisted BlockerSignal row."""

    def test_blocker_signal_persisted_in_pending_with_field_mapping(
        self, account, activity, user_a, fake_provider, patch_active_provider,
    ):
        from app_modules.ai_pipelines.pipelines.transcript_signals import (
            QualificationSignalsPipeline,
        )
        fake_provider.replies = {
            'blocker': (
                '{"signals": [{'
                '"summary": "No budget allocated for Q4", '
                '"source_quote": "We have no budget for this in Q4", '
                '"confidence": 0.85, '
                '"is_inferred": false'
                '}]}'
            ),
        }

        result = QualificationSignalsPipeline().run(
            transcript='Discovery call with Acme. Budget came up at the end.',
            activity=activity,
            user=user_a,
            client_id=account.client_id,
        )

        # One BlockerSignal persisted on the activity.
        blockers = result['signals_by_stage']['blocker']
        assert len(blockers) == 1

        signal = blockers[0]
        assert isinstance(signal, BlockerSignal)
        assert signal.summary      == 'No budget allocated for Q4'
        assert signal.source_quote == 'We have no budget for this in Q4'
        assert signal.confidence   == pytest.approx(0.85)
        assert signal.is_inferred  is False
        assert signal.source       == SignalSource.LLM_EXTRACTED
        assert signal.status       == SignalStatus.PENDING
        assert signal.account_id   == account.id
        assert signal.source_activity_id == activity.id
        # No `raised_by` emitted -> no attribution (Objection S3).
        assert signal.contact_id   is None
        # BlockerSignal never clusters.
        assert signal.canonical_key is None

    def test_multiple_blockers_persist_as_separate_rows(
        self, account, activity, user_a, fake_provider, patch_active_provider,
    ):
        """
        Two distinct blocker quotes in one LLM reply -- both persisted.
        BlockerSignal does not deduplicate at the persistence layer.
        """
        from app_modules.ai_pipelines.pipelines.transcript_signals import (
            QualificationSignalsPipeline,
        )
        fake_provider.replies = {
            'blocker': (
                '{"signals": ['
                '{"summary": "No budget in Q4", '
                '"source_quote": "We have no budget for this in Q4", '
                '"confidence": 0.85, "is_inferred": false},'
                '{"summary": "CTO sign-off required", '
                '"source_quote": "I need to discuss this with our CTO", '
                '"confidence": 0.9, "is_inferred": false}'
                ']}'
            ),
        }

        result = QualificationSignalsPipeline().run(
            transcript='Discovery call with Acme. Two blockers raised.',
            activity=activity,
            user=user_a,
            client_id=account.client_id,
        )
        blockers = result['signals_by_stage']['blocker']
        assert len(blockers) == 2

        summaries = {b.summary for b in blockers}
        assert summaries == {'No budget in Q4', 'CTO sign-off required'}

    def test_empty_blocker_reply_persists_zero_signals_no_error(
        self, account, activity, user_a, fake_provider, patch_active_provider,
    ):
        """
        Empty {"signals": []} from the LLM is the expected "no blocker
        evidence" shape -- it must NOT raise and must NOT mark the run
        as failed.
        """
        from app_modules.ai_pipelines.pipelines.transcript_signals import (
            QualificationSignalsPipeline,
        )
        fake_provider.replies = {'blocker': '{"signals": []}'}

        result = QualificationSignalsPipeline().run(
            transcript='Discovery call without any blocker raised.',
            activity=activity,
            user=user_a,
            client_id=account.client_id,
        )
        assert result['signals_by_stage']['blocker'] == []
        assert BlockerSignal.objects.count() == 0
        # The stage succeeded (parse OK + 0 emitted is fine).
        blocker_sub = next(
            c for c in result['run'].sub_calls if c['stage'] == 'blocker'
        )
        assert blocker_sub['error'] is None
        assert blocker_sub['emitted_count'] == 0


# =============================================================================
# RAISED BY -- the speaker's name as written, linked by the server (TD-279)
# =============================================================================

def _blocker_reply(raised_by_name_json):
    """One blocker signal whose `raised_by_name` is the given JSON literal."""
    return (
        '{"signals": [{'
        '"summary": "No budget allocated for Q4", '
        '"source_quote": "We have no budget for this in Q4", '
        '"confidence": 0.85, '
        '"is_inferred": false, '
        f'"raised_by_name": {raised_by_name_json}'
        '}]}'
    )


class TestBlockerRaisedByAttribution:
    """
    TD-279 B4b: the LLM gets no contact list and returns the speaker's name
    in `raised_by_name`; the server links it to a contact registered on the
    activity (tenant + account filtered, an ambiguous name is never linked).
    An absent / null / unknown name leaves contact None -- the signal is
    ALWAYS persisted.
    """

    def _run(self, account, activity, user_a, fake_provider, raised_by_name_json):
        from app_modules.ai_pipelines.pipelines.transcript_signals import (
            QualificationSignalsPipeline,
        )
        fake_provider.replies = {'blocker': _blocker_reply(raised_by_name_json)}
        result = QualificationSignalsPipeline().run(
            transcript='Discovery call with Acme. Budget came up at the end.',
            activity=activity,
            user=user_a,
            client_id=account.client_id,
        )
        blockers = result['signals_by_stage']['blocker']
        # Never lost because of the attribution.
        assert len(blockers) == 1
        return blockers[0], fake_provider

    def test_speaker_name_links_the_registered_contact(
        self, account, activity, user_a, contact, contact_extra,
        fake_provider, patch_active_provider,
    ):
        activity.contacts.add(contact, contact_extra)
        signal, provider = self._run(account, activity, user_a, fake_provider, '"John Smith"')
        signal.refresh_from_db()
        assert signal.contact_id == contact_extra.id
        # The blocker prompt carries no contact list (context v8).
        blocker_prompt = provider.calls_for('blocker')[0]['user']
        assert 'Prospect contacts' not in blocker_prompt
        assert 'Jane' not in blocker_prompt

    def test_null_name_leaves_contact_none(
        self, account, activity, user_a, contact, contact_extra,
        fake_provider, patch_active_provider,
    ):
        activity.contacts.add(contact, contact_extra)
        signal, _ = self._run(account, activity, user_a, fake_provider, 'null')
        assert signal.contact_id is None

    @pytest.mark.parametrize('raised_by_name_json', ['"Marc"', '"P2"'])
    def test_unknown_name_contact_none_signal_persisted(
        self, account, activity, user_a, contact, contact_extra,
        fake_provider, patch_active_provider, raised_by_name_json,
    ):
        activity.contacts.add(contact, contact_extra)
        signal, _ = self._run(account, activity, user_a, fake_provider, raised_by_name_json)
        assert signal.contact_id is None
        assert BlockerSignal.objects.filter(id=signal.id).exists()

    def test_other_account_contact_is_never_linked(
        self, account, activity, user_a, contact, other_account_contact,
        fake_provider, patch_active_provider,
    ):
        activity.contacts.add(contact, other_account_contact)
        signal, _ = self._run(account, activity, user_a, fake_provider, '"Bill Lumbergh"')
        assert signal.contact_id is None


# =============================================================================
# REGRESSION -- the 4 pre-existing stages still work alongside Blocker
# =============================================================================

class TestFourPreviousStagesStillPersist:
    """
    The Pain / Objective / Impact / TechStack stages must keep producing
    rows after Blocker is added. A single happy-path run is enough --
    detailed per-stage assertions live in the existing signals tests.
    """

    def test_full_5_stage_happy_path_persists_one_signal_per_type(
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

        # 1 signal per type was persisted to the right concrete model.
        assert PainSignal.objects.count()      == 1
        assert ObjectiveSignal.objects.count() == 1
        assert ImpactSignal.objects.count()    == 1
        assert TechStackSignal.objects.count() == 1
        assert BlockerSignal.objects.count()   == 1

        # All in PENDING (LLM_EXTRACTED source -> PENDING status by
        # BaseSignal.save() business rule).
        for model in (PainSignal, ObjectiveSignal, ImpactSignal,
                      TechStackSignal, BlockerSignal):
            instance = model.objects.first()
            assert instance.status == SignalStatus.PENDING, (
                f'{model.__name__} must be PENDING after LLM extraction.'
            )
            assert instance.source == SignalSource.LLM_EXTRACTED

    def test_created_signals_count_includes_blocker(
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
        # 5 stages x 1 signal each = 5 persisted in this happy-path run.
        assert result['run'].created_signals_count == 5
