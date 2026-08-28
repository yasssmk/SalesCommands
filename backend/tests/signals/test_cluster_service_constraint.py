# backend/tests/signals/test_cluster_service_constraint.py
"""
Constraint cluster tests for SignalClusterService.

Constraint clusters on `nature` (ConstraintNature) at READ TIME — the same
mechanism as the TechStack cluster (which groups on tech_name_normalized via
the key= param of _group_by_canonical_key), calqued here. Two differences from
tech:
  * the grouping key is `nature` (always present -> no null bucket);
  * constraint is DC-SCOPED ONLY -- never surfaced at the account level.

Mirrors tests/signals/test_cluster_service_techstack.py.
"""

from django.db import connection
from django.test.utils import CaptureQueriesContext

import pytest

from app_modules.signals.constants import (
    ConstraintNature,
    Rigidity,
    SignalSource,
)
from app_modules.signals.models import ConstraintSignal
from app_modules.signals.serializers import (
    SignalClusterDetailSerializer,
    SignalClusterListSerializer,
)
from app_modules.signals.services import SignalClusterService


pytestmark = pytest.mark.django_db


# =============================================================================
# HELPERS
# =============================================================================

def _mk_constraint(account, activity, decision_cycle, user_a, nature, *,
                   summary='A requirement', rigidity=Rigidity.FIRM,
                   source=SignalSource.MANUAL, **extra):
    """
    Create + persist a ConstraintSignal in one decision cycle. MANUAL source
    lands VALIDATED; pass source=LLM_EXTRACTED for a PENDING member.
    """
    sig = ConstraintSignal(
        account=account,
        source_activity=activity,
        decision_cycle=decision_cycle,
        nature=nature,
        summary=summary,
        rigidity=rigidity,
        source=source,
        **extra,
    )
    sig.save(user=user_a, client_id=account.client_id)
    return sig


def _list_constraint(account, decision_cycle=None, **kwargs):
    return SignalClusterService.list_clusters_for_account(
        account_id=account.id,
        signal_type='constraint',
        decision_cycle_id=(decision_cycle.id if decision_cycle else None),
        **kwargs,
    )


# =============================================================================
# GROUPING — same nature collapses; different natures stay apart
# =============================================================================

class TestConstraintClusterGrouping:

    def test_two_constraints_same_nature_form_one_cluster(
        self, account, activity, decision_cycle, user_a,
    ):
        # The smoke DUPLICATE case: two CONTRACTUAL (e.g. 2x GDPR) -> ONE cluster.
        _mk_constraint(account, activity, decision_cycle, user_a,
                       ConstraintNature.CONTRACTUAL, summary='GDPR compliance')
        _mk_constraint(account, activity, decision_cycle, user_a,
                       ConstraintNature.CONTRACTUAL, summary='GDPR mandatory')

        clusters = _list_constraint(account, decision_cycle)

        assert len(clusters) == 1
        cluster = clusters[0]
        assert cluster['canonical_key'] == 'CONTRACTUAL'
        assert cluster['signal_type'] == 'constraint'
        assert cluster['signal_count'] == 2

    def test_different_natures_form_distinct_clusters(
        self, account, activity, decision_cycle, user_a,
    ):
        _mk_constraint(account, activity, decision_cycle, user_a,
                       ConstraintNature.TECHNICAL)
        _mk_constraint(account, activity, decision_cycle, user_a,
                       ConstraintNature.FINANCIAL)

        clusters = _list_constraint(account, decision_cycle)

        assert len(clusters) == 2
        assert sorted(c['canonical_key'] for c in clusters) == [
            'FINANCIAL', 'TECHNICAL',
        ]
        assert all(c['signal_count'] == 1 for c in clusters)

    def test_three_of_one_nature_form_one_cluster(
        self, account, activity, decision_cycle, user_a,
    ):
        # NON-VACUITY TARGET: re-key the grouping on `s.id` (instead of
        # `s.nature`) in signal_cluster_service and this fails (3 clusters).
        for i in range(3):
            _mk_constraint(account, activity, decision_cycle, user_a,
                           ConstraintNature.SECURITY, summary=f'security req {i}')

        clusters = _list_constraint(account, decision_cycle)

        assert len(clusters) == 1
        assert clusters[0]['signal_count'] == 3
        assert clusters[0]['canonical_key'] == 'SECURITY'


