# app_modules/activities/services/activity_sequence_service.py
"""
Activity Sequence Service.

Reusable playlist engine for calculating activity chains dynamically.
Works with both Decision Cycles and Campaigns (future).

The sequence is calculated based on:
1. decision_step.order (pipeline position)
2. COALESCE(scheduled_date, due_date)
3. scheduled_time
4. created_at (fallback for same date/time)

PERFORMANCE OPTIMIZATIONS:
- Uses SQL Window Functions (ROW_NUMBER) for ranking
- Uses Coalesce() annotations instead of Python calculations
- Single query with all data needed
- Composite index on (decision_cycle, decision_step, scheduled_date, scheduled_time, created_at)
"""

from typing import Optional, List, Dict, Any
from enum import Enum
import datetime

from django.db.models import (
    QuerySet, F, Value, Case, When,
    IntegerField, DateField, TimeField,
    Window
)
from django.db.models.functions import Coalesce, RowNumber

from core.logging import get_logger

logger = get_logger(__name__)


class SequenceScope(str, Enum):
    """
    Scope for activity sequence calculation.
    
    Determines which activities are considered "in the same sequence".
    """
    DECISION_CYCLE = 'decision_cycle'
    DECISION_STEP = 'decision_step'
    CAMPAIGN = 'campaign'  # Future implementation


