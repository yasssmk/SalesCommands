# backend/tests/ai_pipelines/test_techstack_prompt_v5.py
"""
Sprint TechStack T4c — techstack prompt v5 (PO smoke on T4b, Nordline).

PO decision: EVERY tool used in a process of the prospect is tech stack,
generic tools (Excel, Google Sheets, email, phone) and manual means (paper,
whiteboard, notebook) included -- the aim is to understand everything the
prospect's process runs on. Generic / manual means are named as said; usage
and lifecycle follow the usual rules (not said -> UNKNOWN / null).

renewal_date is filled ONLY when a renewal is explicitly said; a stop date is
NEVER a renewal date.

The examples must not come from the Nordline smoke transcript, which stays a
test the prompt has never seen.

These tests prove the TEXT sent to the model (and that the builder keeps a
generic / manual tool), not the LLM behaviour.
"""

import pytest

from app_modules.ai_pipelines.prompts.transcript_signals.techstack_v1 import (
    TECHSTACK_PROMPT_VERSION,
    build_techstack_request,
)
from app_modules.ai_pipelines.services.transcript_signal_extractor import (
    TranscriptSignalExtractor,
)


pytestmark = pytest.mark.django_db


def _flat(text):
    """Whitespace-normalised text: phrase assertions survive the line wrap."""
    return ' '.join(text.split())


@pytest.fixture
def prompt():
    return _flat(build_techstack_request('transcript'))


def test_version_is_v5():
    assert TECHSTACK_PROMPT_VERSION == 'v5'


# =============================================================================
# 1 — every tool used in a process, generic and manual included
# =============================================================================

class TestGenericAndManualToolsAreTechStack:

    def test_explicit_rule(self, prompt):
        assert (
            'EVERY tool the prospect uses in a process is tech stack, '
            'including GENERIC tools (Excel, Google Sheets, email, phone) and '
            'MANUAL means (paper, whiteboard, notebook)'
        ) in prompt

    def test_no_rule_restricts_to_a_specific_software_product(self, prompt):
        assert 'specific tool, software, or product' not in prompt
        assert 'CURRENT usage of a specific tool' not in prompt

    def test_generic_and_manual_means_are_named_as_said(self, prompt):
        assert (
            'A generic or manual means is named AS SAID, capitalised, never '
            'expanded or mapped to a product'
        ) in prompt
        assert '"Excel" (not "Microsoft Excel")' in prompt

    def test_usage_and_lifecycle_follow_the_usual_rules(self, prompt):
        assert (
            'Usage and lifecycle follow the same rules as for any tool '
            '(not said -> "UNKNOWN" / null)'
        ) in prompt

    @pytest.mark.parametrize('example', [
        '« On suit les commandes dans un Google Sheet. » -> "tech_name": "Google Sheets"',
        '« Les bons de livraison sont encore sur papier. » -> "tech_name": "Papier"',
        '« Le planning de l\'atelier est sur un tableau blanc. » -> "tech_name": "Tableau blanc"',
        '« La compta fait ses rapprochements dans Excel. » -> "tech_name": "Excel"',
        '« Les clients passent commande par téléphone. » -> "tech_name": "Téléphone"',
    ])
    def test_varied_examples(self, example, prompt):
        assert example in prompt


class TestBuilderKeepsGenericAndManualTools:

    @pytest.mark.parametrize('name', ['Papier', 'Tableau blanc', 'Excel', 'Téléphone'])
    def test_generic_or_manual_tool_is_persisted_as_said(
        self, name, account, activity, user_a,
    ):
        persisted, _ = TranscriptSignalExtractor().persist_stage(
            stage='techstack',
            raw_signals=[{
                'tech_name': name, 'usage_scope': 'UNKNOWN',
                'usage_departments': [], 'source_quote': f'on fait ça sur {name}',
                'confidence': 0.9, 'is_inferred': False,
            }],
            activity=activity, user=user_a, client_id=account.client_id,
            confidence_min=0.5, drop_inferred=True,
        )
        assert [s.tech_name for s in persisted] == [name]


# =============================================================================
# 2 — renewal only when said; a stop date is never a renewal date
# =============================================================================

class TestRenewalIsNeverAStopDate:

    def test_renewal_only_when_explicitly_said(self, prompt):
        assert (
            '"renewal_date" -- ONLY when a RENEWAL is explicitly said'
        ) in prompt

    def test_a_stop_date_is_never_a_renewal_date(self, prompt):
        assert (
            'A stop / end / termination date is NEVER a renewal date: it goes '
            'to "discontinued_date", and "renewal_date" stays null'
        ) in prompt

    def test_stop_date_example(self, prompt):
        assert (
            '« On résilie notre abonnement Mailchimp fin mars. » -> '
            '"is_discontinued": true, "discontinued_date": "<conversation year>-03-31", '
            '"renewal_date": null'
        ) in prompt

    def test_renewal_example(self, prompt):
        assert (
            '« Le contrat DocuSign se renouvelle le 1er septembre. » -> '
            '"renewal_date": "<conversation year>-09-01", "is_discontinued": false'
        ) in prompt


# =============================================================================
# 3 — nothing taken from the Nordline smoke transcript
# =============================================================================

@pytest.mark.parametrize('smoke_fact', ['Nordline', 'Freshdesk', '30 novembre', '11-30'])
def test_no_example_comes_from_the_nordline_smoke(smoke_fact):
    assert smoke_fact not in build_techstack_request('transcript')
