# backend/tests/ai_pipelines/conftest.py
"""
Pytest fixtures for the ai_pipelines module tests.

This conftest sits next to the test files for ai_pipelines and
COMPLEMENTS the fixtures declared in backend/tests/signals/conftest.py.
We deliberately do NOT re-declare the tenant / user / account /
activity / contact fixtures here -- they live in
backend/tests/signals/conftest.py and pytest discovers them through
the shared parent (`backend/tests/`) when both packages import.

Concretely, the signals conftest also handles:
  * the sqlite OPTIONS strip (pytest_configure hook)
  * the JWT-only / no-CSRF settings autouse fixture
  * APIClient + authenticate helper
  * the cache_invalidation_calls spy

To benefit from those fixtures inside ai_pipelines tests we
re-export them here. pytest-django merges fixture namespaces
automatically when conftest files share an ancestor directory, but
import-side-effect imports of fixture symbols are the cleanest way
to make the re-use explicit.

What lives HERE (ai_pipelines-specific):
  * fake_provider -- a fake LLMProvider that CAPTURES every payload
    sent to .call() (system, user, temperature, model, max_tokens,
    timeout_s) AND returns a pre-canned LLMCallResult per stage.
    Used to assert prompt structure per stage AND to drive deterministic
    pipeline orchestration tests.

  * patch_active_provider -- a fixture that monkeypatches
    get_active_provider so BasePipeline.__init__ resolves to the
    fake_provider instance without each test having to pass
    `provider=...` to the pipeline constructor.

Why FakeProvider captures the payload
-------------------------------------
A pure return-mock provider would let prompt-structure regressions
slip silently (e.g. someone deletes the context layer call -- tests
still pass because the LLM "would have" returned the same fake JSON).
Capturing the payload lets the orchestration tests assert that:

  * For each stage, the system prompt is non-empty.
  * The user prompt contains the transcript verbatim.
  * The user prompt contains stage-specific request markers (TASK
    keyword, stage name).
  * The temperature is what the pipeline declared (0.0).

The captured payloads are exposed on `fake_provider.calls`, a list of
dicts in call order: [{stage_inferred_from_user_prompt: str, system:
str, user: str, temperature: float, model: str, max_tokens: int,
timeout_s: int, ...}].
"""

import pytest

# Re-export the signals conftest fixtures used by ai_pipelines tests.
# pytest-django picks them up through the shared parent package, but
# the explicit imports document the dependency and make IDE jump-to
# work for our tests.
from tests.signals.conftest import (  # noqa: F401
    pytest_configure,
    _jwt_only_no_csrf,
    tenant_a_id,
    tenant_b_id,
    client_account_a,
    client_account_b,
    role_individual_a,
    role_individual_b,
    user_a,
    user_b,
    account,
    other_tenant_account,
    activity,
    other_tenant_activity,
    contact,
    contact_extra,
    api,
    authenticate,
    authed_api_a,
    authed_api_b,
    cache_invalidation_calls,
)


# =============================================================================
# FAKE LLM PROVIDER
# =============================================================================

