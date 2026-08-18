# backend/tests/territories/test_account_tech_stack_filter.py
"""
Unit tests for AccountFilterService's has_tech_stack filter (S10).

The filter used to query the LEGACY `apps.accounts.TechStack` table
(TD-61) — a pre-modular model that nothing in the modular flow writes
to. For any account created through the modular stack it matched
nothing, so "accounts using Salesforce" always came back empty.

It now runs against `app_modules.signals.TechStackSignal`, matching on
`tech_name_normalized` — the column TechStackSignal.save() derives from
the raw `tech_name`. Incoming filter values go through the same
`_normalize_tech_name` helper, so what a user types ("  Salesforce  ")
matches what was stored ("salesforce") without either side caring about
casing or spacing.

Placed alongside test_contact_filter_service.py and
test_account_counts_parity.py, which is where filter-service unit tests
live; both exercise the service directly and reuse ./_builders.
"""

import pytest

from app_modules.accounts.models import CompanyAccount
from app_modules.accounts.services.filter_service import AccountFilterService
from app_modules.signals.constants import SignalSource, SignalStatus
from app_modules.signals.models import TechStackSignal

from ._builders import mk_account


# =============================================================================
# HELPERS
# =============================================================================

def _mk_tech(account, owner, ca, tech_name, status=SignalStatus.VALIDATED):
    """
    A TechStackSignal carrying its identity on the column (no catalogue).

    source is forced to LLM_EXTRACTED for non-VALIDATED statuses because
    BaseSignal.save() rewrites a MANUAL signal to VALIDATED at create
    time (base_model.py rule 1).
    """
    source = (
        SignalSource.MANUAL
        if status == SignalStatus.VALIDATED
        else SignalSource.LLM_EXTRACTED
    )
    sig = TechStackSignal(
        account=account,
        tech_catalog_entry=None,
        tech_name=tech_name,
        source=source,
        status=status,
        source_quote=f'They use {tech_name}',
    )
    sig.save(user=owner, client_id=ca.id)
    return sig


def _filter(ca, user, **filter_definition):
    """Run the real service against a client-scoped base queryset."""
    base = CompanyAccount.objects.filter(client_id=ca.id)
    return AccountFilterService.apply_filters(
        base, filter_definition, client_id=ca.id, user=user,
    )


def _names(qs):
    return sorted(qs.values_list('company_name', flat=True))


# =============================================================================
# A — THE FILTER MATCHES THE MODULAR SIGNAL
# =============================================================================

@pytest.mark.django_db
class TestHasTechStackMatching:

    def test_matches_account_with_the_tech_signal(self, user_a, client_account_a):
        """
        The red-repro case: an account whose only tech evidence is a
        modular TechStackSignal must be found. Against the legacy table
        this returned nothing.
        """
        a = mk_account('WithSalesforce', user_a, client_account_a)
        mk_account('WithoutAnyTech', user_a, client_account_a)
        _mk_tech(a, user_a, client_account_a, 'Salesforce')

        result = _filter(client_account_a, user_a, has_tech_stack=['Salesforce'])

        assert _names(result) == ['WithSalesforce']

    def test_match_is_case_and_whitespace_insensitive(
        self, user_a, client_account_a,
    ):
        """
        Stored "  Salesforce   CRM " normalises to "salesforce crm"; a
        user typing any spelling of it must still match.
        """
        a = mk_account('Acme', user_a, client_account_a)
        _mk_tech(a, user_a, client_account_a, '  Salesforce   CRM ')

        for typed in ('Salesforce CRM', 'salesforce crm', '  SALESFORCE  CRM  '):
            result = _filter(
                client_account_a, user_a, has_tech_stack=[typed],
            )
            assert _names(result) == ['Acme'], f'failed for {typed!r}'

    def test_partial_name_does_not_match(self, user_a, client_account_a):
        """
        Matching is exact-on-normalised, not substring: "Sales" must not
        pull in every account running Salesforce.
        """
        a = mk_account('Acme', user_a, client_account_a)
        _mk_tech(a, user_a, client_account_a, 'Salesforce')

        assert _names(_filter(
            client_account_a, user_a, has_tech_stack=['Sales'],
        )) == []

    def test_a_string_value_is_accepted_not_just_a_list(
        self, user_a, client_account_a,
    ):
        """The service normalises a bare string to a one-element list."""
        a = mk_account('Acme', user_a, client_account_a)
        _mk_tech(a, user_a, client_account_a, 'Salesforce')

        assert _names(_filter(
            client_account_a, user_a, has_tech_stack='Salesforce',
        )) == ['Acme']

    def test_one_account_many_tools(self, user_a, client_account_a):
        a = mk_account('Acme', user_a, client_account_a)
        _mk_tech(a, user_a, client_account_a, 'Salesforce')
        _mk_tech(a, user_a, client_account_a, 'Slack')

        assert _names(_filter(
            client_account_a, user_a, has_tech_stack=['Slack'],
        )) == ['Acme']

    def test_duplicate_signals_do_not_duplicate_the_account(
        self, user_a, client_account_a,
    ):
        """
        Exists() must not fan the account out — three mentions of one
        tool is the corroboration model, not three rows.
        """
        a = mk_account('Acme', user_a, client_account_a)
        for _ in range(3):
            _mk_tech(a, user_a, client_account_a, 'Salesforce')

        result = _filter(client_account_a, user_a, has_tech_stack=['Salesforce'])
        assert result.count() == 1


