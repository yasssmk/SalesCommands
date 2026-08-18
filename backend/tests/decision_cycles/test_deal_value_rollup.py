# backend/tests/decision_cycles/test_deal_value_rollup.py
"""
The unified deal-value roll-up: ONE formula, two bindings, no drift.

Covers ``app_modules/decision_cycles/services/deal_value_sql.py`` and the
``DecisionCycle.total_deal_value`` accessor that reads it.

Two things are proven here:

1. PARITY — the single-cycle accessor, the mass annotation and the KPI 7
   aggregate all return the SAME number, on the same cycles, for one-shot /
   subscription-priced / usage-priced / discounted / catalog-default lines.
   They are three bindings of one expression; if anyone re-implements the
   formula, these fail.

2. QUERY BOUND — a mass roll-up over N cycles through ``annotate_deal_value()``
   costs a CONSTANT number of queries, while the per-instance accessor in a
   Python loop costs one per cycle. The N+1 the annotation exists to prevent is
   asserted explicitly, so "just loop the property" cannot creep back in.

Query-count assertions mirror tests/bi/test_kpi_dc_money.py:207-218
(``django_assert_num_queries`` around the real queryset). Data is built through
the real create path, like tests/decision_cycles/test_deal_product.py:21-31.
"""

from decimal import Decimal

import pytest

from app_modules.bi.definitions.decision_cycles import _PRODUCT_ROLLUP
from app_modules.decision_cycles.models import DealProduct, DecisionCycle
from app_modules.decision_cycles.services import (
    DEAL_VALUE_ALIAS,
    annotate_cycle_state,
    annotate_deal_value,
)
from app_modules.product_catalog.models import ProductCatalog


pytestmark = pytest.mark.django_db


# =============================================================================
# HELPERS — real create path only
# =============================================================================

def _product(user, client_id, name, default_unit_price=None):
    entry = ProductCatalog(name=name, default_unit_price=default_unit_price)
    entry.save(user=user, client_id=client_id)
    return entry


def _line(cycle, product, user, *, quantity=1, unit_price=None, discount=0):
    line = DealProduct(
        decision_cycle=cycle,
        product_catalog_entry=product,
        quantity=quantity,
        unit_price=unit_price,
        discount_percent=discount,
    )
    line.save(user=user, client_id=cycle.client_id)
    return line


def _extra_cycle(account, user, name):
    cycle = DecisionCycle(account=account, owner=user, name=name, is_active=False)
    cycle.save(user=user, client_id=account.client_id)
    return cycle


def _kpi_aggregate(cycle):
    """The KPI 7 binding of the formula, for one cycle."""
    return (
        DecisionCycle.objects
        .filter(pk=cycle.pk)
        .aggregate(total=_PRODUCT_ROLLUP)['total']
    )


def _annotated(cycle):
    """The mass binding of the formula, read back for one cycle."""
    row = annotate_deal_value(DecisionCycle.objects.filter(pk=cycle.pk)).get()
    return getattr(row, DEAL_VALUE_ALIAS)


def _mixed_lines(cycle, user):
    """One line of each shape the catalogue can express today.

    20000 + 10000 + 5000 + 0 + 5000 = 40000
    """
    client_id = cycle.client_id
    _line(cycle, _product(user, client_id, 'One-shot licence'), user,
          quantity=2, unit_price=Decimal('10000'))                       # 20000
    _line(cycle, _product(user, client_id, 'Yearly platform'), user,
          quantity=1, unit_price=Decimal('20000'), discount=Decimal('50'))  # 10000
    _line(cycle, _product(user, client_id, 'Metered API calls',
                          Decimal('0.05')), user, quantity=100000)          # 5000
    _line(cycle, _product(user, client_id, 'Free tier'), user, quantity=3)  # 0
    _line(cycle, _product(user, client_id, 'Catalog priced',
                          Decimal('1250')), user, quantity=4)               # 5000
    return Decimal('40000')


