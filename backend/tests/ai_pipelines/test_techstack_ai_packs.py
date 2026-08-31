# backend/tests/ai_pipelines/test_techstack_ai_packs.py
"""
The AI packs read tech identity + qualification off the SIGNAL (S10).

Both LLM-facing packs used to compose the tool label and the commercial
flags from the TechCatalog FK:

    catalog_name          <- str(signal.tech_catalog_entry)
    is_competitor         <- the catalogue row's flag
    is_integration_target <- the catalogue row's flag

Since sub-step 2 the extractor never populates that FK, so those three
emitted None / False / False on every extracted tech signal — the tool
name disappeared from the deal-health diagnostic and the prep-call
competitive context.

They now read the signal's own columns, and gain the third qualification
axis the catalogue never had:

    tech_name       <- signal.tech_name        (raw, as observed)
    is_competitor   <- signal.is_competitor
    is_integration  <- signal.is_integration
    is_to_replace   <- signal.is_to_replace    (NEW in the packs)

`canonical_key` is dropped from the tech evidence: TechStack is not
clusterable, so it was always None.

Fixture imports mirror tests/ai_pipelines/test_deal_health_evidence_builder.py
(:29-49) and test_prep_call_input_pack.py (:11-33), which both re-export
the decision_cycles conftest fixtures.
"""

import pytest

from tests.decision_cycles.conftest import (  # noqa: F401
    pytest_configure,
    _jwt_only_no_csrf,
    tenant_a_id,
    client_account_a,
    role_individual_a,
    user_a,
    account,
    activity,
    contact,
    api,
    authenticate,
    authed_api_a,
    cache_invalidation_calls,
    cycle,
    five_steps,
)

from app_modules.ai_pipelines.services.deal_health_evidence_builder import (
    DealHealthEvidenceBuilder,
)
from app_modules.ai_pipelines.services.prep_call.input_pack_assembler import (
    PrepInputPackAssembler,
)
from app_modules.signals.constants import SignalSource, SignalStatus


pytestmark = pytest.mark.django_db


# =============================================================================
# FIXTURES / FACTORY
# =============================================================================

def _create_tech(dc, user, client_id, tech_name='Salesforce', **flags):
    """
    A VALIDATED TechStackSignal on the cycle, carrying its identity on
    the column and NO catalogue entry — the shape the extractor now
    produces.

    Mirrors the _create_pain / _create_objective factory style in
    tests/ai_pipelines/test_deal_health_evidence_builder.py:60-75.
    """
    from app_modules.signals.models import TechStackSignal

    sig = TechStackSignal(
        account=dc.account,
        decision_cycle=dc,
        source=SignalSource.MANUAL,
        status=SignalStatus.VALIDATED,
        tech_name=tech_name,
        source_quote=f'They run everything on {tech_name}',
        is_integration=flags.get('is_integration', False),
        is_to_replace=flags.get('is_to_replace', False),
    )
    sig.save(user=user, client_id=client_id)
    return sig


def _create_competitor(dc, user, client_id, competitor_name='Intercom'):
    """
    A VALIDATED CompetitorSignal on the cycle (the detached competitor
    signal, sub-step 1). source=MANUAL -> save() forces VALIDATED and
    derives competitor_name_normalized.
    """
    from app_modules.signals.models import CompetitorSignal

    sig = CompetitorSignal(
        account=dc.account,
        decision_cycle=dc,
        source=SignalSource.MANUAL,
        status=SignalStatus.VALIDATED,
        competitor_name=competitor_name,
        summary=f'Prospect weighing {competitor_name} against us',
    )
    sig.save(user=user, client_id=client_id)
    return sig


@pytest.fixture
def activity_with_cycle(db, account, cycle, user_a):
    """Mirror of the fixture in test_prep_call_input_pack.py:39-53."""
    from app_modules.activities.models import Activity
    from app_modules.activities.constants import ActivityType, ActivityStatus

    a = Activity(
        title='Demo call',
        activity_type=ActivityType.CALL,
        status=ActivityStatus.PLANNED,
        account=account,
        owner=user_a,
        decision_cycle=cycle,
    )
    a.save(user=user_a, client_id=account.client_id)
    return a


# =============================================================================
# A — DEAL-HEALTH EVIDENCE
# =============================================================================

