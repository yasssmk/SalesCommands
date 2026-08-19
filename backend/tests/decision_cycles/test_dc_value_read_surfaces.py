# backend/tests/decision_cycles/test_dc_value_read_surfaces.py
"""
The DC's own value on the READ surfaces the workspace actually calls.

Sprint C made the deal amount derived (Σ of the product lines, discount
included) and exposed it on ONE surface: the DC *list*
(``DecisionCycleListSerializer``, covered by test_dc_list_amount_column.py).
The two surfaces the DC WORKSPACE reads were left behind:

  * ``GET /decision_cycles/by-account/<account_id>/`` — what the workspace
    page loads (views.py ``by_account`` -> ``DecisionCycleTimelineSerializer``);
  * ``GET /decision_cycles/<id>/`` — the cycle detail
    (``DecisionCycleSerializer``).

Both carried ``estimated_value`` — the manual field no runtime path populates
(TD-75) — and no roll-up at all, so the workspace header and the Products tab
had nothing true to render. This module pins both payloads on the SAME derived
amount the list serves, plus its unit (the tenant's single currency).

The amount is NOT re-derived here: every surface reads
``DecisionCycle.total_deal_value``, which is the one formula declared in
decision_cycles/services/deal_value_sql.py. ``estimated_value`` stays in the
payloads untouched — legacy, and nothing displays it any more.

Harness mirrors tests/decision_cycles/test_dc_list_amount_column.py (same
endpoint style, same authed client, same give_deal_value helper).
"""

from decimal import Decimal

import pytest

from app_modules.accounts.models import CompanyAccount
from app_modules.decision_cycles.constants import CycleOutcome
from app_modules.decision_cycles.models import DealProduct, DecisionCycle
from app_modules.product_catalog.models import ProductCatalog
from tests.deal_value_helpers import give_deal_value


pytestmark = pytest.mark.django_db


def _account(owner, ca, *, name):
    account = CompanyAccount(company_name=name, has_buying_decision=True,
                             account_owner=owner)
    account.save(user=owner, client_id=ca.id)
    return account


def _cycle(owner, ca, *, name, amount, estimated_value=None, account=None,
           outcome=None):
    account = account or _account(owner, ca, name=f'Acc-{name}')
    cycle = DecisionCycle(account=account, owner=owner, name=name,
                          estimated_value=estimated_value, outcome=outcome,
                          is_active=False)
    cycle.save(user=owner, client_id=ca.id)
    if amount is not None:
        give_deal_value(cycle, amount, user=owner)
    return cycle


def _discounted_line(cycle, owner, ca, *, list_price, discount):
    """One line at ``list_price`` with ``discount``% off — the payload can only
    be right if the discount travelled with the amount."""
    product = ProductCatalog(name=f'disc-{cycle.name}')
    product.save(user=owner, client_id=ca.id)
    line = DealProduct(decision_cycle=cycle, product_catalog_entry=product,
                       quantity=1, unit_price=list_price,
                       discount_percent=discount)
    line.save(user=owner, client_id=ca.id)
    return line


def _payload(response):
    body = response.json()
    return body['data'] if 'data' in body else body


def _detail(api, cycle):
    return _payload(api.get(f'/decision_cycles/{cycle.id}/'))


def _by_account_rows(api, account):
    data = _payload(api.get(f'/decision_cycles/by-account/{account.id}/'))
    return data['results'] if isinstance(data, dict) and 'results' in data else data


def _row_for(rows, cycle):
    return next(r for r in rows if r['id'] == str(cycle.id))


# ===========================================================================
# GET /decision_cycles/<id>/  — the cycle detail
# ===========================================================================

class TestDetailSurface:

    def test_the_detail_serves_the_derived_roll_up(
        self, authed_api_a, client_account_a, user_a,
    ):
        cycle = _cycle(user_a, client_account_a, name='priced',
                       amount=Decimal('60000'))

        body = _detail(authed_api_a, cycle)

        assert Decimal(body['total_deal_value']) == Decimal('60000')

    def test_the_detail_amount_does_not_come_from_estimated_value(
        self, authed_api_a, client_account_a, user_a,
    ):
        """A decoy on the dead field: the amount must ignore it.

        Unlike the list and by-account payloads, the detail payload has never
        carried ``estimated_value`` at all (it is absent from
        DecisionCycleSerializer.Meta.fields), and this sub-step does not add it
        — surfacing a field nothing populates is the opposite of the point. So
        the assertion is that the decoy neither feeds nor appears in the
        payload."""
        cycle = _cycle(user_a, client_account_a, name='decoyed',
                       amount=Decimal('60000'),
                       estimated_value=Decimal('999999'))

        body = _detail(authed_api_a, cycle)

        assert Decimal(body['total_deal_value']) == Decimal('60000')
        assert 'estimated_value' not in body

    def test_a_cycle_without_lines_shows_zero_not_an_error(
        self, authed_api_a, client_account_a, user_a,
    ):
        cycle = _cycle(user_a, client_account_a, name='empty', amount=None)

        assert Decimal(_detail(authed_api_a, cycle)['total_deal_value']) \
            == Decimal('0')

    def test_the_detail_carries_the_tenant_currency(
        self, authed_api_a, client_account_a, user_a,
    ):
        cycle = _cycle(user_a, client_account_a, name='with-currency',
                       amount=Decimal('1000'))

        assert _detail(authed_api_a, cycle)['currency'] \
            == client_account_a.currency

    def test_the_discount_flows_into_the_detail_amount(
        self, authed_api_a, client_account_a, user_a,
    ):
        cycle = _cycle(user_a, client_account_a, name='disc', amount=None)
        _discounted_line(cycle, user_a, client_account_a,
                         list_price=Decimal('10000'), discount=Decimal('25'))

        assert Decimal(_detail(authed_api_a, cycle)['total_deal_value']) \
            == Decimal('7500')