# =============================================================================
# 1. PARITY — accessor == annotation == KPI aggregate
# =============================================================================

class TestParity:

    def test_all_three_bindings_agree_on_mixed_lines(self, cycle, user_a):
        expected = _mixed_lines(cycle, user_a)

        assert cycle.total_deal_value == expected
        assert _annotated(cycle) == expected
        assert _kpi_aggregate(cycle) == expected

    def test_accessor_matches_python_line_totals(self, cycle, user_a):
        """The SQL roll-up and the per-line Python property still agree — the
        invariant the sub-step 1 characterisation pinned."""
        _mixed_lines(cycle, user_a)

        python_total = sum(line.line_total for line in cycle.deal_products.all())
        assert cycle.total_deal_value == python_total

    def test_discount_is_applied_by_every_binding(self, cycle, user_a):
        _line(cycle, _product(user_a, cycle.client_id, 'Discounted'), user_a,
              quantity=1, unit_price=Decimal('10000'), discount=Decimal('25'))

        assert cycle.total_deal_value == Decimal('7500')
        assert _annotated(cycle) == Decimal('7500')
        assert _kpi_aggregate(cycle) == Decimal('7500')

    def test_catalog_default_price_is_used_by_every_binding(self, cycle, user_a):
        _line(cycle, _product(user_a, cycle.client_id, 'Catalog only',
                              Decimal('1250')), user_a, quantity=4)

        assert cycle.total_deal_value == Decimal('5000')
        assert _annotated(cycle) == Decimal('5000')
        assert _kpi_aggregate(cycle) == Decimal('5000')

    def test_cycle_without_lines_is_zero_everywhere(self, cycle):
        assert cycle.total_deal_value == Decimal('0')
        assert _annotated(cycle) == Decimal('0')
        assert _kpi_aggregate(cycle) == Decimal('0')

    def test_lines_of_another_cycle_do_not_leak(self, cycle, account, user_a):
        _line(cycle, _product(user_a, cycle.client_id, 'Mine'), user_a,
              quantity=1, unit_price=Decimal('1000'))
        other = _extra_cycle(account, user_a, 'Other cycle')
        _line(other, _product(user_a, cycle.client_id, 'Theirs'), user_a,
              quantity=1, unit_price=Decimal('9999'))

        assert cycle.total_deal_value == Decimal('1000')
        assert other.total_deal_value == Decimal('9999')


# =============================================================================
# 2. NO FAN-OUT — the annotation composes with the other to-many reads
# =============================================================================

class TestNoFanOut:

    def test_multiple_lines_are_summed_not_multiplied(self, cycle, user_a):
        for index, price in enumerate((100, 200, 50)):
            _line(cycle, _product(user_a, cycle.client_id, f'Line {index}'),
                  user_a, quantity=1, unit_price=Decimal(price))

        assert _annotated(cycle) == Decimal('350')

    def test_composes_with_annotate_cycle_state(self, cycle, five_steps, user_a):
        """Cycle-state annotations bring their own correlated subqueries over
        steps. Composed with the deal-value annotation the amount must not be
        multiplied by the step count."""
        expected = _mixed_lines(cycle, user_a)

        row = annotate_deal_value(
            annotate_cycle_state(DecisionCycle.objects.filter(pk=cycle.pk))
        ).get()

        assert getattr(row, DEAL_VALUE_ALIAS) == expected
        assert row._total_steps_count == len(five_steps)

    def test_composes_with_the_product_exists_facet(self, cycle, user_a):
        """The DC list's product filter is an Exists() over DealProduct (the
        TD-125 path). Combining it with the roll-up must not inflate."""
        from django.db.models import Exists, OuterRef

        expected = _mixed_lines(cycle, user_a)
        target = cycle.deal_products.first().product_catalog_entry

        lines = DealProduct.objects.filter(
            decision_cycle_id=OuterRef('pk'), product_catalog_entry=target,
        )
        row = annotate_deal_value(
            DecisionCycle.objects.filter(pk=cycle.pk).filter(Exists(lines))
        ).get()

        assert getattr(row, DEAL_VALUE_ALIAS) == expected