class TestDealHealthTechEvidence:

    def test_tech_name_and_flags_come_from_the_signal(
        self, cycle, user_a,
    ):
        """
        The red-repro case: a competitor the account wants to replace,
        with no catalogue entry, must reach the evidence pack with its
        name and both flags.
        """
        # Sub-step 4: the competitor marker now comes from a matching
        # CompetitorSignal, not the techstack is_competitor flag.
        _create_tech(
            cycle, user_a, cycle.client_id,
            tech_name='Salesforce',
            is_to_replace=True,
        )
        _create_competitor(cycle, user_a, cycle.client_id, competitor_name='Salesforce')

        pack = DealHealthEvidenceBuilder().build(cycle)
        tech = pack['signals']['techstack']

        assert len(tech) == 1
        assert tech[0]['tech_name'] == 'Salesforce'
        assert tech[0]['is_competitor'] is True
        assert tech[0]['is_to_replace'] is True
        assert tech[0]['is_integration'] is False

    def test_all_three_flags_are_emitted_independently(self, cycle, user_a):
        # is_competitor now reflects a matching CompetitorSignal; the other
        # two flags still come off the tech row.
        _create_tech(
            cycle, user_a, cycle.client_id,
            tech_name='Slack',
            is_integration=True,
            is_to_replace=True,
        )
        _create_competitor(cycle, user_a, cycle.client_id, competitor_name='Slack')

        tech = DealHealthEvidenceBuilder().build(cycle)['signals']['techstack'][0]
        assert (
            tech['is_competitor'],
            tech['is_integration'],
            tech['is_to_replace'],
        ) == (True, True, True)

    def test_just_used_tool_still_appears_with_all_flags_false(
        self, cycle, user_a,
    ):
        """A tool with no commercial angle is still evidence."""
        _create_tech(cycle, user_a, cycle.client_id, tech_name='Notion')

        tech = DealHealthEvidenceBuilder().build(cycle)['signals']['techstack'][0]
        assert tech['tech_name'] == 'Notion'
        assert tech['is_competitor'] is False
        assert tech['is_integration'] is False
        assert tech['is_to_replace'] is False

    def test_catalogue_keys_and_canonical_key_are_gone(self, cycle, user_a):
        """
        The old FK-derived keys must not survive: leaving them would keep
        feeding None / False into the diagnostic prompt.
        """
        _create_tech(cycle, user_a, cycle.client_id)

        tech = DealHealthEvidenceBuilder().build(cycle)['signals']['techstack'][0]
        assert 'catalog_name' not in tech
        assert 'is_integration_target' not in tech
        assert 'canonical_key' not in tech

    def test_unchanged_evidence_fields_are_preserved(self, cycle, user_a):
        """source_quote / on_deal / usage_departments keep working."""
        _create_tech(cycle, user_a, cycle.client_id, tech_name='Zendesk')

        tech = DealHealthEvidenceBuilder().build(cycle)['signals']['techstack'][0]
        assert tech['source_quote'] == 'They run everything on Zendesk'
        assert tech['on_deal'] is True
        # WHO uses the tool is now the multi-department list (mono -> multi).
        # The legacy single `usage_department` key is retired from the pack.
        assert tech['usage_departments'] == []
        assert 'usage_department' not in tech
        assert tech['summary'] == ''

    def test_raw_spelling_is_preserved_not_normalised(self, cycle, user_a):
        """The pack shows the rep/LLM wording, not the grouping key."""
        _create_tech(cycle, user_a, cycle.client_id, tech_name='Salesforce CRM')

        tech = DealHealthEvidenceBuilder().build(cycle)['signals']['techstack'][0]
        assert tech['tech_name'] == 'Salesforce CRM'


# =============================================================================
# B — DEAL-HEALTH PROMPT RENDERING
# =============================================================================

