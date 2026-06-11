# app_modules/decision_cycles/services/readiness_score_service.py
"""
Readiness Score Service for Decision Cycles.

Evaluates whether a DecisionCycle has accumulated enough validated
evidence for a useful Deal Health diagnostic. Returns a deterministic
score (0-100) based on binary presence of key signal types, stakeholder
roles, products, and activity momentum.

Stateless, read-only, no side effects. Pattern mirrors
CompletenessScoreService (DIMENSION_WEIGHTS constant + overridable
via __init__).

Usage:
    service = ReadinessScoreService()
    result = service.calculate(decision_cycle)
    # result = {'score': 70, 'dimensions': [{'name': ..., 'filled': ..., ...}, ...]}
"""

from app_modules.signals.constants import PeopleRole, SignalStatus


class ReadinessScoreService:
    """
    Deterministic readiness scorer for a DecisionCycle.

    Checks binary presence (at least one validated instance) for each
    dimension. TechStack is intentionally excluded — its presence is
    not a readiness indicator for Deal Health.
    """

    DIMENSION_WEIGHTS = {
        'pain': 20,
        'objective': 15,
        'impact': 15,
        'decision_maker': 15,
        'champion': 10,
        'risk': 10,
        'solution': 10,
        'momentum': 5,
    }

    # PeopleRole values used for the decision_maker and champion dimensions.
    # decision_maker matches DECISION_MAKER or ECONOMIC_BUYER — both carry
    # formal authority to approve the deal.
    _DECISION_MAKER_ROLES = frozenset({
        PeopleRole.DECISION_MAKER,   # 'DECISION_MAKER'
        PeopleRole.ECONOMIC_BUYER,   # 'ECONOMIC_BUYER'
    })
    _CHAMPION_ROLES = frozenset({
        PeopleRole.CHAMPION,         # 'CHAMPION'
    })

    def __init__(self, weights=None):
        self.weights = weights or self.DIMENSION_WEIGHTS.copy()

    def calculate(self, decision_cycle):
        """
        Calculate readiness score for a decision cycle.

        Args:
            decision_cycle: DecisionCycle instance.

        Returns:
            dict with 'score' (int 0-100) and 'dimensions' (list of dicts).
        """
        checks = self._evaluate_dimensions(decision_cycle)

        total_weight = sum(self.weights.get(d['name'], 0) for d in checks)
        earned_weight = sum(
            self.weights.get(d['name'], 0)
            for d in checks
            if d['filled']
        )

        score = round((earned_weight / total_weight) * 100) if total_weight > 0 else 0

        return {
            'score': score,
            'dimensions': checks,
        }

    def _evaluate_dimensions(self, dc):
        """Return a list of dimension dicts with filled status."""
        from app_modules.signals.models import (
            PainSignal,
            ObjectiveSignal,
            ImpactSignal,
            BlockerSignal,
            ConstraintSignal,
            PeopleSignal,
        )
        from app_modules.decision_cycles.models import DealProduct

        validated = SignalStatus.VALIDATED

        has_pain = PainSignal.objects.filter(
            decision_cycle=dc, status=validated,
        ).exists()

        has_objective = ObjectiveSignal.objects.filter(
            decision_cycle=dc, status=validated,
        ).exists()

        has_impact = ImpactSignal.objects.filter(
            decision_cycle=dc, status=validated,
        ).exists()

        has_decision_maker = PeopleSignal.objects.filter(
            decision_cycle=dc,
            status=validated,
            role__in=self._DECISION_MAKER_ROLES,
        ).exists()

        has_champion = PeopleSignal.objects.filter(
            decision_cycle=dc,
            status=validated,
            role__in=self._CHAMPION_ROLES,
        ).exists()

        has_risk = (
            BlockerSignal.objects.filter(
                decision_cycle=dc, status=validated,
            ).exists()
            or ConstraintSignal.objects.filter(
                decision_cycle=dc, status=validated,
            ).exists()
        )

        has_solution = DealProduct.objects.filter(
            decision_cycle=dc,
        ).exists()

        has_momentum = dc.activities.exists()

        return [
            {
                'name': 'pain',
                'filled': has_pain,
                'weight': self.weights.get('pain', 0),
                'detail': 'At least one validated pain signal',
            },
            {
                'name': 'objective',
                'filled': has_objective,
                'weight': self.weights.get('objective', 0),
                'detail': 'At least one validated objective signal',
            },
            {
                'name': 'impact',
                'filled': has_impact,
                'weight': self.weights.get('impact', 0),
                'detail': 'At least one validated impact signal',
            },
            {
                'name': 'decision_maker',
                'filled': has_decision_maker,
                'weight': self.weights.get('decision_maker', 0),
                'detail': 'Decision maker or economic buyer identified',
            },
            {
                'name': 'champion',
                'filled': has_champion,
                'weight': self.weights.get('champion', 0),
                'detail': 'Champion identified',
            },
            {
                'name': 'risk',
                'filled': has_risk,
                'weight': self.weights.get('risk', 0),
                'detail': 'At least one blocker or constraint captured',
            },
            {
                'name': 'solution',
                'filled': has_solution,
                'weight': self.weights.get('solution', 0),
                'detail': 'At least one product attached to the deal',
            },
            {
                'name': 'momentum',
                'filled': has_momentum,
                'weight': self.weights.get('momentum', 0),
                'detail': 'At least one activity linked to the cycle',
            },
        ]