# ===========================================================================
# GET /decision_cycles/by-account/<account_id>/  — what the WORKSPACE loads
# ===========================================================================

class TestByAccountSurface:

    def test_the_workspace_payload_serves_the_derived_roll_up(
        self, authed_api_a, client_account_a, user_a,
    ):
        account = _account(user_a, client_account_a, name='WS')
        cycle = _cycle(user_a, client_account_a, name='priced',
                       amount=Decimal('60000'), account=account)

        row = _row_for(_by_account_rows(authed_api_a, account), cycle)

        assert Decimal(row['total_deal_value']) == Decimal('60000')

    def test_the_workspace_amount_does_not_come_from_estimated_value(
        self, authed_api_a, client_account_a, user_a,
    ):
        account = _account(user_a, client_account_a, name='WS-decoy')
        cycle = _cycle(user_a, client_account_a, name='decoyed',
                       amount=Decimal('60000'), account=account,
                       estimated_value=Decimal('999999'))

        row = _row_for(_by_account_rows(authed_api_a, account), cycle)

        assert Decimal(row['total_deal_value']) == Decimal('60000')
        assert Decimal(row['estimated_value']) == Decimal('999999')

    def test_every_workspace_row_carries_the_tenant_currency(
        self, authed_api_a, client_account_a, user_a,
    ):
        account = _account(user_a, client_account_a, name='WS-cur')
        _cycle(user_a, client_account_a, name='c1', amount=Decimal('1000'),
               account=account)

        rows = _by_account_rows(authed_api_a, account)

        assert rows
        assert all(r['currency'] == client_account_a.currency for r in rows)

    def test_the_discount_flows_into_the_workspace_amount(
        self, authed_api_a, client_account_a, user_a,
    ):
        account = _account(user_a, client_account_a, name='WS-disc')
        cycle = _cycle(user_a, client_account_a, name='disc', amount=None,
                       account=account)
        _discounted_line(cycle, user_a, client_account_a,
                         list_price=Decimal('10000'), discount=Decimal('25'))

        row = _row_for(_by_account_rows(authed_api_a, account), cycle)

        assert Decimal(row['total_deal_value']) == Decimal('7500')

    def test_an_open_and_a_won_cycle_each_carry_their_own_value(
        self, authed_api_a, client_account_a, user_a,
    ):
        """The DC's value is the DEAL's value — it is not a pipeline/won
        aggregate, so the outcome does not zero it out. Open/won exclusivity is
        the aggregation layer's rule (KPIs, quotas), not this surface's."""
        account = _account(user_a, client_account_a, name='WS-mixed')
        open_dc = _cycle(user_a, client_account_a, name='open',
                         amount=Decimal('60000'), account=account)
        won_dc = _cycle(user_a, client_account_a, name='won',
                        amount=Decimal('40000'), account=account,
                        outcome=CycleOutcome.WON)

        rows = _by_account_rows(authed_api_a, account)

        assert Decimal(_row_for(rows, open_dc)['total_deal_value']) \
            == Decimal('60000')
        assert Decimal(_row_for(rows, won_dc)['total_deal_value']) \
            == Decimal('40000')

    def test_the_workspace_payload_stays_query_bounded(
        self, authed_api_a, client_account_a, user_a, django_assert_max_num_queries,
    ):
        """The roll-up is an ANNOTATION on the by_account queryset, not a per-row
        property read: adding cycles must not add queries. Guards the N+1 the
        naive fix would introduce (total_deal_value falls back to one query per
        cycle when the annotation is absent)."""
        account = _account(user_a, client_account_a, name='WS-n1')
        for i in range(4):
            _cycle(user_a, client_account_a, name=f'c{i}',
                   amount=Decimal('1000'), account=account)

        with django_assert_max_num_queries(15):
            _by_account_rows(authed_api_a, account)
