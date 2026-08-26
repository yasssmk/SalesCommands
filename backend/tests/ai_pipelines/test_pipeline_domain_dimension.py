# backend/tests/ai_pipelines/test_pipeline_domain_dimension.py
"""
DOMAIN vs DIMENSION classification fix (COST bug) -- Volet 1 (prompt).

Observed bug: the objective "reduce operational costs by 15%" was stored with
what=COST (a DIMENSION value) instead of a real DOMAIN code (what=OPS). `what`
is the business AREA (OPS / TECH / DATA / PEOPLE / GROWTH); `dimension` is the
measure axis (TIME / COST / QUALITY / SCALE / RISK). The two lists are disjoint
-- COST is a dimension, never a `what`.

What THIS suite proves (and what it does NOT)
---------------------------------------------
* PROMPT-CONTENT tests assert the tightened instruction the LLM actually reads:
  the shared taxonomy block and each request prompt now carry the sharp
  DOMAIN-vs-DIMENSION rule + the failing few-shot ("reduce operational costs by
  15%" -> what="OPS", dimension="COST"). This is the real Volet-1 proof.

* The PERSISTENCE round-trip test drives the pipeline through the FakeProvider,
  which returns a CANNED reply. It therefore proves the persistence/mapping path
  faithfully stores the domain code the model returns (what="OPS" round-trips to
  ObjectiveSignal.what == "OPS") -- it does NOT exercise the live LLM's choice.
  The live behaviour (the model no longer emitting a dimension word in `what`)
  is verified by PO smoke, not here.

Storage-side validation of an out-of-list `what` (log + exclude) is Volet 2 and
is deliberately NOT implemented yet (pending the PO's exclusion-mechanism call).
"""

import json

import pytest

from app_modules.ai_pipelines.prompts.transcript_signals.context import (
    _build_taxonomy_block,
)
from app_modules.ai_pipelines.prompts.transcript_signals.objective_v1 import (
    build_objective_request,
)
from app_modules.ai_pipelines.prompts.transcript_signals.pain_v1 import (
    build_pain_request,
)
from app_modules.ai_pipelines.prompts.transcript_signals.impact_v1 import (
    build_impact_request,
)
from app_modules.ai_pipelines.prompts.transcript_signals.pain_impact_v1 import (
    build_pain_impact_request,
)


# =============================================================================
# PROMPT-CONTENT — the tightened instruction the LLM actually reads
# =============================================================================

class TestTaxonomyDomainDimensionRule:
    """The shared canonical taxonomy block separates DOMAIN from DIMENSION."""

    @pytest.mark.parametrize(
        'stage', ['objective', 'pain', 'impact', 'pain_impact'],
    )
    def test_taxonomy_states_domain_vs_dimension(self, stage):
        block = _build_taxonomy_block(stage)
        # The DOMAIN codes are exposed WITH their label gloss so the model can
        # map a business area to a code rather than grabbing a surface word.
        assert '"OPS" (Operations / Process)' in block
        assert '"GROWTH" (Growth / Revenue)' in block
        # The hard rule: a dimension word is never a `what`.
        assert 'DOMAIN vs DIMENSION' in block
        assert 'ALWAYS a dimension' in block
        assert 'dimension="COST"' in block

    def test_dimension_codes_still_exposed(self):
        block = _build_taxonomy_block('objective')
        assert '"COST" (Cost / Budget)' in block
        assert '"TIME" (Time / Speed)' in block


class TestRequestPromptsDomainDimensionRule:
    """Every canonical-axis request prompt carries the rule + a few-shot."""

    def _assert_rule_and_fewshot(self, prompt):
        # The rule.
        assert 'DOMAIN vs DIMENSION' in prompt
        assert 'ALWAYS a dimension, NEVER a `what`' in prompt
        # The disambiguating few-shot maps operations+cost to OPS/COST.
        assert 'what="OPS"' in prompt
        assert 'dimension="COST"' in prompt
        # It must never teach a dimension word as a domain.
        assert 'what="COST"' not in prompt

    def test_objective_prompt(self):
        prompt = build_objective_request('SOME TRANSCRIPT')
        self._assert_rule_and_fewshot(prompt)
        # The exact case that failed in production.
        assert 'reduce operational costs by 15%' in prompt

    def test_pain_prompt(self):
        self._assert_rule_and_fewshot(build_pain_request('SOME TRANSCRIPT'))

    def test_impact_prompt(self):
        self._assert_rule_and_fewshot(build_impact_request('SOME TRANSCRIPT'))

    def test_pain_impact_prompt(self):
        # The merged stage is the live pain/impact path (A2).
        self._assert_rule_and_fewshot(
            build_pain_impact_request('SOME TRANSCRIPT')
        )


# =============================================================================
# PERSISTENCE ROUND-TRIP — the domain code the model returns is stored as-is
# =============================================================================

pytestmark_db = pytest.mark.django_db


@pytest.mark.django_db
class TestObjectiveDomainPersistence:
    """
    A canned objective reply with what="OPS", dimension="COST" must persist an
    ObjectiveSignal with what=OPS (a real DOMAIN), dimension=COST -- proving the
    persistence/mapping path keeps the domain code intact. FakeProvider returns
    the canned JSON, so this exercises persistence, NOT the live LLM choice.
    """

    def _run_objective(self, account, activity, user_a, fake_provider, obj):
        from app_modules.ai_pipelines.pipelines.transcript_signals import (
            QualificationSignalsPipeline,
        )
        fake_provider.replies = {
            'objective': json.dumps({'signals': [obj]}),
        }
        result = QualificationSignalsPipeline().run(
            transcript='We want to reduce operational costs by 15% this year.',
            activity=activity,
            user=user_a,
            client_id=account.client_id,
        )
        return result['signals_by_stage']['objective']

    def test_operational_cost_objective_stores_domain_ops_dimension_cost(
        self, account, activity, user_a, fake_provider, patch_active_provider,
    ):
        objectives = self._run_objective(
            account, activity, user_a, fake_provider,
            {
                'what': 'OPS',
                'dimension': 'COST',
                'scope_level': 'BUSINESS',
                'target_department': None,
                'summary': 'Reduce operational costs by 15% this year',
                'source_quote': 'we want to reduce operational costs by 15% this year',
                'confidence': 0.9,
                'is_inferred': False,
            },
        )
        assert len(objectives) == 1
        # DOMAIN kept as the real business-area code -- NOT the dimension word.
        assert objectives[0].what == 'OPS'
        assert objectives[0].dimension == 'COST'
        # canonical_key reflects the correct domain:dimension pair.
        assert objectives[0].canonical_key == 'objective:OPS:COST'