class TestDealHealthPromptRendering:

    def test_prompt_renders_the_tool_name_and_qualifications(
        self, cycle, user_a,
    ):
        """
        diagnostic_v1._format_signal reads the pack keys directly — a
        rename that stopped at the builder would silently blank the
        "Tool:" line out of the prompt.
        """
        from app_modules.ai_pipelines.prompts.deal_health.diagnostic_v1 import (
            _format_signal,
        )

        # "Competitor: yes" now derives from a matching CompetitorSignal.
        _create_tech(
            cycle, user_a, cycle.client_id,
            tech_name='Salesforce',
            is_to_replace=True,
        )
        _create_competitor(cycle, user_a, cycle.client_id, competitor_name='Salesforce')
        tech = DealHealthEvidenceBuilder().build(cycle)['signals']['techstack'][0]

        rendered = _format_signal('techstack', tech)

        assert 'Tool: Salesforce' in rendered
        assert 'Competitor: yes' in rendered
        assert 'To replace: yes' in rendered

    def test_prompt_omits_flags_that_are_false(self, cycle, user_a):
        from app_modules.ai_pipelines.prompts.deal_health.diagnostic_v1 import (
            _format_signal,
        )

        _create_tech(cycle, user_a, cycle.client_id, tech_name='Notion')
        tech = DealHealthEvidenceBuilder().build(cycle)['signals']['techstack'][0]

        rendered = _format_signal('techstack', tech)

        assert 'Tool: Notion' in rendered
        assert 'Competitor: yes' not in rendered
        assert 'To replace: yes' not in rendered
        assert 'Integration: yes' not in rendered

    def test_prompt_renders_integration_flag(self, cycle, user_a):
        from app_modules.ai_pipelines.prompts.deal_health.diagnostic_v1 import (
            _format_signal,
        )

        _create_tech(
            cycle, user_a, cycle.client_id,
            tech_name='HubSpot', is_integration=True,
        )
        tech = DealHealthEvidenceBuilder().build(cycle)['signals']['techstack'][0]

        assert 'Integration: yes' in _format_signal('techstack', tech)


# =============================================================================
# C — PREP-CALL INPUT PACK
# =============================================================================

class TestPrepCallTechSerialization:

    def test_serialized_tech_carries_name_and_to_replace_only(
        self, cycle, user_a,
    ):
        from app_modules.signals.models import TechStackSignal

        _create_tech(
            cycle, user_a, cycle.client_id,
            tech_name='Salesforce',
            is_to_replace=True,
        )

        rows = PrepInputPackAssembler._serialize_techstack_signals(
            TechStackSignal.objects.filter(decision_cycle=cycle)
        )

        assert len(rows) == 1
        assert rows[0]['tech_name'] == 'Salesforce'
        assert rows[0]['is_to_replace'] is True
        # is_competitor is NO LONGER surfaced: the competitor facet is the
        # CompetitorSignal now, and the manual tech flag has been retired.
        assert 'is_competitor' not in rows[0]
        # is_integration is NOT surfaced either (retired earlier; TECHNICAL
        # constraint captures a required integration).
        assert 'is_integration' not in rows[0]
        assert 'catalog_name' not in rows[0]
        assert 'is_integration_target' not in rows[0]


class TestPrepCallCompetitiveContext:

    def _pack(self, activity_with_cycle, contact):
        return PrepInputPackAssembler().build(
            activity=activity_with_cycle,
            target_contact=contact,
            brief_mode='CONVICTION',
        )

    def test_competitor_lands_in_competing_on_deal(
        self, activity_with_cycle, contact, cycle, user_a,
    ):
        # Sub-step 4: a competitor is a CompetitorSignal, not a techstack flag.
        _create_competitor(cycle, user_a, cycle.client_id, competitor_name='Salesforce')

        comp = self._pack(activity_with_cycle, contact)['competitive_context']

        assert [c['tool'] for c in comp['competing_on_deal']] == ['Salesforce']
        # No TechStackSignal on the DC -> no incumbents.
        assert comp['incumbents'] == []

    def test_non_competitor_lands_in_incumbents(
        self, activity_with_cycle, contact, cycle, user_a,
    ):
        _create_tech(cycle, user_a, cycle.client_id, tech_name='Notion')

        comp = self._pack(activity_with_cycle, contact)['competitive_context']

        assert [c['tool'] for c in comp['incumbents']] == ['Notion']
        assert comp['competing_on_deal'] == []

    def test_to_replace_tools_are_surfaced_as_their_own_bucket(
        self, activity_with_cycle, contact, cycle, user_a,
    ):
        """
        The qualification the catalogue never carried: a tool the account
        intends to drop is an open door, whether or not we compete with it.
        """
        _create_tech(
            cycle, user_a, cycle.client_id,
            tech_name='Zendesk', is_to_replace=True,
        )

        comp = self._pack(activity_with_cycle, contact)['competitive_context']

        assert [c['tool'] for c in comp['to_replace']] == ['Zendesk']

    def test_a_tool_can_be_competitor_and_to_replace(
        self, activity_with_cycle, contact, cycle, user_a,
    ):
        # The competitor facet is a CompetitorSignal; the to_replace facet
        # stays on the techstack row. The same tool can be both.
        _create_competitor(cycle, user_a, cycle.client_id, competitor_name='Salesforce')
        _create_tech(
            cycle, user_a, cycle.client_id,
            tech_name='Salesforce', is_to_replace=True,
        )

        comp = self._pack(activity_with_cycle, contact)['competitive_context']

        assert [c['tool'] for c in comp['competing_on_deal']] == ['Salesforce']
        assert [c['tool'] for c in comp['to_replace']] == ['Salesforce']

    def test_empty_when_no_tech_signals(self, activity_with_cycle, contact):
        comp = self._pack(activity_with_cycle, contact)['competitive_context']

        assert comp['incumbents'] == []
        assert comp['competing_on_deal'] == []
        assert comp['to_replace'] == []


