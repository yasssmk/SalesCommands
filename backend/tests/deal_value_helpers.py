# backend/tests/deal_value_helpers.py
"""
Shared test helper: give a DecisionCycle a known deal value.

Since TD-75 the money KPIs (PIPELINE_VALUE / REVENUE_WON, campaign objectives,
personal objectives, quotas) sum ``DecisionCycle.total_deal_value`` — the
DERIVED product roll-up — instead of the manual ``estimated_value`` field that
no runtime path ever populated. Tests that used to seed an amount with
``estimated_value=1500`` must now give the cycle a real product line worth that
amount, through the real create path.

One helper, one home: every test module that needs a priced cycle imports this
rather than re-deriving the roll-up, so a change to the formula cannot leave
some suites seeding amounts a different way.
"""

import uuid
from decimal import Decimal


def give_deal_value(cycle, amount, *, user=None, quantity=1):
    """Attach ONE DealProduct line to ``cycle`` so its total_deal_value == amount.

    The line carries the amount as a unit_price override with no discount, so
    the roll-up (quantity x price x (1 - discount/100)) returns exactly
    ``amount``. Each call creates its own catalogue entry, so a cycle can carry
    several lines without hitting the
    (decision_cycle, product_catalog_entry) uniqueness constraint.

    Returns the created DealProduct (None when ``amount`` is None, so callers
    can pass their existing "no amount" fixtures straight through).
    """
    if amount is None:
        return None

    from app_modules.decision_cycles.models import DealProduct
    from app_modules.product_catalog.models import ProductCatalog

    actor = user or cycle.owner or cycle.created_by

    product = ProductCatalog(name=f'Test product {uuid.uuid4()}')
    product.save(user=actor, client_id=cycle.client_id)

    line = DealProduct(
        decision_cycle=cycle,
        product_catalog_entry=product,
        quantity=quantity,
        unit_price=Decimal(str(amount)) / Decimal(str(quantity)),
    )
    line.save(user=actor, client_id=cycle.client_id)
    return line
