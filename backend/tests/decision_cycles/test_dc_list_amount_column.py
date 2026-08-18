# backend/tests/decision_cycles/test_dc_list_amount_column.py
"""
The DC list's Amount column — served from the derived roll-up, with its unit.

The column used to read ``estimated_value``, a manual field no runtime path
populates (TD-75), so it rendered a dash on every row. The list payload now
carries:

  * ``total_deal_value`` — the product roll-up, read off the ``_deal_value``
    annotation the list queryset carries (views.py list branch), so the
    serializer costs no extra query per row;
  * ``currency`` — the tenant's single currency (core.currency), the unit that
    amount is in.

``estimated_value`` stays in the payload untouched: it is the legacy manual
field, and nothing displays it any more.

Sorting follows the column: the orderable term is the annotation alias, not the
dead field — sorting by a column nobody populates sorted nothing.

Harness mirrors tests/decision_cycles/test_dc_list_filters_ordering.py (same
endpoint, same authed client).
"""

from decimal import Decimal

import pytest

from app_modules.accounts.models import CompanyAccount
from app_modules.decision_cycles.models import DecisionCycle
from app_modules.decision_cycles.services import DEAL_VALUE_ALIAS
from tests.deal_value_helpers import give_deal_value


pytestmark = pytest.mark.django_db


LIST_URL = '/decision_cycles/'


def _cycle(owner, ca, *, name, amount, estimated_value=None):
    account = CompanyAccount(company_name=f'Acc-{name}', has_buying_decision=True,
                             account_owner=owner)
    account.save(user=owner, client_id=ca.id)

    cycle = DecisionCycle(account=account, owner=owner, name=name,
                          estimated_value=estimated_value, is_active=False)
    cycle.save(user=owner, client_id=ca.id)
    give_deal_value(cycle, amount, user=owner)
    return cycle


def _rows(response):
    body = response.json()
    data = body['data'] if 'data' in body else body
    return data['results'] if isinstance(data, dict) and 'results' in data else data


def _row_for(rows, cycle):
    return next(r for r in rows if r['id'] == str(cycle.id))


class TestAmountColumnPayload:

    def test_the_list_serves_the_derived_roll_up(
        self, authed_api_a, client_account_a, user_a,
    ):
        cycle = _cycle(user_a, client_account_a, name='priced',
                       amount=Decimal('60000'))

        row = _row_for(_rows(authed_api_a.get(LIST_URL)), cycle)

        assert Decimal(row['total_deal_value']) == Decimal('60000')

    def test_the_amount_does_not_come_from_estimated_value(
        self, authed_api_a, client_account_a, user_a,
    ):
        """A decoy on the dead field: the column must ignore it."""
        cycle = _cycle(user_a, client_account_a, name='decoyed',
                       amount=Decimal('60000'),
                       estimated_value=Decimal('999999'))

        row = _row_for(_rows(authed_api_a.get(LIST_URL)), cycle)

        assert Decimal(row['total_deal_value']) == Decimal('60000')
        assert Decimal(row['estimated_value']) == Decimal('999999')   # untouched

    def test_a_cycle_without_lines_shows_zero_not_an_error(
        self, authed_api_a, client_account_a, user_a,
    ):
        cycle = _cycle(user_a, client_account_a, name='empty', amount=None)

        row = _row_for(_rows(authed_api_a.get(LIST_URL)), cycle)

        assert Decimal(row['total_deal_value']) == Decimal('0')

    def test_every_row_carries_the_tenant_currency(
        self, authed_api_a, client_account_a, user_a,
    ):
        _cycle(user_a, client_account_a, name='with-currency',
               amount=Decimal('1000'))

        rows = _rows(authed_api_a.get(LIST_URL))

        assert rows
        assert all(r['currency'] == client_account_a.currency for r in rows)


class TestAmountOrdering:

    def test_the_list_orders_on_the_roll_up(
        self, authed_api_a, client_account_a, user_a,
    ):
        small = _cycle(user_a, client_account_a, name='small',
                       amount=Decimal('100'))
        big = _cycle(user_a, client_account_a, name='big',
                     amount=Decimal('9000'))

        asc = _rows(authed_api_a.get(LIST_URL, {'ordering': DEAL_VALUE_ALIAS}))
        ids = [r['id'] for r in asc if r['id'] in (str(small.id), str(big.id))]

        assert ids == [str(small.id), str(big.id)]

        desc = _rows(authed_api_a.get(LIST_URL, {'ordering': f'-{DEAL_VALUE_ALIAS}'}))
        ids = [r['id'] for r in desc if r['id'] in (str(small.id), str(big.id))]

        assert ids == [str(big.id), str(small.id)]

    def test_the_orderable_terms_expose_the_roll_up_not_the_dead_field(self):
        from app_modules.decision_cycles.config import CONFIG

        assert DEAL_VALUE_ALIAS in CONFIG.filters.dc_ordering_fields
        assert 'estimated_value' not in CONFIG.filters.dc_ordering_fields


class TestNoAmountFilter:
    """TD-124 stays deferred to the Filters sprint — unblocked by a reliable
    amount, but NOT built here."""

    def test_the_list_has_no_amount_facet(self):
        from app_modules.decision_cycles.views.views import DecisionCycleFilterSet

        facets = set(DecisionCycleFilterSet.base_filters)

        assert not {f for f in facets if 'amount' in f or 'value' in f}
