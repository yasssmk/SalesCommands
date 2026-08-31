# backend/tests/signals/test_techstack_name_normalization.py
"""
Model-level coverage for the TechStackSignal tech identity fields (S10).

Product rules under test:

  1. `tech_name` holds the raw display text exactly as the LLM (or the
     rep) wrote it — "Salesforce CRM", "  HubSpot  Marketing Hub ".
     It is never rewritten.

  2. `tech_name_normalized` is DERIVED from `tech_name` on every save:
     lowercase + strip + internal whitespace collapsed to single
     spaces. It is the grouping / filtering / de-duplication key.
     `tech_name` is the single source of truth — the normalized column
     is always recomputed, so the two can never desync.

  3. Blank / missing `tech_name` yields `tech_name_normalized == ''`
     (empty string, never None — mirrors the model's prevailing
     non-nullable text convention, cf. `cost_description` and `notes`).

  4. `is_to_replace` is the sole surviving qualification boolean,
     defaulting to False (is_competitor was dropped in 8b, is_integration
     in 9c). False means "a tool the account simply uses".

Non-regression:
  * `canonical_key` stays None — TechStack is not clusterable and the
    new save() override must not touch it.
  * The existing metadata surface (usage_scope, renewal_date, notes,
    metadata JSON, ...) is untouched by normalisation.

Instantiation + save mirror the existing helper style in
tests/signals/test_techstack_pending_catalog_link.py:53-60 —
`TechStackSignal(...)` then `sig.save(user=..., client_id=...)`, i.e.
the real ModuleBaseModel.save() audit path, not `objects.create()`.
"""

import pytest

from app_modules.signals.constants import SignalSource, SignalStatus, UsageScope
from app_modules.signals.models import TechStackSignal


pytestmark = pytest.mark.django_db


# =============================================================================
# HELPERS
# =============================================================================

def _make_signal(account, activity, user, **overrides):
    """
    Build + save a TechStackSignal through the real save() path.

    Mirrors `_make_pending_unmatched` in
    tests/signals/test_techstack_pending_catalog_link.py:53-60.
    """
    kwargs = {
        'account': account,
        'source_activity': activity,
        'source': SignalSource.LLM_EXTRACTED,
    }
    kwargs.update(overrides)

    sig = TechStackSignal(**kwargs)
    sig.save(user=user, client_id=account.client_id)
    return sig


# =============================================================================
# A — NORMALISATION AT SAVE
# =============================================================================

class TestTechNameNormalization:

    def test_raw_name_is_preserved_and_normalized_on_create(
        self, account, activity, user_a,
    ):
        """
        The red-repro case: mixed case + leading/trailing padding +
        internal multi-space collapses to a single lower-cased,
        single-spaced key, while the raw text survives verbatim.
        """
        sig = _make_signal(
            account, activity, user_a,
            tech_name='  Salesforce   CRM ',
        )

        # Raw text is never rewritten.
        assert sig.tech_name == '  Salesforce   CRM '
        # Derived key: lower + strip + collapse.
        assert sig.tech_name_normalized == 'salesforce crm'

        # And it is what actually landed in the DB, not just in memory.
        sig.refresh_from_db()
        assert sig.tech_name == '  Salesforce   CRM '
        assert sig.tech_name_normalized == 'salesforce crm'

    @pytest.mark.parametrize(
        'raw, expected',
        [
            ('Salesforce', 'salesforce'),
            ('SALESFORCE', 'salesforce'),
            ('  HubSpot  ', 'hubspot'),
            ('Microsoft   Teams', 'microsoft teams'),
            ('  Google \t Workspace \n Suite ', 'google workspace suite'),
            ('Zoom', 'zoom'),
        ],
    )
    def test_normalisation_cases(self, account, activity, user_a, raw, expected):
        sig = _make_signal(account, activity, user_a, tech_name=raw)
        assert sig.tech_name_normalized == expected

    def test_blank_tech_name_normalizes_to_empty_string(
        self, account, activity, user_a,
    ):
        """Whitespace-only input must not crash and must yield ''."""
        sig = _make_signal(account, activity, user_a, tech_name='   ')

        assert sig.tech_name_normalized == ''
        sig.refresh_from_db()
        assert sig.tech_name_normalized == ''

    def test_omitted_tech_name_defaults_to_empty_string(
        self, account, activity, user_a,
    ):
        """A signal saved without any tech_name at all is still valid."""
        sig = _make_signal(account, activity, user_a)

        assert sig.tech_name == ''
        assert sig.tech_name_normalized == ''

    def test_resave_recomputes_normalized_no_desync(
        self, account, activity, user_a,
    ):
        """
        The normalized column is derived, never authored: changing
        tech_name on an existing row must recompute it on the next save.
        """
        sig = _make_signal(account, activity, user_a, tech_name='Salesforce')
        assert sig.tech_name_normalized == 'salesforce'

        sig.tech_name = '  HubSpot   Marketing '
        sig.save(user=user_a, client_id=account.client_id)

        assert sig.tech_name_normalized == 'hubspot marketing'
        sig.refresh_from_db()
        assert sig.tech_name_normalized == 'hubspot marketing'

    def test_hand_written_normalized_is_overwritten_by_save(
        self, account, activity, user_a,
    ):
        """
        tech_name is the single source of truth — a caller cannot author
        tech_name_normalized directly.
        """
        sig = _make_signal(
            account, activity, user_a,
            tech_name='Salesforce',
            tech_name_normalized='SOMETHING ELSE',
        )
        assert sig.tech_name_normalized == 'salesforce'

    def test_same_tech_written_differently_shares_the_normalized_key(
        self, account, activity, user_a,
    ):
        """The whole point: two spellings de-duplicate onto one key."""
        a = _make_signal(account, activity, user_a, tech_name='Salesforce CRM')
        b = _make_signal(account, activity, user_a, tech_name='  salesforce   crm  ')

        assert a.tech_name != b.tech_name
        assert a.tech_name_normalized == b.tech_name_normalized == 'salesforce crm'

        assert TechStackSignal.objects.filter(
            account=account,
            tech_name_normalized='salesforce crm',
        ).count() == 2