class TestPrepCallPromptRendering:

    def test_context_renders_tool_names(
        self, activity_with_cycle, contact, cycle, user_a,
    ):
        """
        prompts/prep_call/context.py formats competitive_context — it
        must keep printing a real tool name, not "unknown".
        """
        from app_modules.ai_pipelines.prompts.prep_call.context import (
            build_context_layer,
        )

        # Competitor facet -> CompetitorSignal; incumbents/to_replace -> techstack.
        _create_competitor(cycle, user_a, cycle.client_id, competitor_name='Salesforce')
        _create_tech(cycle, user_a, cycle.client_id, tech_name='Notion')
        _create_tech(
            cycle, user_a, cycle.client_id,
            tech_name='Zendesk', is_to_replace=True,
        )

        pack = PrepInputPackAssembler().build(
            activity=activity_with_cycle,
            target_contact=contact,
            brief_mode='CONVICTION',
        )
        rendered = build_context_layer(pack, 'CONVICTION')

        assert 'Competitor on deal: Salesforce' in rendered
        assert 'Incumbent: Notion' in rendered
        assert 'To replace: Zendesk' in rendered
        assert 'unknown' not in rendered


# =============================================================================
# D — RECABLING: competitor facet reads CompetitorSignal (sub-step 4)
# =============================================================================

class TestPrepCallCompetitorFromCompetitorSignal:
    """
    competing_on_deal is sourced from CompetitorSignal (DC + VALIDATED),
    NOT from TechStackSignal.is_competitor. incumbents is every VALIDATED
    TechStackSignal on the DC, independent of the (now unused) flag.
    """

    def _pack(self, activity_with_cycle, contact):
        return PrepInputPackAssembler().build(
            activity=activity_with_cycle,
            target_contact=contact,
            brief_mode='CONVICTION',
        )

    def test_competing_on_deal_comes_from_competitor_signal(
        self, activity_with_cycle, contact, cycle, user_a,
    ):
        # A competitor lives as a CompetitorSignal (not a techstack flag).
        _create_competitor(cycle, user_a, cycle.client_id, competitor_name='Intercom')
        # A merely-used tool is a techstack row (is_competitor stays False).
        _create_tech(cycle, user_a, cycle.client_id, tech_name='Zendesk')

        comp = self._pack(activity_with_cycle, contact)['competitive_context']

        assert [c['tool'] for c in comp['competing_on_deal']] == ['Intercom']
        # incumbents = the account's tooling on the DC, without any is_competitor logic.
        assert [c['tool'] for c in comp['incumbents']] == ['Zendesk']


class TestDealHealthCompetitorFromCompetitorSignal:
    """
    The deal-health "Competitor: yes" marker reflects the EXISTENCE of a
    CompetitorSignal (DC + VALIDATED) matching the tool, not the techstack
    is_competitor flag.
    """

    def test_competitor_marker_comes_from_competitor_signal(
        self, cycle, user_a,
    ):
        from app_modules.ai_pipelines.prompts.deal_health.diagnostic_v1 import (
            _format_signal,
        )
        # A merely-used tool (no manual competitor flag exists anymore) ...
        _create_tech(
            cycle, user_a, cycle.client_id,
            tech_name='Salesforce',
        )
        # ... but a CompetitorSignal names it as a competitor on this deal.
        _create_competitor(cycle, user_a, cycle.client_id, competitor_name='Salesforce')

        tech = DealHealthEvidenceBuilder().build(cycle)['signals']['techstack'][0]
        rendered = _format_signal('techstack', tech)

        assert 'Competitor: yes' in rendered
