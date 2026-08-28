# backend/tests/ai_pipelines/test_techstack_usage_departments_extraction.py
"""
Tech scope (usage) sub-step 2 -- extraction fills the multi-department M2M.

The techstack stage now emits `usage_departments` (an array of department
names explicitly designated as USERS of the tool). The extractor resolves
them to StandardDepartment rows and assigns the M2M
TechStackSignal.usage_departments. The legacy single-FK usage_department is
NO LONGER filled by extraction.

Two proof surfaces (mirror of test_techstack_extraction_raw_name.py):
  * PIPELINE PATH (persist_stage): a real extraction produces the right
    departments on the M2M, 0 / 1 / many, singular left null.
  * PROMPT-CONTENT: the tightened request prompt carries the explicit-
    designation rule + the multi and empty few-shots. This is the
    non-vacuity target -- mutate the designation instruction out of
    techstack_v1.py and this class goes red.
"""

import pytest

from app_modules.ai_pipelines.prompts.transcript_signals.techstack_v1 import (
    build_techstack_request,
)
from app_modules.ai_pipelines.services.transcript_signal_extractor import (
    TranscriptSignalExtractor,
    resolve_tech_usage_departments,
)
from app_modules.signals.models import TechStackSignal


pytestmark = pytest.mark.django_db


# =============================================================================
# FIXTURES — StandardDepartment vocabulary rows
# =============================================================================

@pytest.fixture
def dept_marketing(db):
    from app_modules.core_modules.models import StandardDepartment
    d, _ = StandardDepartment.objects.get_or_create(name='Marketing')
    return d


@pytest.fixture
def dept_sales(db):
    from app_modules.core_modules.models import StandardDepartment
    d, _ = StandardDepartment.objects.get_or_create(name='Sales')
    return d


@pytest.fixture
def dept_support(db):
    from app_modules.core_modules.models import StandardDepartment
    d, _ = StandardDepartment.objects.get_or_create(name='Customer Support')
    return d


# =============================================================================
# HELPERS
# =============================================================================

def _raw(tech_name, **overrides):
    payload = {
        'tech_name':      tech_name,
        'is_competitor':  False,
        'is_to_replace':  False,
        'usage_scope':    'TEAM',
        'usage_departments': [],
        'source_quote':   f'The team is on {tech_name}',
        'confidence':     0.9,
        'is_inferred':    False,
    }
    payload.update(overrides)
    return payload


def _persist(activity, account, user, raw_signals):
    return TranscriptSignalExtractor().persist_stage(
        stage='techstack',
        raw_signals=raw_signals,
        activity=activity,
        user=user,
        client_id=account.client_id,
        confidence_min=0.5,
        drop_inferred=True,
    )


def _dept_names(sig):
    return set(sig.usage_departments.values_list('name', flat=True))


# =============================================================================
# A — EXTRACTION FILLS THE M2M (0 / 1 / many), SINGULAR STAYS NULL
# =============================================================================

class TestExtractionFillsMultiDepartment:

    def test_single_designated_department_lands_on_the_m2m(
        self, account, activity, user_a, dept_marketing,
    ):
        """'the marketing team is on HubSpot' -> usage_departments=[Marketing]."""
        persisted, dropped = _persist(
            activity, account, user_a,
            [_raw('HubSpot', usage_departments=['Marketing'])],
        )

        assert dropped == 0
        sig = persisted[0]
        assert _dept_names(sig) == {'Marketing'}
        # The legacy single FK is NOT filled by extraction anymore.
        assert sig.usage_department_id is None

    def test_multiple_designated_departments_all_land(
        self, account, activity, user_a, dept_sales, dept_marketing,
    ):
        """'Sales and Marketing use X' -> [Sales, Marketing]."""
        persisted, _ = _persist(
            activity, account, user_a,
            [_raw('HubSpot', usage_departments=['Sales', 'Marketing'])],
        )

        sig = persisted[0]
        assert _dept_names(sig) == {'Sales', 'Marketing'}
        assert sig.usage_department_id is None

    def test_no_designated_department_yields_empty(
        self, account, activity, user_a,
    ):
        """A tool with nobody designated -> empty M2M, usage_scope kept."""
        persisted, _ = _persist(
            activity, account, user_a,
            [_raw('Slack', usage_scope='COMPANY', usage_departments=[])],
        )

        sig = persisted[0]
        assert _dept_names(sig) == set()
        assert sig.usage_scope == 'COMPANY'  # SCALE preserved, complementary
        assert sig.usage_department_id is None

    def test_zendesk_support_smoke(
        self, account, activity, user_a, dept_support,
    ):
        """PO smoke: Zendesk -> Customer Support."""
        persisted, _ = _persist(
            activity, account, user_a,
            [_raw('Zendesk', usage_departments=['Customer Support'])],
        )
        assert _dept_names(persisted[0]) == {'Customer Support'}


