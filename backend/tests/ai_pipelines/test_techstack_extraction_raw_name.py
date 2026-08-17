# backend/tests/ai_pipelines/test_techstack_extraction_raw_name.py
"""
Tech-stack extraction on the S10 contract: raw name + qualification booleans.

The LLM no longer matches a TechCatalog UUID. It emits the tool name as
free text plus three independent booleans, and the extractor writes them
straight onto the sub-step-1 fields:

    LLM field        ->  TechStackSignal column
    ---------------      ----------------------------------------
    tech_name        ->  tech_name (raw) -> tech_name_normalized
                         (derived by TechStackSignal.save())
    is_competitor    ->  is_competitor
    is_integration   ->  is_integration
    is_to_replace    ->  is_to_replace

`tech_catalog_entry` is never set by the extractor anymore (the FK still
exists on the model — it is removed in sub-step 5).

Harness mirrors TestPersistStageBlocker in
tests/ai_pipelines/test_pipeline_extractor_blocker.py:194-249 — the real
`persist_stage()` integration surface the pipeline orchestrator calls,
safety filter and builder chained, no LLM provider involved.
"""

import pytest

from app_modules.ai_pipelines.services.transcript_signal_extractor import (
    TranscriptSignalExtractor,
)
from app_modules.signals.constants import SignalSource, SignalStatus
from app_modules.signals.models import TechStackSignal
from app_modules.signals.services.signal_data_service import SignalDataService


pytestmark = pytest.mark.django_db


# =============================================================================
# HELPERS
# =============================================================================

def _raw(tech_name, **overrides):
    """A well-formed LLM tech-stack emission on the new contract."""
    payload = {
        'tech_name':      tech_name,
        'is_competitor':  False,
        'is_integration': False,
        'is_to_replace':  False,
        'usage_scope':    'COMPANY',
        'source_quote':   f'We use {tech_name} across the company',
        'confidence':     0.9,
        'is_inferred':    False,
    }
    payload.update(overrides)
    return payload


def _persist(activity, account, user, raw_signals):
    """Run the real extraction path for the techstack stage."""
    return TranscriptSignalExtractor().persist_stage(
        stage='techstack',
        raw_signals=raw_signals,
        activity=activity,
        user=user,
        client_id=account.client_id,
        confidence_min=0.5,
        drop_inferred=True,
    )


# =============================================================================
# A — RAW NAME LANDS ON THE MODEL, NO CATALOGUE INVOLVED
# =============================================================================

class TestRawNameExtraction:

    def test_raw_name_and_competitor_flag_persist_without_catalogue(
        self, account, activity, user_a,
    ):
        """
        The red-repro case: an LLM emission carrying a tech name and
        is_competitor, with NO catalogue UUID anywhere, must produce a
        TechStackSignal whose identity comes from the raw text.
        """
        persisted, dropped = _persist(
            activity, account, user_a,
            [_raw('Salesforce', is_competitor=True)],
        )

        assert dropped == 0
        assert len(persisted) == 1

        sig = persisted[0]
        assert isinstance(sig, TechStackSignal)
        assert sig.tech_name == 'Salesforce'
        assert sig.tech_name_normalized == 'salesforce'
        assert sig.is_competitor is True
        assert sig.tech_catalog_entry_id is None

        # And it is what actually landed in the DB.
        sig.refresh_from_db()
        assert sig.tech_name == 'Salesforce'
        assert sig.tech_name_normalized == 'salesforce'
        assert sig.is_competitor is True
        assert sig.tech_catalog_entry_id is None

    def test_raw_text_is_preserved_verbatim_and_normalised_by_save(
        self, account, activity, user_a,
    ):
        """
        The extractor must NOT normalise — that is the model's save()
        job (sub-step 1). Padding and casing survive on `tech_name`.
        """
        persisted, _ = _persist(
            activity, account, user_a,
            [_raw('  Salesforce   CRM ')],
        )

        sig = persisted[0]
        assert sig.tech_name == '  Salesforce   CRM '
        assert sig.tech_name_normalized == 'salesforce crm'

    def test_signal_keeps_the_standard_llm_lifecycle(
        self, account, activity, user_a,
    ):
        """Source / status / quote / scope routing is unchanged."""
        persisted, _ = _persist(
            activity, account, user_a,
            [_raw('HubSpot', usage_scope='TEAM')],
        )

        sig = persisted[0]
        assert sig.source == SignalSource.LLM_EXTRACTED
        assert sig.status == SignalStatus.PENDING
        assert sig.source_quote == 'We use HubSpot across the company'
        assert sig.usage_scope == 'TEAM'
        assert sig.account_id == account.id
        assert sig.source_activity_id == activity.id

    def test_pending_tech_name_is_no_longer_the_identity_carrier(
        self, account, activity, user_a,
    ):
        """
        metadata['pending_tech_name'] was the old identity slot. The
        tool name now lives on the column; nothing should depend on the
        metadata key anymore.
        """
        persisted, _ = _persist(activity, account, user_a, [_raw('Notion')])

        sig = persisted[0]
        assert sig.tech_name == 'Notion'
        assert 'pending_tech_name' not in (sig.metadata or {})


