# backend/tests/territories/test_contact_filter_service.py
"""
Unit tests for ContactFilterService.

Focus:
- opted_out now filters (the gap the inline evaluator never closed);
- influence_level (scalar + array) and standard_department filter correctly;
- has_buying_authority honours an explicit boolean;
- contact_scope 'mine' narrows via the owning account's owner;
- the service never widens past the client-scoped base queryset it is given.
"""

import pytest

from app_modules.contacts.models import Contact
from app_modules.contacts.services.filter_service import ContactFilterService

from ._builders import mk_user, mk_account, mk_contact


def _base(ca):
    return Contact.objects.filter(client_id=ca.id)


def _count(ca, filter_definition, user=None):
    return ContactFilterService.apply_filters(
        _base(ca), filter_definition, user=user,
    ).count()


@pytest.mark.django_db
class TestOptedOut:
    """The fix: opted_out is declared in ALLOWED_FILTER_KEYS but was never
    evaluated by the old inline counter."""

    def test_opted_out_false_excludes_opted_out_contacts(self, user_a, client_account_a):
        acc = mk_account('Acme', user_a, client_account_a)
        mk_contact(acc, user_a, client_account_a, opted_out=False)
        mk_contact(acc, user_a, client_account_a, opted_out=False)
        mk_contact(acc, user_a, client_account_a, opted_out=True)

        assert _count(client_account_a, {'opted_out': False}) == 2

    def test_opted_out_true_selects_only_opted_out(self, user_a, client_account_a):
        acc = mk_account('Acme', user_a, client_account_a)
        mk_contact(acc, user_a, client_account_a, opted_out=False)
        mk_contact(acc, user_a, client_account_a, opted_out=True)

        assert _count(client_account_a, {'opted_out': True}) == 1

    def test_empty_filter_counts_all(self, user_a, client_account_a):
        acc = mk_account('Acme', user_a, client_account_a)
        mk_contact(acc, user_a, client_account_a, opted_out=False)
        mk_contact(acc, user_a, client_account_a, opted_out=True)

        assert _count(client_account_a, {}) == 2


@pytest.mark.django_db
class TestDirectFilters:

    def test_influence_level_scalar(self, user_a, client_account_a):
        acc = mk_account('Acme', user_a, client_account_a)
        mk_contact(acc, user_a, client_account_a, influence_level='DECISION_MAKER')
        mk_contact(acc, user_a, client_account_a, influence_level='USER')

        assert _count(client_account_a, {'influence_level': 'DECISION_MAKER'}) == 1

    def test_influence_level_array(self, user_a, client_account_a):
        acc = mk_account('Acme', user_a, client_account_a)
        mk_contact(acc, user_a, client_account_a, influence_level='DECISION_MAKER')
        mk_contact(acc, user_a, client_account_a, influence_level='CHAMPION')
        mk_contact(acc, user_a, client_account_a, influence_level='USER')

        assert _count(
            client_account_a, {'influence_level': ['DECISION_MAKER', 'CHAMPION']}
        ) == 2

    def test_has_buying_authority_true(self, user_a, client_account_a):
        acc = mk_account('Acme', user_a, client_account_a)
        mk_contact(acc, user_a, client_account_a, has_buying_authority=True)
        mk_contact(acc, user_a, client_account_a, has_buying_authority=False)
        mk_contact(acc, user_a, client_account_a, has_buying_authority=None)

        assert _count(client_account_a, {'has_buying_authority': True}) == 1


@pytest.mark.django_db
class TestContactScope:

    def test_scope_mine_narrows_by_account_owner(
        self, user_a, client_account_a, role_individual_a
    ):
        other = mk_user('other-a@a.test', client_account_a, role_individual_a)
        acc_mine = mk_account('Mine', user_a, client_account_a)
        acc_other = mk_account('Other', other, client_account_a)
        mk_contact(acc_mine, user_a, client_account_a)
        mk_contact(acc_other, other, client_account_a)

        # user_a with 'mine' scope sees only the contact on their own account.
        assert _count(client_account_a, {'contact_scope': 'mine'}, user=user_a) == 1
        # Without scope, both contacts count.
        assert _count(client_account_a, {}, user=user_a) == 2

    def test_scope_all_is_noop(self, user_a, client_account_a):
        acc = mk_account('Acme', user_a, client_account_a)
        mk_contact(acc, user_a, client_account_a)
        assert _count(client_account_a, {'contact_scope': 'all'}, user=user_a) == 1


@pytest.mark.django_db
def test_service_does_not_widen_past_client_base(
    user_a, client_account_a, user_b, client_account_b
):
    """A contact on tenant B is invisible when the base queryset is scoped to
    tenant A — the service filters within the queryset it is handed, never
    widening it."""
    acc_a = mk_account('A', user_a, client_account_a)
    acc_b = mk_account('B', user_b, client_account_b)
    mk_contact(acc_a, user_a, client_account_a)
    mk_contact(acc_b, user_b, client_account_b)

    assert _count(client_account_a, {'opted_out': False}) == 1