# =============================================================================
# B — QUALIFICATION BOOLEANS
# =============================================================================

class TestQualificationBooleans:

    def test_defaults_to_false(self, account, activity, user_a):
        """No qualification set = a tech the account simply uses. is_competitor
        (8b) and is_integration (9c) were dropped — is_to_replace is the sole
        surviving qualification boolean."""
        sig = _make_signal(account, activity, user_a, tech_name='Notion')

        assert sig.is_to_replace is False

    def test_is_to_replace_is_settable(self, account, activity, user_a):
        sig = _make_signal(
            account, activity, user_a,
            tech_name='Salesforce',
            is_to_replace=True,
        )

        sig.refresh_from_db()
        assert sig.is_to_replace is True

    def test_flag_survives_a_name_edit(self, account, activity, user_a):
        """The save() override must not reset unrelated fields."""
        sig = _make_signal(
            account, activity, user_a,
            tech_name='Jira',
            is_to_replace=True,
        )

        sig.tech_name = 'Jira Software'
        sig.save(user=user_a, client_id=account.client_id)

        sig.refresh_from_db()
        assert sig.tech_name_normalized == 'jira software'
        assert sig.is_to_replace is True


# =============================================================================
# C — NON-REGRESSION ON THE EXISTING MODEL SURFACE
# =============================================================================

class TestExistingSurfaceUntouched:

    def test_canonical_key_stays_none(self, account, activity, user_a):
        """
        TechStack is not clusterable. The new save() override must not
        compute or set canonical_key (cleaned up in sub-step 5).
        """
        sig = _make_signal(account, activity, user_a, tech_name='Salesforce')

        assert sig.canonical_key is None
        sig.refresh_from_db()
        assert sig.canonical_key is None

    def test_metadata_surface_is_untouched_by_normalisation(
        self, account, activity, user_a,
    ):
        """usage_scope / renewal_date / notes / metadata all survive."""
        sig = _make_signal(
            account, activity, user_a,
            tech_name='  Zendesk  ',
            usage_scope=UsageScope.COMPANY,
            usage_start_year=2019,
            cost_description='around 3000€/month',
            notes='mentioned twice on the call',
            metadata={'pending_tech_name': 'Zendesk'},
        )

        sig.refresh_from_db()
        assert sig.tech_name_normalized == 'zendesk'
        assert sig.usage_scope == UsageScope.COMPANY
        assert sig.usage_start_year == 2019
        assert sig.cost_description == 'around 3000€/month'
        assert sig.notes == 'mentioned twice on the call'
        assert sig.metadata == {'pending_tech_name': 'Zendesk'}

    def test_base_signal_status_rules_still_apply(
        self, account, activity, user_a,
    ):
        """
        BaseSignal.save() business rules must still run after the
        normalisation step (MANUAL → VALIDATED + confidence cleared,
        LLM_EXTRACTED → PENDING).
        """
        llm = _make_signal(account, activity, user_a, tech_name='Asana')
        assert llm.status == SignalStatus.PENDING

        manual = _make_signal(
            account, activity, user_a,
            tech_name='Trello',
            source=SignalSource.MANUAL,
            confidence=0.9,
        )
        assert manual.status == SignalStatus.VALIDATED
        assert manual.confidence is None
        assert manual.tech_name_normalized == 'trello'
