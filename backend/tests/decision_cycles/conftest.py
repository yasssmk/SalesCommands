# backend/tests/decision_cycles/conftest.py
"""
Pytest fixtures for the decision_cycles module tests.

This conftest COMPLEMENTS the fixtures declared in
backend/tests/signals/conftest.py. We re-export the tenant / user /
account / activity / contact fixtures and add decision-cycle-specific
ones: an active cycle, the 5-step linked-list pipeline, and callable
factories for PLANNED and COMPLETED activities on a given step.

Re-exported from tests/signals/conftest.py (same pattern as
tests/ai_pipelines/conftest.py):
    pytest_configure, _jwt_only_no_csrf,
    tenant_a_id, client_account_a, role_individual_a, user_a,
    account, contact, api, authenticate, authed_api_a

New fixtures (decision_cycles-specific):
    cycle              -- active DecisionCycle on tenant A account
    five_steps         -- ordered list of 5 DecisionStep (linked-list)
    planned_activity_on_step   -- callable factory -> Activity PLANNED
    completed_activity_on_step -- callable factory -> Activity COMPLETED
"""

from datetime import timedelta

import pytest
from django.utils import timezone

from tests.signals.conftest import (  # noqa: F401
    pytest_configure,
    _jwt_only_no_csrf,
    tenant_a_id,
    tenant_b_id,
    client_account_a,
    client_account_b,
    role_individual_a,
    role_individual_b,
    user_a,
    user_b,
    account,
    other_tenant_account,
    activity,
    other_tenant_activity,
    contact,
    contact_extra,
    api,
    authenticate,
    authed_api_a,
    authed_api_b,
    cache_invalidation_calls,
)


# =============================================================================
# DECISION CYCLE — active cycle on tenant A
# =============================================================================

@pytest.fixture
def cycle(db, account, user_a):
    """
    Active DecisionCycle tied to the tenant-A CompanyAccount.

    Uses the project's standard save(user=, client_id=) pattern so
    that ModuleBaseModel audit fields and ClientScopeManager scoping
    are populated identically to production.
    """
    from app_modules.decision_cycles.models import DecisionCycle

    c = DecisionCycle(
        account=account,
        owner=user_a,
        name='Test Cycle',
        is_active=True,
    )
    c.save(user=user_a, client_id=account.client_id)
    return c


# =============================================================================
# FIVE STEPS — mirrors _create_pipeline_steps() from views.py l.281-314
# =============================================================================

@pytest.fixture
def five_steps(db, cycle, user_a):
    """
    The 5 auto-created DecisionStep instances in linked-list order,
    mirroring the production auto-creation logic in
    DecisionCycleViewSet._create_pipeline_steps().

    Iterates PIPELINE_STEPS_CONFIG (constants.py l.39-70) and builds
    each step with: name from label, stage from value, order from
    config, status NOT_STARTED, previous_step chained.

    Returns: list of 5 DecisionStep ordered by `order` (1-5).
    """
    from app_modules.decision_cycles.constants import (
        DecisionStepStatus,
        PIPELINE_STEPS_CONFIG,
    )
    from app_modules.decision_cycles.models import DecisionStep

    steps = []
    previous = None

    for config in PIPELINE_STEPS_CONFIG:
        step = DecisionStep(
            cycle=cycle,
            name=config['step'].label,
            stage=config['step'].value,
            order=config['order'],
            status=DecisionStepStatus.NOT_STARTED,
            previous_step=previous,
            expected_end=None,
        )
        step.save(user=user_a, client_id=cycle.client_id)
        steps.append(step)
        previous = step

    return steps


# =============================================================================
# ACTIVITY FACTORIES — callables that create Activities on a given step
# =============================================================================

@pytest.fixture
def planned_activity_on_step(db, account, user_a):
    """
    Callable factory: ``planned_activity_on_step(step, **overrides)``

    Creates and returns an Activity with status PLANNED, linked to the
    step's cycle and the step itself. Default scheduled_date is 7 days
    from now; override any field via kwargs.
    """
    from app_modules.activities.constants import ActivityStatus, ActivityType
    from app_modules.activities.models import Activity

    def _factory(step, **overrides):
        defaults = dict(
            title='Planned activity',
            activity_type=ActivityType.MEETING,
            status=ActivityStatus.PLANNED,
            account=account,
            owner=user_a,
            decision_cycle=step.cycle,
            decision_step=step,
            scheduled_date=timezone.now().date() + timedelta(days=7),
        )
        defaults.update(overrides)
        a = Activity(**defaults)
        a.save(user=user_a, client_id=account.client_id)
        return a

    return _factory


@pytest.fixture
def completed_activity_on_step(db, account, user_a):
    """
    Callable factory: ``completed_activity_on_step(step, **overrides)``

    Creates and returns an Activity with status COMPLETED and
    completed_at populated, linked to the step's cycle and the step
    itself. Default completed_at is now; override any field via kwargs.
    """
    from app_modules.activities.constants import ActivityStatus, ActivityType
    from app_modules.activities.models import Activity

    def _factory(step, **overrides):
        defaults = dict(
            title='Completed activity',
            activity_type=ActivityType.MEETING,
            status=ActivityStatus.COMPLETED,
            account=account,
            owner=user_a,
            decision_cycle=step.cycle,
            decision_step=step,
            completed_at=timezone.now(),
            scheduled_date=timezone.now().date() - timedelta(days=3),
        )
        defaults.update(overrides)
        a = Activity(**defaults)
        a.save(user=user_a, client_id=account.client_id)
        return a

    return _factory


# =============================================================================
# PRODUCT CATALOG ENTRY — used by DealProduct fixtures
# =============================================================================

@pytest.fixture
def product_catalog_entry(db, client_account_a, user_a):
    """
    A single ProductCatalog entry on tenant A.
    """
    from app_modules.product_catalog.models import ProductCatalog

    entry = ProductCatalog(
        name='Enterprise License',
        description='Annual enterprise subscription',
        default_unit_price=10000,
    )
    entry.save(user=user_a, client_id=client_account_a.id)
    return entry


# =============================================================================
# DEAL HEALTH SNAPSHOT — latest snapshot on the cycle
# =============================================================================

@pytest.fixture
def deal_health_snapshot(db, cycle, user_a):
    """
    A DealHealthSnapshot attached to the default test cycle.
    """
    from app_modules.decision_cycles.models import DealHealthSnapshot

    snap = DealHealthSnapshot(
        decision_cycle=cycle,
        diagnostic={
            'global_diagnostic': 'Test diagnostic',
            'dimensions': [],
            'gaps': [],
            'levers': {},
            'themes': [],
        },
    )
    snap.save(user=user_a, client_id=cycle.client_id)
    return snap


# =============================================================================
# DEAL PRODUCT — line item on the cycle
# =============================================================================

@pytest.fixture
def deal_product(db, cycle, product_catalog_entry, user_a):
    """
    A DealProduct linking the product_catalog_entry to the test cycle.
    """
    from app_modules.decision_cycles.models import DealProduct

    dp = DealProduct(
        decision_cycle=cycle,
        product_catalog_entry=product_catalog_entry,
        quantity=2,
        unit_price=9500,
    )
    dp.save(user=user_a, client_id=cycle.client_id)
    return dp
