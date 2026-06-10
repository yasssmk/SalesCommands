# backend/tests/decision_cycles/test_cycle_model_invariants.py
"""
Tests for DecisionCycle model-level invariants.

Covers:
  - Single-active-cycle invariant: saving a cycle with is_active=True
    deactivates all other active cycles for the same (account, client_id).
  - Saving an inactive cycle does NOT deactivate other cycles.
  - unique_together (account, name, client_id) raises IntegrityError on
    duplicate names within the same tenant.
"""

import pytest
from django.db import IntegrityError

from app_modules.decision_cycles.models import DecisionCycle


# =========================================================================
# SINGLE-ACTIVE-CYCLE INVARIANT
# =========================================================================

class TestSingleActiveCycleInvariant:

    @pytest.mark.django_db
    def test_new_active_cycle_deactivates_previous(
        self, cycle, account, user_a,
    ):
        """Creating a second active cycle deactivates the first."""
        second = DecisionCycle(
            account=account,
            owner=user_a,
            name='Second Cycle',
            is_active=True,
        )
        second.save(user=user_a, client_id=account.client_id)

        cycle.refresh_from_db()
        assert cycle.is_active is False
        assert second.is_active is True

    @pytest.mark.django_db
    def test_saving_inactive_cycle_leaves_others_untouched(
        self, cycle, account, user_a,
    ):
        """Saving an inactive cycle does NOT deactivate the active one."""
        inactive = DecisionCycle(
            account=account,
            owner=user_a,
            name='Inactive Cycle',
            is_active=False,
        )
        inactive.save(user=user_a, client_id=account.client_id)

        cycle.refresh_from_db()
        assert cycle.is_active is True
        assert inactive.is_active is False

    @pytest.mark.django_db
    def test_reactivating_cycle_deactivates_current(
        self, cycle, account, user_a,
    ):
        """Re-saving an existing cycle as active deactivates the other."""
        second = DecisionCycle(
            account=account,
            owner=user_a,
            name='Second Cycle',
            is_active=False,
        )
        second.save(user=user_a, client_id=account.client_id)

        assert cycle.is_active is True

        second.is_active = True
        second.save(user=user_a, update_fields=['is_active'])

        cycle.refresh_from_db()
        assert cycle.is_active is False
        assert second.is_active is True


# =========================================================================
# UNIQUE TOGETHER (account, name, client_id)
# =========================================================================

class TestUniqueNamePerAccountTenant:

    @pytest.mark.django_db
    def test_duplicate_name_same_account_raises(self, cycle, account, user_a):
        """Two cycles with the same name on the same (account, client_id) violate the constraint."""
        duplicate = DecisionCycle(
            account=account,
            owner=user_a,
            name=cycle.name,
            is_active=False,
        )
        with pytest.raises(IntegrityError):
            duplicate.save(user=user_a, client_id=account.client_id)