class FakeProvider:
    """
    Test double for LLMProvider used by the QualificationSignalsPipeline
    tests.

    Behaviour:
      * Records every .call() invocation in `self.calls` (a list of
        dicts in call order). Each entry captures the full kwargs
        passed by BasePipeline._call_llm so tests can assert the
        prompt structure for each stage.

      * Returns a pre-canned LLMCallResult content per stage. The
        stage is inferred from a marker in the user prompt -- each
        stage's request builder embeds a distinctive TASK header
        ("Extract PAIN signals", "Extract OBJECTIVE signals", ...)
        which the provider scans to pick the right reply.

      * If `raise_per_stage` declares an exception for the current
        stage, it is raised instead of returning content. Used to
        drive PARTIAL / TIMEOUT / PARSE_ERROR / LLM_ERROR scenarios.

    Construction:
        FakeProvider(replies={'pain': '...JSON...', 'blocker': '...'},
                     raise_per_stage={'techstack': LLMTimeoutError('x')})

    Replies default to "{\\"signals\\": []}" for any stage not declared
    -- this makes the happy-path test setup terse (only specify the
    stages you actually care about for that test) and prevents
    accidental cross-contamination between tests.
    """

    # Marker substring -> stage name. Kept in sync with the TASK header
    # of each prompt request builder. The first 5 markers belong to the
    # transcript_signals/ family (QualificationSignalsPipeline); the
    # last belongs to the next_steps/ family (NextStepsPipeline, B4).
    _STAGE_MARKERS = (
        # A2: the merged pain+impact stage. Listed FIRST and its header
        # ("Extract PAIN and IMPACT signals") deliberately does not contain
        # the legacy "Extract PAIN signals" / "Extract IMPACT signals"
        # substrings, so inference maps it to 'pain_impact', not a legacy
        # stage.
        ('Extract PAIN and IMPACT signals', 'pain_impact'),
        ('Extract PAIN signals',       'pain'),
        ('Extract OBJECTIVE signals',  'objective'),
        ('Extract IMPACT signals',     'impact'),
        ('Extract TECH STACK signals', 'techstack'),
        ('Extract BLOCKER signals',    'blocker'),
        ('Extract CONSTRAINT signals', 'constraint'),
        ('Extract COMPETITOR signals', 'competitor'),
        ('Extract NEXT-STEP signals',  'next_steps'),
    )

    _EMPTY_REPLY = '{"signals": []}'

    def __init__(self, replies=None, raise_per_stage=None):
        self.replies = dict(replies or {})
        self.raise_per_stage = dict(raise_per_stage or {})
        self.calls = []

    # -------------------------------------------------------------------------
    # PROVIDER INTERFACE
    # -------------------------------------------------------------------------

    def call(self, *, system, user, temperature, model, max_tokens, timeout_s):
        """
        Matches LLMProvider.call(...) signature.

        Returns:
            LLMCallResult with the canned content for the inferred stage.

        Raises:
            Whatever was declared in `raise_per_stage[stage]` (typically
            one of the providers/base.py exception classes).
        """
        from app_modules.ai_pipelines.providers.base import LLMCallResult

        stage = self._infer_stage(user)

        call_record = {
            'stage':       stage,
            'system':      system,
            'user':        user,
            'temperature': temperature,
            'model':       model,
            'max_tokens':  max_tokens,
            'timeout_s':   timeout_s,
        }
        self.calls.append(call_record)

        # Raise per-stage exception if configured -- BEFORE returning.
        if stage in self.raise_per_stage:
            raise self.raise_per_stage[stage]

        content = self.replies.get(stage, self._EMPTY_REPLY)

        return LLMCallResult(
            content=content,
            input_tokens=42,
            output_tokens=24,
            model_used=model,
            duration_ms=10,
        )

    # -------------------------------------------------------------------------
    # HELPERS FOR TESTS
    # -------------------------------------------------------------------------

    def calls_for(self, stage):
        """Return the subset of self.calls whose inferred stage matches."""
        return [c for c in self.calls if c['stage'] == stage]

    def stages_in_order(self):
        """Return the ordered list of stages invoked."""
        return [c['stage'] for c in self.calls]

    # -------------------------------------------------------------------------
    # INTERNAL -- STAGE INFERENCE
    # -------------------------------------------------------------------------

    def _infer_stage(self, user_prompt):
        """
        Scan the user prompt for a known TASK marker and return the
        matching stage name. Falls back to 'unknown' (the test that
        triggered this will fail loudly on the assertion).
        """
        for marker, stage in self._STAGE_MARKERS:
            if marker in user_prompt:
                return stage
        return 'unknown'


@pytest.fixture
def fake_provider():
    """Default empty-reply provider; tests configure replies on demand."""
    return FakeProvider()