# =============================================================================
# DC-SCOPING — constraint is never surfaced at the account level
# =============================================================================

class TestConstraintClusterDCScoped:

    def test_no_decision_cycle_returns_empty(
        self, account, activity, decision_cycle, user_a,
    ):
        _mk_constraint(account, activity, decision_cycle, user_a,
                       ConstraintNature.TECHNICAL)

        # Account-level (no decision_cycle_id) -> constraint is DC-only -> [].
        assert _list_constraint(account, None) == []
        # But scoped to the DC it appears.
        assert len(_list_constraint(account, decision_cycle)) == 1

    def test_other_decision_cycle_does_not_leak(
        self, account, activity, decision_cycle, user_a,
    ):
        from app_modules.decision_cycles.models import DecisionCycle
        other_dc = DecisionCycle(account=account, name='Other cycle')
        other_dc.save(user=user_a, client_id=account.client_id)

        _mk_constraint(account, activity, decision_cycle, user_a,
                       ConstraintNature.TECHNICAL)

        # The other DC has no constraints of its own.
        assert _list_constraint(account, other_dc) == []


# =============================================================================
# CLUSTER CONTRACT — neutral axes, headline text, departments
# =============================================================================

class TestConstraintClusterContract:

    def test_neutral_values_on_inapplicable_keys(
        self, account, activity, decision_cycle, user_a,
    ):
        _mk_constraint(account, activity, decision_cycle, user_a,
                       ConstraintNature.FUNCTIONAL,
                       summary='Real-time reporting required')

        cluster = _list_constraint(account, decision_cycle)[0]

        # Detached from what x dimension -> neutral.
        assert cluster['what'] is None
        assert cluster['dimension'] is None
        assert cluster['max_scope_level'] is None
        # No constraint scorer -> neutral floor.
        assert cluster['priority_score'] == 0
        # The representative constraint text is the headline.
        assert cluster['summary'] == 'Real-time reporting required'

    def test_departments_aggregate_across_members(
        self, account, activity, decision_cycle, user_a,
    ):
        from app_modules.core_modules.models import StandardDepartment
        it_dept, _ = StandardDepartment.objects.get_or_create(name='IT')

        _mk_constraint(account, activity, decision_cycle, user_a,
                       ConstraintNature.TECHNICAL, target_department=it_dept)
        _mk_constraint(account, activity, decision_cycle, user_a,
                       ConstraintNature.TECHNICAL)  # BUSINESS (no dept)

        cluster = _list_constraint(account, decision_cycle)[0]

        assert cluster['signal_count'] == 2
        # One named department; the BUSINESS member contributes none.
        assert cluster['departments'] == [
            {'id': str(it_dept.id), 'name': it_dept.get_name_display()},
        ]

    def test_cluster_list_serializer_renders_constraint_cluster(
        self, account, activity, decision_cycle, user_a,
    ):
        _mk_constraint(account, activity, decision_cycle, user_a,
                       ConstraintNature.TECHNICAL)
        cluster = _list_constraint(account, decision_cycle)[0]

        data = SignalClusterListSerializer(cluster).data
        assert data['signal_type'] == 'constraint'
        assert data['canonical_key'] == 'TECHNICAL'

    def test_validated_and_pending_counts(
        self, account, activity, decision_cycle, user_a,
    ):
        _mk_constraint(account, activity, decision_cycle, user_a,
                       ConstraintNature.OPERATIONAL)  # MANUAL -> VALIDATED
        _mk_constraint(account, activity, decision_cycle, user_a,
                       ConstraintNature.OPERATIONAL,
                       source=SignalSource.LLM_EXTRACTED)  # -> PENDING

        cluster = _list_constraint(account, decision_cycle)[0]
        assert cluster['signal_count'] == 2
        assert cluster['confirmation_count'] == 1  # one VALIDATED
        assert cluster['has_pending_signals'] is True
        assert cluster['pending_count'] == 1