# =============================================================================
# B — THE THREE BOOLEANS
# =============================================================================

class TestQualificationBooleansFromLLM:

    def test_all_three_default_false_when_llm_omits_them(
        self, account, activity, user_a,
    ):
        """A tool the account simply uses."""
        persisted, _ = _persist(
            activity, account, user_a,
            [{
                'tech_name':    'Zoom',
                'source_quote': 'Everyone is on Zoom',
                'confidence':   0.9,
                'is_inferred':  False,
            }],
        )

        sig = persisted[0]
        assert sig.is_competitor is False
        assert sig.is_integration is False
        assert sig.is_to_replace is False

    def test_booleans_flow_through_independently(
        self, account, activity, user_a,
    ):
        persisted, _ = _persist(
            activity, account, user_a,
            [_raw('Salesforce', is_competitor=True, is_to_replace=True)],
        )

        sig = persisted[0]
        sig.refresh_from_db()
        assert sig.is_competitor is True
        assert sig.is_integration is False
        assert sig.is_to_replace is True

    def test_all_three_true_is_legal(self, account, activity, user_a):
        persisted, _ = _persist(
            activity, account, user_a,
            [_raw('Slack', is_competitor=True, is_integration=True,
                  is_to_replace=True)],
        )

        sig = persisted[0]
        sig.refresh_from_db()
        assert (sig.is_competitor, sig.is_integration, sig.is_to_replace) == (
            True, True, True,
        )

    def test_truthy_non_bool_values_are_coerced(
        self, account, activity, user_a,
    ):
        """An LLM emitting "true"/1 must not land a non-boolean in the DB."""
        persisted, _ = _persist(
            activity, account, user_a,
            [_raw('Jira', is_integration=1, is_competitor=None)],
        )

        sig = persisted[0]
        assert sig.is_integration is True
        assert sig.is_competitor is False


# =============================================================================
# C — MALFORMED EMISSIONS ARE DROPPED
# =============================================================================

class TestMalformedEmissions:

    def test_missing_tech_name_is_dropped(self, account, activity, user_a):
        persisted, dropped = _persist(
            activity, account, user_a,
            [{
                'source_quote': 'They use something for CRM',
                'confidence':   0.9,
                'is_inferred':  False,
            }],
        )

        assert persisted == []
        assert dropped == 1

    def test_blank_tech_name_is_dropped(self, account, activity, user_a):
        persisted, dropped = _persist(
            activity, account, user_a,
            [_raw('   ')],
        )

        assert persisted == []
        assert dropped == 1

    def test_missing_source_quote_is_dropped(self, account, activity, user_a):
        persisted, dropped = _persist(
            activity, account, user_a,
            [_raw('Salesforce', source_quote=None)],
        )

        assert persisted == []
        assert dropped == 1

    def test_safety_filter_still_applies(self, account, activity, user_a):
        """Low confidence and inferred signals are dropped as before."""
        persisted, dropped = _persist(
            activity, account, user_a,
            [
                _raw('Salesforce'),                      # kept
                _raw('HubSpot', confidence=0.3),         # low confidence
                _raw('Pipedrive', is_inferred=True),     # inferred
            ],
        )

        assert len(persisted) == 1
        assert dropped == 2
        assert persisted[0].tech_name == 'Salesforce'

    def test_department_scope_is_still_demoted_to_null(
        self, account, activity, user_a,
    ):
        """usage_scope filtering is unchanged by this rework."""
        persisted, _ = _persist(
            activity, account, user_a,
            [_raw('Asana', usage_scope='DEPARTMENT')],
        )

        assert persisted[0].usage_scope is None