@pytest.fixture
def patch_active_provider(monkeypatch, fake_provider):
    """
    Monkeypatch get_active_provider so BasePipeline.__init__ resolves
    to the fake provider when no `provider=...` kwarg is passed.

    Both the providers package and pipelines/base.py imported
    get_active_provider at module load time; we patch BOTH binding
    sites to be safe.
    """
    from app_modules.ai_pipelines import providers as providers_pkg
    from app_modules.ai_pipelines.pipelines import base as base_pipeline_module

    monkeypatch.setattr(
        providers_pkg, 'get_active_provider', lambda: fake_provider,
    )
    monkeypatch.setattr(
        base_pipeline_module, 'get_active_provider', lambda: fake_provider,
    )
    return fake_provider


# =============================================================================
# CANNED LLM REPLIES -- shared seed data for happy-path stages
# =============================================================================

# A minimal LLM payload per stage that the safety filter accepts
# (confidence = 0.9 >= 0.5; is_inferred = false). Used by orchestration
# tests that want a "everything succeeded" baseline without hand-rolling
# JSON per test.
CANNED_REPLIES_HAPPY = {
    # A2: the merged pain+impact stage returns ONE object with two arrays.
    # One pain + one impact so the happy-path run persists 1 of each into
    # the separate 'pain' / 'impact' response keys.
    'pain_impact': (
        '{"pains": [{'
        '"what": "OPS", '
        '"dimension": "TIME", '
        '"scope_level": "BUSINESS", '
        '"target_department": null, '
        '"summary": "Reporting takes 3 weeks", '
        '"source_quote": "Our reporting takes 3 weeks", '
        '"confidence": 0.9, '
        '"is_inferred": false'
        '}], "impacts": [{'
        '"what": "OPS", '
        '"dimension": "TIME", '
        '"impact_type": "TIME", '
        '"scope_level": "BUSINESS", '
        '"target_department": null, '
        '"summary": "Managers spend 5h/week on manual reports", '
        '"source_quote": "Managers spend 5 hours a week on manual reports", '
        '"confidence": 0.9, '
        '"is_inferred": false'
        '}]}'
    ),
    # Legacy single-stage replies retained for tests that still drive the
    # standalone 'pain' / 'impact' stages directly (not used by the merged
    # pipeline, which reads 'pain_impact').
    'pain': (
        '{"signals": [{'
        '"what": "OPS", '
        '"dimension": "TIME", '
        '"scope_level": "BUSINESS", '
        '"target_department": null, '
        '"summary": "Reporting takes 3 weeks", '
        '"source_quote": "Our reporting takes 3 weeks", '
        '"confidence": 0.9, '
        '"is_inferred": false'
        '}]}'
    ),
    'objective': (
        '{"signals": [{'
        '"what": "GROWTH", '
        '"dimension": "TIME", '
        '"scope_level": "BUSINESS", '
        '"target_department": null, '
        '"summary": "Cut onboarding time in half", '
        '"source_quote": "We want to onboard customers twice as fast", '
        '"confidence": 0.9, '
        '"is_inferred": false'
        '}]}'
    ),
    'impact': (
        '{"signals": [{'
        '"what": "OPS", '
        '"dimension": "TIME", '
        '"impact_type": "TIME", '
        '"scope_level": "BUSINESS", '
        '"target_department": null, '
        '"summary": "Managers spend 5h/week on manual reports", '
        '"source_quote": "Managers spend 5 hours a week on manual reports", '
        '"confidence": 0.9, '
        '"is_inferred": false'
        '}]}'
    ),
    # S10: free-text identity + the three qualification booleans.
    # Replaces the old tech_catalog_entry_id / tech_name_raw XOR.
    'techstack': (
        '{"signals": [{'
        '"tech_name": "Salesforce", '
        '"is_competitor": true, '
        '"is_to_replace": false, '
        '"usage_scope": "COMPANY", '
        '"source_quote": "We use Salesforce across the company", '
        '"confidence": 0.9, '
        '"is_inferred": false'
        '}]}'
    ),
    'blocker': (
        '{"signals": [{'
        '"summary": "No budget allocated for Q4", '
        '"source_quote": "We have no budget for this in Q4", '
        '"confidence": 0.9, '
        '"is_inferred": false'
        '}]}'
    ),
}