# =============================================================================
# DETAIL — members through the constraint list serializer
# =============================================================================

class TestConstraintClusterDetail:

    def test_detail_returns_members(
        self, account, activity, decision_cycle, user_a,
    ):
        _mk_constraint(account, activity, decision_cycle, user_a,
                       ConstraintNature.TECHNICAL, summary='Integrate with SAP')
        _mk_constraint(account, activity, decision_cycle, user_a,
                       ConstraintNature.TECHNICAL, summary='SSO required')

        detail = SignalClusterService.get_cluster_detail(
            account_id=account.id,
            canonical_key='TECHNICAL',
            signal_type='constraint',
            decision_cycle_id=decision_cycle.id,
        )
        data = SignalClusterDetailSerializer(detail).data

        assert len(data['members']) == 2
        # Members render through the constraint list serializer (nature exposed).
        assert all(m['nature'] == 'TECHNICAL' for m in data['members'])

    def test_detail_unknown_nature_raises(
        self, account, activity, decision_cycle, user_a,
    ):
        from core.exceptions import StandardizedValidationError
        _mk_constraint(account, activity, decision_cycle, user_a,
                       ConstraintNature.TECHNICAL)
        with pytest.raises(StandardizedValidationError):
            SignalClusterService.get_cluster_detail(
                account_id=account.id,
                canonical_key='FINANCIAL',  # no such member in this DC
                signal_type='constraint',
                decision_cycle_id=decision_cycle.id,
            )


# =============================================================================
# N+1 — query count constant as data grows
# =============================================================================

class TestConstraintClusterQueryCount:

    def _count(self, account, decision_cycle):
        with CaptureQueriesContext(connection) as ctx:
            _list_constraint(account, decision_cycle)
        return len(ctx)

    def test_query_count_is_constant_as_data_grows(
        self, account, activity, decision_cycle, user_a, contact, contact_extra,
    ):
        activity.contacts.add(contact)
        _mk_constraint(account, activity, decision_cycle, user_a,
                       ConstraintNature.TECHNICAL)
        _mk_constraint(account, activity, decision_cycle, user_a,
                       ConstraintNature.TECHNICAL)
        small = self._count(account, decision_cycle)

        activity.contacts.add(contact_extra)
        for nat in (ConstraintNature.FINANCIAL, ConstraintNature.SECURITY,
                    ConstraintNature.CONTRACTUAL, ConstraintNature.OPERATIONAL):
            _mk_constraint(account, activity, decision_cycle, user_a, nat)
        large = self._count(account, decision_cycle)

        assert small == large
        assert large <= 4


# =============================================================================
# REGRESSION — adding constraint did not disturb the other cluster types
# =============================================================================

class TestOtherTypesUnaffected:

    def test_mixed_list_returns_constraint_and_pain_without_raising(
        self, account, activity, decision_cycle, user_a,
    ):
        from app_modules.signals.models import PainSignal
        from app_modules.signals.constants import (
            SignalWhat, SignalDimension, ScopeLevel,
        )
        pain = PainSignal(
            account=account, source_activity=activity,
            decision_cycle=decision_cycle,
            what=SignalWhat.OPS, dimension=SignalDimension.TIME,
            scope_level=ScopeLevel.BUSINESS,
            summary='Slow reporting', source=SignalSource.MANUAL,
        )
        pain.save(user=user_a, client_id=account.client_id)

        _mk_constraint(account, activity, decision_cycle, user_a,
                       ConstraintNature.TECHNICAL)

        clusters = SignalClusterService.list_clusters_for_account(
            account_id=account.id,
            signal_type=['pain', 'constraint'],
            decision_cycle_id=decision_cycle.id,
        )
        types = {c['signal_type'] for c in clusters}
        assert 'pain' in types
        assert 'constraint' in types