# =============================================================================
# 3. QUERY BOUND — the N+1 guard
# =============================================================================

class TestQueryBound:

    N = 5

    def _many_cycles(self, account, user, client_id):
        """N cycles of 2 lines each -> grand total N x 3000."""
        product_a = _product(user, client_id, 'Bulk A')
        product_b = _product(user, client_id, 'Bulk B')
        cycles = []
        for index in range(self.N):
            cycle = _extra_cycle(account, user, f'Bulk cycle {index}')
            _line(cycle, product_a, user, quantity=1, unit_price=Decimal('1000'))
            _line(cycle, product_b, user, quantity=1, unit_price=Decimal('2000'))
            cycles.append(cycle)
        return cycles

    def test_grand_total_over_many_cycles_is_one_query(
        self, account, user_a, client_account_a, django_assert_num_queries,
    ):
        from django.db.models import Sum

        self._many_cycles(account, user_a, client_account_a.id)

        with django_assert_num_queries(1):
            total = (
                annotate_deal_value(
                    DecisionCycle.objects.filter(client_id=client_account_a.id)
                )
                .aggregate(grand_total=Sum(DEAL_VALUE_ALIAS))['grand_total']
            )

        assert total == Decimal('15000')            # 5 x 3000

    def test_reading_the_accessor_on_annotated_rows_costs_nothing_extra(
        self, account, user_a, client_account_a, django_assert_num_queries,
    ):
        """The whole point: N cycles, ONE query, accessor free per row."""
        self._many_cycles(account, user_a, client_account_a.id)

        with django_assert_num_queries(1):
            rows = list(
                annotate_deal_value(
                    DecisionCycle.objects.filter(client_id=client_account_a.id)
                )
            )
            values = [row.total_deal_value for row in rows]

        assert sum(values) == Decimal('15000')

    def test_accessor_without_annotation_is_one_query_per_cycle(
        self, account, user_a, client_account_a, django_assert_num_queries,
    ):
        """The N+1 the annotation exists to avoid, asserted so it stays visible:
        a plain queryset costs 1 query + 1 PER cycle."""
        self._many_cycles(account, user_a, client_account_a.id)

        with django_assert_num_queries(1 + self.N):
            rows = list(DecisionCycle.objects.filter(client_id=client_account_a.id))
            values = [row.total_deal_value for row in rows]

        assert sum(values) == Decimal('15000')

    def test_single_instance_accessor_is_exactly_one_query(
        self, cycle, user_a, django_assert_num_queries,
    ):
        _line(cycle, _product(user_a, cycle.client_id, 'Solo'), user_a,
              quantity=1, unit_price=Decimal('1000'))

        with django_assert_num_queries(1):
            assert cycle.total_deal_value == Decimal('1000')


# =============================================================================
# 4. TENANT ISOLATION on the mass path
# =============================================================================

class TestTenantIsolation:

    def test_rollup_is_bounded_by_the_queryset_the_caller_scopes(
        self, cycle, other_tenant_account, user_b, user_a,
    ):
        from django.db.models import Sum

        _line(cycle, _product(user_a, cycle.client_id, 'Tenant A line'), user_a,
              quantity=1, unit_price=Decimal('1000'))
        foreign = _extra_cycle(other_tenant_account, user_b, 'Tenant B cycle')
        _line(foreign, _product(user_b, foreign.client_id, 'Tenant B line'),
              user_b, quantity=1, unit_price=Decimal('7777'))

        total = (
            annotate_deal_value(
                DecisionCycle.objects.filter(client_id=cycle.client_id)
            )
            .aggregate(grand_total=Sum(DEAL_VALUE_ALIAS))['grand_total']
        )

        assert total == Decimal('1000')