# DEPARTMENT-scoped variants for pain / objective / impact. Each carries
# scope_level = DEPARTMENT and a target_department drawn from the
# StandardDepartment controlled vocabulary ("Marketing"). Used by the
# scope-extraction tests to assert the extractor reads scope_level and
# resolves target_department to the FK (A1). The 'Marketing' department
# must exist in the DB (post_migrate seed, or get_or_create in the test).
CANNED_REPLIES_DEPARTMENT = {
    # A2 merged stage, INDEPENDENT SCOPE proof drawn from one passage
    # ("the marketing data isn't reliable, it costs the company ~40k/quarter"):
    #   pain   -> DEPARTMENT / Marketing (who HAS the problem)
    #   impact -> BUSINESS / FINANCIAL   (who BEARS the cost)
    'pain_impact': (
        '{"pains": [{'
        '"what": "DATA", '
        '"dimension": "QUALITY", '
        '"scope_level": "DEPARTMENT", '
        '"target_department": "Marketing", '
        '"summary": "Marketing data quality is poor", '
        '"source_quote": "the marketing data isn\'t reliable", '
        '"confidence": 0.9, '
        '"is_inferred": false'
        '}], "impacts": [{'
        '"what": "DATA", '
        '"dimension": "QUALITY", '
        '"impact_type": "FINANCIAL", '
        '"scope_level": "BUSINESS", '
        '"target_department": null, '
        '"summary": "Unreliable marketing data costs ~40k per quarter", '
        '"source_quote": "it costs the company about 40k per quarter", '
        '"confidence": 0.9, '
        '"is_inferred": false'
        '}]}'
    ),
    'pain': (
        '{"signals": [{'
        '"what": "DATA", '
        '"dimension": "QUALITY", '
        '"scope_level": "DEPARTMENT", '
        '"target_department": "Marketing", '
        '"summary": "Marketing data quality is poor", '
        '"source_quote": "Our marketing team cannot trust the campaign data", '
        '"confidence": 0.9, '
        '"is_inferred": false'
        '}]}'
    ),
    'objective': (
        '{"signals": [{'
        '"what": "DATA", '
        '"dimension": "QUALITY", '
        '"scope_level": "DEPARTMENT", '
        '"target_department": "Marketing", '
        '"summary": "Improve marketing data quality", '
        '"source_quote": "Marketing wants clean, trustworthy campaign data", '
        '"confidence": 0.9, '
        '"is_inferred": false'
        '}]}'
    ),
    'impact': (
        '{"signals": [{'
        '"what": "DATA", '
        '"dimension": "QUALITY", '
        '"impact_type": "PRODUCTIVITY", '
        '"scope_level": "DEPARTMENT", '
        '"target_department": "Marketing", '
        '"summary": "Marketing loses time on bad data", '
        '"source_quote": "Marketing spends 6 hours a week cleaning campaign data", '
        '"confidence": 0.9, '
        '"is_inferred": false'
        '}]}'
    ),
}


# A minimal happy-path LLM payload for the NextStepsPipeline single
# stage. Used by Sprint B4 tests that want a "everything succeeded"
# baseline without hand-rolling JSON per test. The shape mirrors
# prompts/next_steps/next_steps_v1.py OUTPUT SCHEMA.
CANNED_REPLY_NEXT_STEPS_HAPPY = (
    '{"signals": [{'
    '"suggested_title": "Send pricing recap to CFO", '
    '"suggested_activity_type": "EMAIL", '
    '"suggested_due_date": "2026-12-15", '
    '"source_quote": "The CFO asked for a pricing recap by mid-December", '
    '"confidence": 0.9, '
    '"is_inferred": false'
    '}]}'
)