# =============================================================================
# B — RESOLVER GUARDS (unresolved / General Management / dedup)
# =============================================================================

class TestResolverGuards:

    def test_unresolved_name_is_dropped_not_invented(
        self, account, activity, user_a, dept_marketing,
    ):
        """A name outside the vocabulary is dropped; the valid one survives."""
        persisted, _ = _persist(
            activity, account, user_a,
            [_raw('HubSpot', usage_departments=['Marketing', 'Wizardry'])],
        )
        assert _dept_names(persisted[0]) == {'Marketing'}

    def test_general_management_is_dropped(
        self, account, activity, user_a,
    ):
        """A company-wide / executive catch-all is not a using department."""
        from app_modules.core_modules.models import StandardDepartment
        StandardDepartment.objects.get_or_create(name='General Management')

        persisted, _ = _persist(
            activity, account, user_a,
            [_raw('Slack', usage_departments=['General Management'])],
        )
        assert _dept_names(persisted[0]) == set()

    def test_duplicate_names_collapse(
        self, account, activity, user_a, dept_sales,
    ):
        persisted, _ = _persist(
            activity, account, user_a,
            [_raw('HubSpot', usage_departments=['Sales', 'Sales'])],
        )
        assert list(persisted[0].usage_departments.values_list('name', flat=True)) == [
            'Sales',
        ]

    def test_non_list_payload_yields_empty(self, db):
        """Defensive: a malformed non-list usage_departments -> []."""
        assert resolve_tech_usage_departments({'usage_departments': 'Sales'}) == []
        assert resolve_tech_usage_departments({}) == []


# =============================================================================
# C — PROMPT CONTENT (non-vacuity target)
# =============================================================================

class TestUsageDepartmentsPromptContent:
    """Mutate the designation instruction in techstack_v1.py and this re-reds."""

    def _prompt(self):
        return build_techstack_request('SOME TRANSCRIPT')

    def test_prompt_asks_for_the_using_departments(self):
        prompt = self._prompt()
        assert 'USAGE DEPARTMENTS' in prompt
        assert 'usage_departments' in prompt

    def test_prompt_states_the_explicit_designation_rule(self):
        prompt = self._prompt()
        assert 'DESIGNATION RULE' in prompt
        assert 'EXPLICITLY DESIGNATED' in prompt
        # Speaker / technical word alone do NOT designate a user.
        assert 'do NOT designate a user' in prompt

    def test_prompt_allows_multiple_departments(self):
        prompt = self._prompt()
        assert 'Several departments are allowed on one' in prompt
        assert '["Sales", "Marketing"]' in prompt

    def test_prompt_requires_empty_when_none_designated(self):
        prompt = self._prompt()
        assert 'emit an EMPTY' in prompt
        assert 'NEVER invent or guess a department' in prompt

    def test_prompt_no_longer_forces_department_mentions_to_unknown(self):
        """The old 'treat any department X uses tool Y as UNKNOWN' rule is gone."""
        prompt = self._prompt()
        assert 'the rep will refine' not in prompt
