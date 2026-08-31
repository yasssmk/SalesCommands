# backend/tests/ai_pipelines/test_techstack_extraction_raw_name.py
"""
Tech-stack extraction on the S10 contract: raw name + qualification booleans.

The LLM no longer matches a TechCatalog UUID. It emits the tool name as
free text plus two independent booleans, and the extractor writes them
straight onto the sub-step-1 fields (is_integration was retired -- a
required integration is now a TECHNICAL ConstraintSignal):

    LLM field        ->  TechStackSignal column
    ---------------      ----------------------------------------
    tech_name        ->  tech_name (raw) -> tech_name_normalized
                         (derived by TechStackSignal.save())
    is_competitor    ->  is_competitor
    is_to_replace    ->  is_to_replace

The tech catalogue is gone entirely: nothing on this path references it.

Harness mirrors TestPersistStageBlocker in
tests/ai_pipelines/test_pipeline_extractor_blocker.py:194-249 — the real
`persist_stage()` integration surface the pipeline orchestrator calls,
safety filter and builder chained, no LLM provider involved.
"""

import json

import pytest

from app_modules.ai_pipelines.prompts.transcript_signals.techstack_v1 import (
    build_techstack_request,
)
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

    def test_raw_name_persists_and_is_competitor_no_longer_extracted(
        self, account, activity, user_a,
    ):
        """
        Identity comes from the raw text (no catalogue). The extractor no
        longer POSES is_competitor — and since sub-step 8b the field no longer
        exists at all, so an emitted is_competitor=true cannot land. The
        competitor facet is now a CompetitorSignal from the competitor stage
        (mirror of the earlier is_integration retirement). The persisted
        TechStackSignal simply carries its raw identity.
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
        # And it is what actually landed in the DB.
        sig.refresh_from_db()
        assert sig.tech_name == 'Salesforce'
        assert sig.tech_name_normalized == 'salesforce'
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
        assert sig.is_to_replace is False

    def test_booleans_flow_through_independently(
        self, account, activity, user_a,
    ):
        # Sub-step 5: is_competitor is no longer extracted (stays default
        # False even when the LLM emits it); is_to_replace still flows.
        persisted, _ = _persist(
            activity, account, user_a,
            [_raw('Salesforce', is_competitor=True, is_to_replace=True)],
        )

        sig = persisted[0]
        sig.refresh_from_db()
        assert sig.is_to_replace is True

    def test_to_replace_flows_through(self, account, activity, user_a):
        persisted, _ = _persist(
            activity, account, user_a,
            [_raw('Slack', is_competitor=True, is_to_replace=True)],
        )

        sig = persisted[0]
        sig.refresh_from_db()
        assert sig.is_to_replace is True
        # is_competitor (8b) and is_integration (9c) are no longer fields at
        # all, so an emitted value for either cannot land.

    def test_truthy_non_bool_values_are_coerced(
        self, account, activity, user_a,
    ):
        """An LLM emitting "true"/1 must not land a non-boolean in the DB.
        Coercion is asserted on is_to_replace, the surviving extracted flag
        (is_competitor is no longer extracted -- sub-step 5)."""
        persisted, _ = _persist(
            activity, account, user_a,
            [_raw('Jira', is_to_replace=1, is_competitor=1)],
        )

        sig = persisted[0]
        assert sig.is_to_replace is True
        # is_competitor is not extracted anymore -> stays False regardless.

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
                _raw('salesforce', is_to_replace=True, source_quote='q2'),
            ],
        )

        assert len(persisted) == 1
        # First-occurrence-wins still holds on the surviving flag: the second
        # candidate's is_to_replace does not win. (is_competitor is no longer a
        # field at all — dropped in sub-step 8b — so an emitted value cannot
        # land regardless.)
        assert persisted[0].is_to_replace is False


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


# =============================================================================
# F — CANONICAL TECH NAME (Cluster Tech Stack, sub-step 1: prompt)
# =============================================================================
#
# The prompt now instructs the LLM to emit a CANONICAL, STABLE tech_name so
# the same tool named two ways in one transcript ("HubSpot" / "Hubspot CRM",
# "SFDC" / "Salesforce") comes out under one spelling and collapses to a
# single signal on the activity.
#
# What these tests prove (mirrors the COST-bug precedent in
# test_pipeline_domain_dimension.py):
#   * PROMPT-CONTENT (TestCanonicalNamePromptContent) asserts the tightened
#     instruction the LLM actually reads — the canonical rule + the few-shot.
#     This is the real sub-step-1 proof and the non-vacuity target: mutate
#     the instruction in techstack_v1.py and this class goes red.
#   * The PIPELINE ROUND-TRIP (TestCanonicalNameCollapsesToOneSignal) drives
#     the REAL extraction path (QualificationSignalsPipeline.run through the
#     FakeProvider) with two emissions the hardened prompt would produce —
#     both already canonical to "HubSpot" — and proves the activity ends with
#     exactly ONE tech signal. FakeProvider returns a CANNED reply, so this
#     exercises the extraction/dedup path, NOT the live LLM's naming choice.
#     The live behaviour (the model actually canonicalising) is PO smoke.


class TestCanonicalNamePromptContent:
    """
    The techstack request prompt carries the canonical-name rule + few-shot.

    Non-vacuity: this is the class that must re-red when the canonical
    instruction is mutated out of techstack_v1.py.
    """

    def _prompt(self):
        return build_techstack_request('SOME TRANSCRIPT')

    def test_prompt_instructs_a_canonical_stable_name(self):
        prompt = self._prompt()
        assert 'CANONICAL name' in prompt
        assert 'official product name' in prompt
        # The stable-spelling intent is stated, not just implied.
        assert 'official, stable casing' in prompt

    def test_prompt_drops_speaker_appended_descriptors(self):
        prompt = self._prompt()
        # The "descriptor is not part of the product name" rule + its example.
        assert '"HubSpot CRM" -> "HubSpot"' in prompt
        assert '"Salesforce CRM" ->' in prompt

    def test_prompt_resolves_unambiguous_acronyms(self):
        prompt = self._prompt()
        assert '"SFDC" -> "Salesforce"' in prompt

    def test_prompt_ties_two_spellings_to_one_name(self):
        prompt = self._prompt()
        # The core cluster guarantee: same tool named twice -> same tech_name.
        assert 'the SAME tool is named several ways' in prompt
        assert 'the SAME canonical' in prompt

    def test_prompt_keeps_verbatim_when_ambiguous_or_unknown(self):
        prompt = self._prompt()
        # The prudence rule: no invented mapping.
        assert 'Stay verbatim when unsure' in prompt
        assert 'inventing a mapping' in prompt
        # The in-house / unknown few-shot keeps the raw name.
        assert 'Pyramid' in prompt

    def test_prompt_no_longer_teaches_the_old_verbatim_rule(self):
        """The old 'name as it appears / do not expand abbreviations' rule
        is gone — it directly contradicts canonicalisation."""
        prompt = self._prompt()
        assert 'do not expand abbreviations' not in prompt
        assert 'Emit the tool name as it appears in the transcript' not in prompt


@pytest.mark.django_db
class TestCanonicalNameCollapsesToOneSignal:
    """
    Real extraction path: when the model emits the SAME canonical tech_name
    for two mentions of one tool, the activity ends with ONE tech signal.

    Drives QualificationSignalsPipeline.run through the FakeProvider (the
    same harness the orchestration tests use), so persist_stage + the
    normalised-name dedup run exactly as in production.
    """

    def _techstack_reply(self, emissions):
        return json.dumps({'signals': emissions})

    def _run(self, account, activity, user_a, fake_provider, emissions):
        from app_modules.ai_pipelines.pipelines.transcript_signals import (
            QualificationSignalsPipeline,
        )
        fake_provider.replies = {
            'techstack': self._techstack_reply(emissions),
        }
        result = QualificationSignalsPipeline().run(
            transcript=(
                'We run everything on Hubspot. Honestly our HubSpot CRM '
                'is a bit of a mess right now.'
            ),
            activity=activity,
            user=user_a,
            client_id=account.client_id,
        )
        return result['signals_by_stage']['techstack']

    def test_two_canonical_emissions_of_one_tool_make_one_signal(
        self, account, activity, user_a, fake_provider, patch_active_provider,
    ):
        # What the hardened prompt is expected to produce: both mentions
        # already canonicalised to "HubSpot", each with its own quote.
        tech_signals = self._run(
            account, activity, user_a, fake_provider,
            [
                {
                    'tech_name': 'HubSpot',
                    'is_competitor': False,
                    'is_integration': False,
                    'is_to_replace': False,
                    'usage_scope': 'COMPANY',
                    'source_quote': 'We run everything on Hubspot',
                    'confidence': 0.9,
                    'is_inferred': False,
                },
                {
                    'tech_name': 'HubSpot',
                    'is_competitor': False,
                    'is_integration': False,
                    'is_to_replace': False,
                    'usage_scope': 'COMPANY',
                    'source_quote': 'our HubSpot CRM is a bit of a mess',
                    'confidence': 0.9,
                    'is_inferred': False,
                },
            ],
        )

        # One tool -> one signal on the activity.
        assert len(tech_signals) == 1
        sig = tech_signals[0]
        assert sig.tech_name == 'HubSpot'
        assert sig.tech_name_normalized == 'hubspot'
        assert sig.source_activity_id == activity.id
        # The corroborating second quote is preserved, not lost.
        assert sig.metadata['additional_quotes'] == [
            'our HubSpot CRM is a bit of a mess'
        ]

    def test_two_distinct_tools_stay_two_signals(
        self, account, activity, user_a, fake_provider, patch_active_provider,
    ):
        """Guard: canonicalisation must not over-collapse distinct tools."""
        tech_signals = self._run(
            account, activity, user_a, fake_provider,
            [
                {
                    'tech_name': 'HubSpot',
                    'usage_scope': 'COMPANY',
                    'source_quote': 'We run everything on Hubspot',
                    'confidence': 0.9,
                    'is_inferred': False,
                },
                {
                    'tech_name': 'Salesforce',
                    'usage_scope': 'COMPANY',
                    'source_quote': 'Sales lives in Salesforce',
                    'confidence': 0.9,
                    'is_inferred': False,
                },
            ],
        )

        assert len(tech_signals) == 2
        assert sorted(s.tech_name for s in tech_signals) == [
            'HubSpot', 'Salesforce',
        ]
