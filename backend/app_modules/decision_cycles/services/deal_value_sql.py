# app_modules/decision_cycles/services/deal_value_sql.py
"""
Single source of truth for a DecisionCycle's deal value (the product roll-up).

ONE formula, declared once in ``_line_value()``:

    line value = quantity
               x Coalesce(unit_price, catalog default_unit_price, 0)
               x (1 - discount_percent / 100)

    deal value = Σ line value over the cycle's deal_products (0 when none)

It is the SQL twin of ``DealProduct.line_total`` (models.py) — the parity of the
two is asserted by tests/decision_cycles/test_product_rollup_characterisation.py
and tests/decision_cycles/test_deal_value_rollup.py.

TWO BINDINGS, ONE FORMULA
-------------------------
The same per-line expression is bound two ways because the two read shapes need
different SQL, and building both from ``_line_value()`` is what keeps them from
drifting apart:

* ``DEAL_VALUE_SUM`` — the JOIN form, evaluated from a DecisionCycle queryset
  with ``.aggregate()``. This is what the KPI 7 definitions consume
  (app_modules/bi/definitions/decision_cycles.py). A scalar aggregate over a
  SINGLE to-many relation cannot double-count.

* ``annotate_deal_value(queryset)`` — the PER-ROW form, an isolated correlated
  Subquery grouped by decision_cycle. Mass roll-ups (a list page, a team or user
  pipeline, any Σ over many cycles) MUST use this instead of touching
  ``DecisionCycle.total_deal_value`` in a Python loop, which would be one query
  per cycle.

  The subquery form is deliberate, mirroring ``_isolated_step_count`` in
  derivation_sql.py: a plain ``.annotate(Sum('deal_products__...'))`` would join
  the to-many relation into the outer row set, so combining it with ANY other
  to-many join (or with a second aggregate) would multiply rows and inflate the
  total. Correlated + grouped, it stays a single scalar per cycle and composes
  safely with annotate_cycle_state() and with the product Exists() facet.

No stored column and no write: the value follows the lines, so it is derived on
read. ``DecisionCycle.estimated_value`` is a separate MANUAL field — this module
does not read or write it (its reconciliation is TD-75, a later sub-step).
"""

from decimal import Decimal

from django.db.models import (
    DecimalField,
    ExpressionWrapper,
    F,
    OuterRef,
    Subquery,
    Sum,
    Value,
)
from django.db.models.functions import Coalesce


# Alias for the per-row annotation. Underscored so it can never clash with a
# model field or a serializer output key (same convention as derivation_sql.py).
DEAL_VALUE_ALIAS = '_deal_value'

# Money output field for the roll-up. Wider than the 14,2 columns it sums so a
# multi-line cycle cannot overflow, and 4 decimals so a percentage discount does
# not silently round each line before the Σ.
_MONEY = DecimalField(max_digits=24, decimal_places=4)

# Price resolution + the Σ share the same output field as the lines they read.
_PRICE = DecimalField(max_digits=14, decimal_places=2)


def _line_value(prefix=''):
    """The per-line money expression — THE formula, declared once.

    ``prefix`` binds it to the row it is evaluated from: '' when the queryset IS
    DealProduct (subquery form), 'deal_products__' when it is DecisionCycle
    (join form).
    """
    return ExpressionWrapper(
        F(f'{prefix}quantity')
        * Coalesce(
            F(f'{prefix}unit_price'),
            F(f'{prefix}product_catalog_entry__default_unit_price'),
            Value(Decimal('0')),
            output_field=_PRICE,
        )
        * (
            Value(Decimal('1'))
            - F(f'{prefix}discount_percent') / Value(Decimal('100'))
        ),
        output_field=_MONEY,
    )


def _zero_coalesced(expression):
    """A cycle with no lines has a deal value of 0, never NULL."""
    return Coalesce(expression, Value(Decimal('0')), output_field=_MONEY)


# JOIN form — for `DecisionCycle.objects...aggregate(total=DEAL_VALUE_SUM)`.
DEAL_VALUE_SUM = _zero_coalesced(Sum(_line_value('deal_products__')))


def deal_value_subquery():
    """PER-ROW form — an isolated correlated Subquery over a cycle's lines,
    grouped by decision_cycle so it returns exactly one scalar per outer row
    (0 when the cycle has no line). Built lazily: it needs the DealProduct
    model, which imports this package back."""
    from ..models import DealProduct

    per_cycle_total = (
        DealProduct.objects
        .filter(decision_cycle_id=OuterRef('pk'))
        .order_by()
        .values('decision_cycle_id')
        .annotate(_total=Sum(_line_value()))
        .values('_total')[:1]
    )
    return _zero_coalesced(Subquery(per_cycle_total, output_field=_MONEY))


def annotate_deal_value(queryset):
    """Annotate a DecisionCycle queryset with its product roll-up under
    ``DEAL_VALUE_ALIAS``.

    This is the ONLY performant path for a mass roll-up. Reading
    ``cycle.total_deal_value`` on an annotated row costs no extra query (the
    property reads the annotation); on a non-annotated instance it costs one.
    """
    return queryset.annotate(**{DEAL_VALUE_ALIAS: deal_value_subquery()})


def deal_value_for(cycle):
    """The deal value of ONE cycle, in one query, from the same formula.

    Used by ``DecisionCycle.total_deal_value`` when the instance carries no
    annotation. Never call this in a loop — use annotate_deal_value().
    """
    from ..models import DecisionCycle

    return (
        DecisionCycle.objects
        .filter(pk=cycle.pk)
        .aggregate(_total=DEAL_VALUE_SUM)['_total']
    )