# =============================================================================
# B — MULTI-VALUE (OR) SEMANTICS
# =============================================================================

@pytest.mark.django_db
class TestMultiValueSemantics:

    def test_any_of_the_listed_tools_matches(self, user_a, client_account_a):
        """Mirrors the legacy __in semantics: OR, not AND."""
        a = mk_account('HasSalesforce', user_a, client_account_a)
        b = mk_account('HasHubSpot', user_a, client_account_a)
        mk_account('HasNeither', user_a, client_account_a)
        _mk_tech(a, user_a, client_account_a, 'Salesforce')
        _mk_tech(b, user_a, client_account_a, 'HubSpot')

        result = _filter(
            client_account_a, user_a, has_tech_stack=['Salesforce', 'HubSpot'],
        )

        assert _names(result) == ['HasHubSpot', 'HasSalesforce']

    def test_each_value_is_normalised_independently(
        self, user_a, client_account_a,
    ):
        a = mk_account('Acme', user_a, client_account_a)
        _mk_tech(a, user_a, client_account_a, 'HubSpot')

        assert _names(_filter(
            client_account_a, user_a,
            has_tech_stack=['  SALESFORCE ', 'hubspot'],
        )) == ['Acme']

    def test_a_blank_entry_never_matches_a_blank_tech_name(
        self, user_a, client_account_a,
    ):
        """
        A blank filter value is dropped, so it cannot silently match
        signals whose tech_name is empty. Paired with a real value here
        so the filter is genuinely active — a blank-only input is
        treated as "no filter at all" (next test).
        """
        blank = mk_account('BlankTechName', user_a, client_account_a)
        real = mk_account('HasSalesforce', user_a, client_account_a)
        _mk_tech(blank, user_a, client_account_a, '')
        _mk_tech(real, user_a, client_account_a, 'Salesforce')

        result = _filter(
            client_account_a, user_a, has_tech_stack=['   ', 'Salesforce'],
        )

        assert _names(result) == ['HasSalesforce']

    def test_blank_only_input_is_treated_as_no_filter(
        self, user_a, client_account_a,
    ):
        """
        Whitespace-only values normalise away to nothing, which is the
        same state as an absent filter — so the queryset is returned
        untouched rather than narrowed to zero. Consistent with the
        `if not tech_names` guard and with the view, which only applies
        the filter when the query param is truthy.
        """
        mk_account('A1', user_a, client_account_a)
        mk_account('A2', user_a, client_account_a)

        assert _names(_filter(
            client_account_a, user_a, has_tech_stack=['   ', ''],
        )) == ['A1', 'A2']


# =============================================================================
# C — STATUS RULE: PENDING and VALIDATED count, REJECTED does not
# =============================================================================

