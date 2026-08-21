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
from .derivation_sql import annotate_step_derived_status, annotate_cycle_state
from .deal_value_sql import (
    DEAL_VALUE_ALIAS,
    DEAL_VALUE_SUM,
    annotate_deal_value,
    deal_value_for,
)
from .close_date_sql import (
    CLOSE_DATE_ALIAS,
    annotate_effective_close_date,
    effective_close_date_expr,
    effective_close_date_for,
)

__all__ = [
    'CompletenessScoreService',
    'StepAggregationService',
    'StepStatusDerivationService',
    'CycleAggregationService',
    'ReadinessScoreService',
    'PeopleConsolidationService',
    'annotate_step_derived_status',
    'annotate_cycle_state',
    'DEAL_VALUE_ALIAS',
    'DEAL_VALUE_SUM',
    'annotate_deal_value',
    'deal_value_for',
    'CLOSE_DATE_ALIAS',
    'annotate_effective_close_date',
    'effective_close_date_expr',
    'effective_close_date_for',
]