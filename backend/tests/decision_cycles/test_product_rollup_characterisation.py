# backend/tests/decision_cycles/test_product_rollup_characterisation.py
"""
CHARACTERISATION of the product amount roll-up AS IT EXISTS TODAY (Sprint C, 1/7).

This module changes NO behaviour and asserts NO desired behaviour. It pins what
the code computes right now, so the Sprint C repoint (sub-step 4) has a
regression floor and any change becomes visible as a failing assertion.

WHAT EXISTS TODAY (verified before writing this file)
-----------------------------------------------------
* Per line — ``DealProduct.line_total``, a read-only Python property:
  ``app_modules/decision_cycles/models.py:927-938``

      price = unit_price OR product_catalog_entry.default_unit_price OR -> 0
      line_total = quantity * price * (1 - discount_percent / 100)

* Per decision cycle — there is NO ``DecisionCycle.total_deal_value`` and no
  stored DC total. The only server-side sum of a cycle's lines is the SQL
  expression backing KPI 7:
  ``app_modules/bi/definitions/decision_cycles.py:40-57``
  (``_LINE_VALUE`` per line, ``_PRODUCT_ROLLUP = Coalesce(Sum(_LINE_VALUE), 0)``)

  That SQL expression is a SECOND, independent implementation of the same
  formula. Their equivalence is asserted below: it is the property the repoint
  must preserve.

WHAT DOES NOT EXIST TODAY (the gaps this file documents, and does NOT fix)
--------------------------------------------------------------------------
* No pricing TYPE (one-shot / subscription / usage) on either model.
* No periodicity, term, duration or billing-frequency field anywhere.
  -> "20k/yr x 3yr = 60k" is NOT computable; the formula has no term factor.
* No estimated-volume field.
  -> a usage-metered line contributes exactly like any other line.
* No 0-100 bound on ``discount_percent`` (TD-74) -> a >100% discount yields a
  NEGATIVE line total.
* No runtime path writes ``DecisionCycle.estimated_value`` (TD-75).

The field-name snapshots below are deliberate TRIPWIRES: when sub-step 2 adds
pricing-type / term / volume fields, those tests fail and must be updated in the
same commit that adds them. That is the intent, not a defect.

Test data is built through the real create path (``Model.save(user=, client_id=)``),
mirroring ``tests/decision_cycles/test_deal_product.py`` and
``tests/bi/test_kpi_dc_money.py``. ``line_total`` is never hand-set: it cannot be
-- it is a property, not a column.
"""

from decimal import Decimal

import pytest

from app_modules.decision_cycles.models import DealProduct, DecisionCycle
from app_modules.product_catalog.models import ProductCatalog

# The DC-level roll-up under characterisation. Importing the private expression
# is intentional: it IS the artefact being pinned, and sub-step 4 will move or
# rebind it -- this import is the tripwire that says so.
from app_modules.bi.definitions.decision_cycles import _PRODUCT_ROLLUP


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


def _sql_rollup(cycle):
    """The DC-level total as the ONLY server-side roll-up computes it today
    (the KPI 7 SQL expression), evaluated for a single cycle."""
    return (
        DecisionCycle.objects
        .filter(pk=cycle.pk)
        .aggregate(total=_PRODUCT_ROLLUP)['total']
    )


# =============================================================================
# 1. line_total — the formula that IS implemented
# =============================================================================

class TestLineTotalFormula:
    """qty x price x (1 - discount/100). No other factor exists."""

    def test_quantity_times_unit_price(self, cycle, user_a):
        product = _product(user_a, cycle.client_id, 'One-shot licence', None)
        line = _line(cycle, product, user_a, quantity=2, unit_price=Decimal('10000'))

        assert line.line_total == Decimal('20000')

    def test_fifty_percent_discount_halves_the_line(self, cycle, user_a):
        product = _product(user_a, cycle.client_id, 'One-shot licence 50', None)
        line = _line(
            cycle, product, user_a,
            quantity=2, unit_price=Decimal('10000'), discount=Decimal('50'),
        )

        assert line.line_total == Decimal('10000')

    def test_price_falls_back_to_catalog_default(self, cycle, user_a):
        product = _product(user_a, cycle.client_id, 'Catalog priced', Decimal('7500'))
        line = _line(cycle, product, user_a, quantity=4, unit_price=None)

        assert line.line_total == Decimal('30000')

    def test_no_price_anywhere_yields_zero(self, cycle, user_a):
        product = _product(user_a, cycle.client_id, 'Free tier', None)
        line = _line(cycle, product, user_a, quantity=3, unit_price=None)

        # models.py:932-933 returns a bare 0 (int), not Decimal('0').
        assert line.line_total == 0

    def test_zero_discount_is_the_default(self, cycle, user_a):
        product = _product(user_a, cycle.client_id, 'Default discount', None)
        line = _line(cycle, product, user_a, quantity=1, unit_price=Decimal('1000'))

        assert line.discount_percent == Decimal('0')
        assert line.line_total == Decimal('1000')