@pytest.mark.django_db
class TestStatusRule:

    def test_pending_signal_counts(self, user_a, client_account_a):
        """
        A tech mention is real intel before a rep validates it — an
        LLM-extracted PENDING signal makes the account match.
        """
        a = mk_account('Acme', user_a, client_account_a)
        _mk_tech(
            a, user_a, client_account_a, 'Salesforce',
            status=SignalStatus.PENDING,
        )

        assert _names(_filter(
            client_account_a, user_a, has_tech_stack=['Salesforce'],
        )) == ['Acme']

    def test_validated_signal_counts(self, user_a, client_account_a):
        a = mk_account('Acme', user_a, client_account_a)
        _mk_tech(
            a, user_a, client_account_a, 'Salesforce',
            status=SignalStatus.VALIDATED,
        )

        assert _names(_filter(
            client_account_a, user_a, has_tech_stack=['Salesforce'],
        )) == ['Acme']

    def test_rejected_signal_does_not_count(self, user_a, client_account_a):
        """A rep dismissed it — the account is not running that tool."""
        a = mk_account('Acme', user_a, client_account_a)
        _mk_tech(
            a, user_a, client_account_a, 'Salesforce',
            status=SignalStatus.REJECTED,
        )

        assert _names(_filter(
            client_account_a, user_a, has_tech_stack=['Salesforce'],
        )) == []

    def test_rejected_alongside_validated_still_matches(
        self, user_a, client_account_a,
    ):
        a = mk_account('Acme', user_a, client_account_a)
        _mk_tech(
            a, user_a, client_account_a, 'Salesforce',
            status=SignalStatus.REJECTED,
        )
        _mk_tech(
            a, user_a, client_account_a, 'Salesforce',
            status=SignalStatus.VALIDATED,
        )

        assert _names(_filter(
            client_account_a, user_a, has_tech_stack=['Salesforce'],
        )) == ['Acme']


# =============================================================================
# D — TENANT SCOPING
# =============================================================================

@pytest.mark.django_db
class TestTenantScoping:

    def test_another_tenants_account_is_not_matched(
        self, user_a, client_account_a, user_b, client_account_b,
    ):
        """
        Same tool, different tenant. The base queryset is already
        client-scoped; the Exists() subquery is scoped too, so neither
        layer can leak.
        """
        a = mk_account('TenantA', user_a, client_account_a)
        b = mk_account('TenantB', user_b, client_account_b)
        _mk_tech(a, user_a, client_account_a, 'Salesforce')
        _mk_tech(b, user_b, client_account_b, 'Salesforce')

        assert _names(_filter(
            client_account_a, user_a, has_tech_stack=['Salesforce'],
        )) == ['TenantA']
        assert _names(_filter(
            client_account_b, user_b, has_tech_stack=['Salesforce'],
        )) == ['TenantB']


# =============================================================================
# E — NON-REGRESSION: THE FILTER ONLY NARROWS WHEN ASKED
# =============================================================================

@pytest.mark.django_db
class TestNoFilterIsNoOp:

    def test_absent_filter_returns_every_account(self, user_a, client_account_a):
        mk_account('A1', user_a, client_account_a)
        mk_account('A2', user_a, client_account_a)

        assert _names(_filter(client_account_a, user_a)) == ['A1', 'A2']

    def test_empty_list_returns_every_account(self, user_a, client_account_a):
        mk_account('A1', user_a, client_account_a)
        mk_account('A2', user_a, client_account_a)

        assert _names(_filter(
            client_account_a, user_a, has_tech_stack=[],
        )) == ['A1', 'A2']

    def test_unmatched_tool_returns_nothing(self, user_a, client_account_a):
        a = mk_account('Acme', user_a, client_account_a)
        _mk_tech(a, user_a, client_account_a, 'Salesforce')

        assert _names(_filter(
            client_account_a, user_a, has_tech_stack=['Pipedrive'],
        )) == []


# =============================================================================
# F — SAVED-FILTER SUMMARY
# =============================================================================

class TestFilterSummary:

    def test_summary_lists_the_requested_tools(self):
        summary = AccountFilterService.get_filter_summary(
            {'has_tech_stack': ['Salesforce', 'HubSpot']}
        )
        assert 'Tech Stack: Salesforce, HubSpot' in summary

    def test_summary_accepts_a_bare_string(self):
        summary = AccountFilterService.get_filter_summary(
            {'has_tech_stack': 'Salesforce'}
        )
        assert 'Tech Stack: Salesforce' in summary