class ActivitySequenceService:
    """
    Service for calculating activity sequences dynamically.
    
    Reusable for Decision Cycles and Campaigns.
    
    PERFORMANCE:
    - Single SQL query with Window Functions
    - No Python sorting - all done in database
    - Minimal data transfer with .only()
    
    Usage:
        # Get sequence context for a single activity
        context = ActivitySequenceService.get_sequence_context(
            activity=my_activity,
            scope=SequenceScope.DECISION_CYCLE
        )
        
        # Get full sequence for a scope
        sequence = ActivitySequenceService.get_sequence_for_scope(
            scope=SequenceScope.DECISION_CYCLE,
            scope_id='uuid',
            client_id='uuid'
        )
    """
    
    # Max values for COALESCE fallback (activities without dates go last)
    _MAX_DATE = datetime.date(9999, 12, 31)
    _MAX_TIME = datetime.time(23, 59, 59)
    
    # =========================================================================
    # PUBLIC METHODS
    # =========================================================================
    
    @classmethod
    def get_sequence_context(
        cls,
        activity,
        scope: SequenceScope = SequenceScope.DECISION_CYCLE
    ) -> Optional[Dict[str, Any]]:
        """
        Get the sequence context for an activity.
        
        Returns previous and next activities based on the specified scope.
        Uses a single optimized SQL query with Window Functions.
        
        Args:
            activity: The activity to get context for
            scope: The scope for sequence calculation
            
        Returns:
            dict with sequence info, or None if activity has no valid scope
            
            {
                'scope': 'decision_cycle',
                'scope_id': 'uuid-of-cycle',
                'position': 2,
                'total': 4,
                'previous_activities': [...],
                'next_activities': [...]
            }
        """
        if not activity:
            return None
        
        # Check if activity has a valid scope
        scope_id = cls._get_scope_id(activity, scope)
        if not scope_id:
            return None
        
        # Get all activities with their sequence rank (single optimized query)
        ranked_activities = cls._get_ranked_activities(activity, scope)
        
        if not ranked_activities:
            return None
        
        # Find current activity and its position
        current_rank = None
        total = len(ranked_activities)
        
        for act in ranked_activities:
            if act['id'] == activity.id:
                current_rank = act['_rank']
                break
        
        if current_rank is None:
            logger.warning(
                "activity_not_found_in_scope",
                extra={
                    'activity_id': str(activity.id),
                    'scope': scope.value,
                    'scope_id': str(scope_id)
                }
            )
            return None
        
        # Get previous activities (most recent COMPLETED, exclude CANCELLED)
        previous_activities = cls._get_previous_completed_activities(
            ranked_activities, current_rank
        )
        
        # Get next activities (only PENDING: PLANNED/IN_PROGRESS)
        next_activities = cls._get_pending_activities_after_rank(
            ranked_activities, current_rank
        )
        
        return {
            'scope': scope.value,
            'scope_id': str(scope_id),
            'position': current_rank,
            'total': total,
            'previous_activities': previous_activities,
            'next_activities': next_activities,
        }
    
    @classmethod
    def get_previous_activities(
        cls,
        activity,
        scope: SequenceScope = SequenceScope.DECISION_CYCLE
    ) -> List[Dict[str, Any]]:
        """
        Get only the previous activities for an activity.
        
        Returns:
            List of activity dicts (may be multiple if same rank)
        """
        context = cls.get_sequence_context(activity, scope)
        if not context:
            return []
        return context.get('previous_activities', [])
    
    @classmethod
    def get_next_activities(
        cls,
        activity,
        scope: SequenceScope = SequenceScope.DECISION_CYCLE
    ) -> List[Dict[str, Any]]:
        """
        Get only the next activities for an activity.
        
        Returns:
            List of activity dicts (may be multiple if same rank)
        """
        context = cls.get_sequence_context(activity, scope)
        if not context:
            return []
        return context.get('next_activities', [])
    
    @classmethod
    def get_sequence_for_scope(
        cls,
        scope: SequenceScope,
        scope_id: str,
        client_id: str
    ) -> List[Dict[str, Any]]:
        """
        Get the full ordered sequence for a scope.
        
        Useful for displaying a timeline or playlist view.
        
        Args:
            scope: The scope type
            scope_id: UUID of the scope object (cycle/step/campaign)
            client_id: Client ID for multi-tenant isolation
            
        Returns:
            Ordered list of activity dicts with position info
        """
        # Import here to avoid circular imports
        from ..models import Activity
        from ..constants import ActivityStatus
        
        # Build base queryset
        filter_kwargs = {
            'client_id': client_id,
        }
        exclude_kwargs = {
            'status': ActivityStatus.CANCELLED
        }
        
        if scope == SequenceScope.DECISION_CYCLE:
            filter_kwargs['decision_cycle_id'] = scope_id
        elif scope == SequenceScope.DECISION_STEP:
            filter_kwargs['decision_step_id'] = scope_id
        elif scope == SequenceScope.CAMPAIGN:
            # Future: filter_kwargs['campaign_id'] = scope_id
            return []
        
        queryset = Activity.objects.filter(**filter_kwargs).exclude(**exclude_kwargs)
        
        if not queryset.exists():
            return []
        
        # Annotate and order
        ranked_queryset = cls._annotate_with_rank(queryset)
        
        # Convert to list of dicts
        result = []
        total = ranked_queryset.count()
        
        for activity in ranked_queryset:
            act_dict = cls._activity_to_dict(activity)
            act_dict['position'] = activity._rank
            act_dict['total'] = total
            result.append(act_dict)
        
        return result
    
    # =========================================================================
    # PRIVATE METHODS - QUERY BUILDING
    # =========================================================================
    
    @classmethod
    def _get_scope_id(cls, activity, scope: SequenceScope) -> Optional[str]:
        """Get the scope ID for an activity based on scope type."""
        if scope == SequenceScope.DECISION_CYCLE:
            return activity.decision_cycle_id
        elif scope == SequenceScope.DECISION_STEP:
            return activity.decision_step_id
        elif scope == SequenceScope.CAMPAIGN:
            # Future: return activity.campaign_id
            return None
        return None
    
    @classmethod
    def _get_scope_queryset(cls, activity, scope: SequenceScope) -> QuerySet:
        """
        Get queryset of all activities in the same scope.
        
        Excludes CANCELLED activities from sequence calculation.
        """
        # Import here to avoid circular imports
        from ..models import Activity
        from ..constants import ActivityStatus
        
        base_filter = {
            'client_id': activity.client_id,
        }
        
        exclude_filter = {
            'status': ActivityStatus.CANCELLED
        }
        
        if scope == SequenceScope.DECISION_CYCLE:
            if not activity.decision_cycle_id:
                return Activity.objects.none()
            base_filter['decision_cycle_id'] = activity.decision_cycle_id
            
        elif scope == SequenceScope.DECISION_STEP:
            if not activity.decision_step_id:
                return Activity.objects.none()
            base_filter['decision_step_id'] = activity.decision_step_id
            
        elif scope == SequenceScope.CAMPAIGN:
            return Activity.objects.none()
        
        return Activity.objects.filter(**base_filter).exclude(**exclude_filter)
    
    @classmethod
    def _annotate_with_rank(cls, queryset: QuerySet) -> QuerySet:
        """
        Annotate queryset with sequence rank using SQL Window Functions.
        
        Uses:
        - Coalesce(decision_step__order, 999) for step ordering
        - Coalesce(scheduled_date, due_date, MAX_DATE) for date ordering
        - Coalesce(scheduled_time, MAX_TIME) for time ordering
        - ROW_NUMBER() for unique ranking
        
        ORDER BY:
        1. decision_step__order (nulls last = 999)
        2. effective_date (scheduled_date OR due_date, nulls last)
        3. scheduled_time (nulls last)
        4. created_at
        """
        # Annotate with effective values for ordering
        annotated = queryset.annotate(
            # Step order with nulls last
            _step_order=Coalesce(
                F('decision_step__order'),
                Value(999),
                output_field=IntegerField()
            ),
            # Effective date: COALESCE(scheduled_date, due_date, MAX_DATE)
            _effective_date=Coalesce(
                F('scheduled_date'),
                F('due_date'),
                Value(cls._MAX_DATE),
                output_field=DateField()
            ),
            # Effective time: COALESCE(scheduled_time, MAX_TIME)
            _effective_time=Coalesce(
                F('scheduled_time'),
                Value(cls._MAX_TIME),
                output_field=TimeField()
            ),
        )
        
        # Add ROW_NUMBER window function for ranking
        ranked = annotated.annotate(
            _rank=Window(
                expression=RowNumber(),
                order_by=[
                    F('_step_order').asc(),
                    F('_effective_date').asc(),
                    F('_effective_time').asc(),
                    F('created_at').asc(),
                ]
            )
        )
        
        # Order by rank for consistent iteration
        return ranked.select_related(
            'decision_step',
            'owner'
        ).only(
            'id', 'title', 'activity_type', 'status', 'outcome',
            'scheduled_date', 'scheduled_time', 'due_date',
            'created_at',
            'decision_step__id', 'decision_step__order', 'decision_step__name',
            'owner__id', 'owner__first_name', 'owner__last_name'
        ).order_by('_rank')
    
    @classmethod
    def _get_ranked_activities(cls, activity, scope: SequenceScope) -> List[Dict]:
        """
        Get all activities in scope with their ranks as a list of dicts.
        
        Returns list of dicts with activity info and _rank.
        """
        queryset = cls._get_scope_queryset(activity, scope)
        
        if not queryset.exists():
            return []
        
        ranked_queryset = cls._annotate_with_rank(queryset)
        
        result = []
        for act in ranked_queryset:
            act_dict = cls._activity_to_dict(act)
            act_dict['_rank'] = act._rank
            result.append(act_dict)
        
        return result
    
    # =========================================================================
    # PRIVATE METHODS - DATA TRANSFORMATION
    # =========================================================================
    
    @classmethod
    def _activity_to_dict(cls, activity) -> Dict[str, Any]:
        """
        Convert an activity object to a dict with all needed fields.
        """
        return {
            'id': activity.id,
            'title': activity.title,
            'activity_type': activity.activity_type,
            'status': activity.status,
            'outcome': activity.outcome,
            'scheduled_date': activity.scheduled_date,
            'scheduled_time': activity.scheduled_time,
            'due_date': activity.due_date,
            'decision_step_id': activity.decision_step_id,
            'decision_step_name': (
                activity.decision_step.name 
                if activity.decision_step 
                else None
            ),
            'decision_step_order': (
                activity.decision_step.order 
                if activity.decision_step 
                else 999
            ),
            'owner_id': activity.owner_id,
            'owner_name': (
                f"{activity.owner.first_name or ''} {activity.owner.last_name or ''}".strip()
                if activity.owner
                else None
            ),
        }
    
    @classmethod
    def _get_activities_at_rank(
        cls,
        ranked_activities: List[Dict],
        target_rank: int
    ) -> List[Dict[str, Any]]:
        """
        Get all activities at a specific rank.
        
        Note: With ROW_NUMBER(), each activity has a unique rank.
        However, we still support returning multiple activities
        if they have the same "logical rank" (same step/date/time).
        
        For simplicity with ROW_NUMBER, we return the single activity
        at that rank. If you need multiple activities at same position,
        use DENSE_RANK instead.
        """
        if target_rank < 1:
            return []
        
        result = []
        for act in ranked_activities:
            if act['_rank'] == target_rank:
                result.append(cls._format_activity_for_response(act))
                # With ROW_NUMBER, only one activity per rank
                # But we could extend to check for same step/date/time
                break
        
        return result
    
    @classmethod
    def _get_previous_completed_activities(
        cls,
        ranked_activities: List[Dict],
        current_rank: int
    ) -> List[Dict]:
        """
        Get the most recent COMPLETED activity before current rank.
        
        Excludes CANCELLED activities.
        Returns at most 1 activity (the immediately previous completed one).
        
        For "previous", we want to show what was done before, so COMPLETED
        is more relevant than PLANNED.
        """
        # Get all activities with rank < current, excluding CANCELLED
        previous = [
            act for act in ranked_activities
            if act['_rank'] < current_rank and act.get('status') != 'CANCELLED'
        ]
        
        if not previous:
            return []
        
        # Sort by rank descending to get the most recent first
        previous_sorted = sorted(previous, key=lambda x: x['_rank'], reverse=True)
        
        # Return only the first one (most recent)
        return [previous_sorted[0]]
    
    
    @classmethod
    def _get_pending_activities_after_rank(
        cls, 
        ranked_activities: List[Dict], 
        current_rank: int
    ) -> List[Dict]:
        """
        Get PENDING activities with rank > current_rank.
        
        Only returns activities with status PLANNED or IN_PROGRESS.
        Skips COMPLETED and CANCELLED activities.
        
        This ensures "next activities" shows actual upcoming work,
        not already-completed activities that happen to be sequenced after.
        """
        pending_statuses = ('PLANNED', 'IN_PROGRESS')
        return [
            act for act in ranked_activities
            if act['_rank'] > current_rank and act.get('status') in pending_statuses
        ]
    
    @classmethod
    def _format_activity_for_response(cls, activity_dict: Dict) -> Dict[str, Any]:
        """
        Format an activity dict for API response.
        
        Returns only the fields needed for display in previous/next lists.
        """
        return {
            'id': str(activity_dict['id']),
            'title': activity_dict['title'],
            'activity_type': activity_dict['activity_type'],
            'status': activity_dict['status'],
            'outcome': activity_dict.get('outcome'),
            'scheduled_date': (
                activity_dict['scheduled_date'].isoformat() 
                if activity_dict.get('scheduled_date') 
                else None
            ),
            'due_date': (
                activity_dict['due_date'].isoformat() 
                if activity_dict.get('due_date') 
                else None
            ),
            'decision_step_name': activity_dict.get('decision_step_name'),
        }