# =============================================================================
# 2. SUBSCRIPTION — the term factor does not exist (GAP)
# =============================================================================

class TestSubscriptionTermGap:
    """The PO rule "20k/yr x 3yr engagement = 60k" is NOT computable today.

    Nothing on ProductCatalog, DealProduct or DecisionCycle can carry a term,
    a duration or a billing frequency, so the roll-up has no factor to apply.
    A 3-year subscription entered at its yearly price yields the YEARLY amount.
    """

    def test_yearly_price_is_not_multiplied_by_any_term(self, cycle, user_a):
        product = _product(user_a, cycle.client_id, 'SaaS subscription', None)
        # "20k per year, 3-year engagement" -- the 3 years are unrepresentable.
        line = _line(cycle, product, user_a, quantity=1, unit_price=Decimal('20000'))

        assert line.line_total == Decimal('20000')      # the PO rule expects 60000
        assert line.line_total != Decimal('60000')

    def test_no_term_or_periodicity_field_exists(self):
        """Tripwire: fails the day a term/periodicity field is added."""
        names = _all_field_names()
        for candidate in (
            'duration', 'duration_months', 'term', 'contract_term',
            'engagement_duration', 'billing_frequency', 'periodicity',
            'pricing_term', 'contract_payment_term', 'recurrence',
        ):
            assert candidate not in names, (
                f"'{candidate}' now exists -- update this characterisation test "
                f"together with the roll-up formula."
            )


# =============================================================================
# 3. USAGE-METERED — no estimated volume (GAP)
# =============================================================================

class TestUsageMeteredGap:
    """A usage-metered product cannot be distinguished, and carries no volume.

    There is no pricing type, so a "usage" product is an ordinary catalog entry;
    there is no estimated-volume input, so the only quantity-like input is
    ``quantity``. A usage line therefore contributes quantity x price, exactly
    like a one-shot line -- it never produces 0 and never reads a volume.
    """

    def test_usage_line_behaves_exactly_like_any_other_line(self, cycle, user_a):
        product = _product(user_a, cycle.client_id, 'API calls (metered)', Decimal('0.05'))
        # The only volume-ish input available today is `quantity`.
        line = _line(cycle, product, user_a, quantity=100000, unit_price=None)

        assert line.line_total == Decimal('5000.00')

    def test_no_estimated_volume_field_exists(self):
        """Tripwire: fails the day an estimated-volume field is added."""
        names = _all_field_names()
        for candidate in (
            'estimated_volume', 'estimated_quantity', 'estimated_units',
            'volume', 'usage_volume', 'unit_of_measure', 'units_per',
        ):
            assert candidate not in names, (
                f"'{candidate}' now exists -- update this characterisation test."
            )


# =============================================================================
# 4. PRICING TYPE — absent from both models (GAP)
# =============================================================================

class TestPricingTypeGap:

    def test_no_pricing_type_field_exists(self):
        names = _all_field_names()
        for candidate in ('pricing_type', 'product_type', 'price_type', 'kind', 'type'):
            assert candidate not in names, (
                f"'{candidate}' now exists -- update this characterisation test."
            )

    def test_product_catalog_field_snapshot(self):
        """The catalog carries exactly ONE pricing field today."""
        assert {f.name for f in ProductCatalog._meta.concrete_fields} == {
            'id', 'client_id', 'created_by', 'updated_by', 'created_at', 'updated_at',
            'name', 'description', 'value_proposition',
            'default_unit_price',
        }

    def test_deal_product_field_snapshot(self):
        assert {f.name for f in DealProduct._meta.concrete_fields} == {
            'id', 'client_id', 'created_by', 'updated_by', 'created_at', 'updated_at',
            'decision_cycle', 'product_catalog_entry',
            'quantity', 'unit_price', 'discount_percent', 'notes',
        }


def _all_field_names():
    return (
        {f.name for f in ProductCatalog._meta.concrete_fields}
        | {f.name for f in DealProduct._meta.concrete_fields}
        | {f.name for f in DecisionCycle._meta.concrete_fields}
    )


# =============================================================================
# 5. DC-level roll-up — what actually sums the lines
# =============================================================================