# =============================================================================
# D — BATCH DEDUP ON THE NORMALISED NAME
# =============================================================================

class TestBatchDedupOnNormalisedName:

    def test_three_spellings_of_one_tool_collapse_to_one_signal(
        self, account, activity, user_a,
    ):
        persisted, dropped = _persist(
            activity, account, user_a,
            [
                _raw('Salesforce', source_quote='We use Salesforce for CRM'),
                _raw('salesforce', source_quote='Salesforce is our main tool'),
                _raw(' Salesforce ', source_quote='The team relies on Salesforce'),
            ],
        )

        assert len(persisted) == 1
        assert dropped == 2

        sig = persisted[0]
        assert sig.tech_name == 'Salesforce'
        assert sig.source_quote == 'We use Salesforce for CRM'
        assert len(sig.metadata['additional_quotes']) == 2

    def test_internal_whitespace_variants_collapse_too(
        self, account, activity, user_a,
    ):
        persisted, _ = _persist(
            activity, account, user_a,
            [
                _raw('Microsoft Teams', source_quote='q1'),
                _raw('microsoft   teams', source_quote='q2'),
            ],
        )

        assert len(persisted) == 1
        assert persisted[0].tech_name_normalized == 'microsoft teams'

    def test_distinct_tools_stay_separate(self, account, activity, user_a):
        persisted, _ = _persist(
            activity, account, user_a,
            [
                _raw('Salesforce', source_quote='q1'),
                _raw('HubSpot', source_quote='q2'),
                _raw('Salesforce', source_quote='q3'),
            ],
        )

        assert len(persisted) == 2
        assert [s.tech_name for s in persisted] == ['Salesforce', 'HubSpot']

    def test_dedup_keeps_the_first_candidates_booleans(
        self, account, activity, user_a,
    ):
        """
        The winner is the first occurrence — its qualification wins.
        Documents the behaviour rather than silently merging flags.
        """
        persisted, _ = _persist(
            activity, account, user_a,
            [
                _raw('Salesforce', is_competitor=True, source_quote='q1'),
                _raw('salesforce', is_integration=True, source_quote='q2'),
            ],
        )

        assert len(persisted) == 1
        assert persisted[0].is_competitor is True
        assert persisted[0].is_integration is False


# =============================================================================
# E — DOWNSTREAM LABEL READS THE RAW NAME
# =============================================================================

class TestSignalDataServiceLabel:

    def test_extract_summary_returns_the_tech_name(
        self, account, activity, user_a,
    ):
        """
        _extract_summary feeds LLM-facing payloads. It used to compose
        the label from the catalogue FK; with the FK now always null it
        must read tech_name or it returns ''.
        """
        persisted, _ = _persist(activity, account, user_a, [_raw('Salesforce')])

        label = SignalDataService._extract_summary(
            persisted[0], is_tech_stack=True,
        )
        assert label == 'Salesforce'

    def test_extract_summary_appends_notes_when_present(
        self, account, activity, user_a,
    ):
        """The "<tool> — <notes>" composition is preserved."""
        persisted, _ = _persist(activity, account, user_a, [_raw('Salesforce')])
        sig = persisted[0]
        sig.notes = 'used by the whole revenue org'
        sig.save(user=user_a, client_id=account.client_id)

        label = SignalDataService._extract_summary(sig, is_tech_stack=True)
        assert label == 'Salesforce — used by the whole revenue org'

    def test_extract_summary_is_empty_without_a_name_or_notes(
        self, account, activity, user_a,
    ):
        sig = TechStackSignal(
            account=account,
            source_activity=activity,
            source=SignalSource.LLM_EXTRACTED,
        )
        sig.save(user=user_a, client_id=account.client_id)

        assert SignalDataService._extract_summary(sig, is_tech_stack=True) == ''
