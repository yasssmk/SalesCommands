# backend/app_modules/decision_cycles/services/__init__.py
"""
Services for Decision Cycle module.

Service architecture:
- CompletenessScoreService: Gamification scoring for step field completion
- StepAggregationService: Aggregates Activity data into Step-level insights
- StalledDetectionService: Detects stalled steps with actionable diagnostics
- CycleAggregationService: Derives Cycle-level intelligence from Steps
"""
from .completeness_score import CompletenessScoreService
from .step_aggregation_service import StepAggregationService
from .step_status_derivation_service import StepStatusDerivationService
from .cycle_aggregation_service import CycleAggregationService
from .readiness_score_service import ReadinessScoreService
from .people_consolidation_service import PeopleConsolidationService

__all__ = [
    'CompletenessScoreService',
    'StepAggregationService',
    'StepStatusDerivationService',
    'CycleAggregationService',
    'ReadinessScoreService',
    'PeopleConsolidationService',
]