class TestDecisionCycleRollUp:

    def test_no_total_deal_value_attribute(self):
        """Tripwire: there is no DC-level total today, stored or computed."""
        assert not hasattr(DecisionCycle, 'total_deal_value')
        assert 'total_deal_value' not in {
            f.name for f in DecisionCycle._meta.concrete_fields
        }

    def test_rollup_sums_a_one_shot_and_a_subscription_line(self, cycle, user_a):
        one_shot = _product(user_a, cycle.client_id, 'Implementation', None)
        subscription = _product(user_a, cycle.client_id, 'Platform yearly', None)
        line_a = _line(cycle, one_shot, user_a, quantity=2, unit_price=Decimal('10000'))
        line_b = _line(cycle, subscription, user_a, quantity=1, unit_price=Decimal('20000'))

        assert _sql_rollup(cycle) == Decimal('40000')                    # 20000 + 20000
        assert _sql_rollup(cycle) == line_a.line_total + line_b.line_total

    def test_rollup_reflects_a_discounted_line(self, cycle, user_a):
        full = _product(user_a, cycle.client_id, 'Full price', None)
        discounted = _product(user_a, cycle.client_id, 'Discounted', None)
        _line(cycle, full, user_a, quantity=1, unit_price=Decimal('10000'))
        _line(cycle, discounted, user_a, quantity=1, unit_price=Decimal('10000'),
              discount=Decimal('25'))

        assert _sql_rollup(cycle) == Decimal('17500')                    # 10000 + 7500

    def test_rollup_uses_the_catalog_default_when_no_override(self, cycle, user_a):
        product = _product(user_a, cycle.client_id, 'Catalog only', Decimal('1250'))
        _line(cycle, product, user_a, quantity=4, unit_price=None)

        assert _sql_rollup(cycle) == Decimal('5000')

    def test_rollup_is_zero_for_a_cycle_without_lines(self, cycle):
        assert _sql_rollup(cycle) == Decimal('0')

    def test_sql_rollup_equals_python_line_total_sum(self, cycle, user_a):
        """The two independent implementations agree. THIS is the property the
        sub-step 4 repoint must preserve."""
        specs = [
            (Decimal('10000'), 2, Decimal('0')),
            (Decimal('20000'), 1, Decimal('50')),
            (Decimal('333.33'), 3, Decimal('10')),
            (None, 5, Decimal('0')),            # catalog default 1000 -> 5000
        ]
        for index, (unit_price, quantity, discount) in enumerate(specs):
            product = _product(
                user_a, cycle.client_id, f'Mixed line {index}', Decimal('1000'),
            )
            _line(cycle, product, user_a, quantity=quantity,
                  unit_price=unit_price, discount=discount)

        python_total = sum(
            line.line_total for line in cycle.deal_products.all()
        )
        assert _sql_rollup(cycle) == python_total
        # 20000 + 10000 + 899.991 + 5000
        assert python_total == Decimal('35899.991')


# =============================================================================
# 6. discount_percent is unbounded (TD-74) — documented, NOT fixed here
# =============================================================================

class TestDiscountIsUnbounded:
    """No CheckConstraint and no DRF validator bounds discount_percent to 0-100
    (TD-74). Both implementations of the formula therefore accept out-of-range
    values and produce nonsense amounts. Pinned here to motivate sub-step 3.
    """

    def test_discount_above_100_makes_the_line_negative(self, cycle, user_a):
        product = _product(user_a, cycle.client_id, 'Over-discounted', None)
        line = _line(cycle, product, user_a, quantity=1, unit_price=Decimal('10000'),
                     discount=Decimal('150'))

        assert line.line_total == Decimal('-5000')
        assert _sql_rollup(cycle) == Decimal('-5000')

    def test_negative_discount_inflates_the_line(self, cycle, user_a):
        product = _product(user_a, cycle.client_id, 'Negative discount', None)
        line = _line(cycle, product, user_a, quantity=1, unit_price=Decimal('10000'),
                     discount=Decimal('-50'))

        assert line.line_total == Decimal('15000')

    def test_no_database_constraint_guards_the_range(self):
        from django.core.validators import MaxValueValidator, MinValueValidator

        assert {c.name for c in DealProduct._meta.constraints} == set()

        # The only validator attached is the DecimalValidator that every
        # DecimalField carries (max_digits / decimal_places) -- no range guard.
        validators = DealProduct._meta.get_field('discount_percent').validators
        assert not any(
            isinstance(v, (MinValueValidator, MaxValueValidator)) for v in validators
        )


# =============================================================================
# 7. estimated_value stays untouched by the lines (TD-75 floor)
# =============================================================================

class TestEstimatedValueIsNotFedByLines:
    """Today no runtime path rolls lines up into DecisionCycle.estimated_value.
    Sub-step 4 changes this; until then the floor is "adding lines changes
    nothing".
    """

    def test_adding_lines_leaves_estimated_value_none(self, cycle, user_a):
        assert cycle.estimated_value is None

        product = _product(user_a, cycle.client_id, 'Roll-up probe', None)
        _line(cycle, product, user_a, quantity=2, unit_price=Decimal('10000'))

        cycle.refresh_from_db()
        assert cycle.estimated_value is None
        assert _sql_rollup(cycle) == Decimal('20000')
