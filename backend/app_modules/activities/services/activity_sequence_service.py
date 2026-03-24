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
        
        # Get previous activities (context-dependent based on current status)
        previous_activities = cls._get_previous_activities(
            ranked_activities, current_rank, activity.status
        )
        
        # Get next activities (only PENDING: PLANNED/IN_PROGRESS)
        next_activities = cls._get_pending_activities_after_rank(
            ranked_activities, current_rank, activity.status
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
            filter_kwargs['campaign_id'] = scope_id
           
        
        queryset = Activity.objects.filter(**filter_kwargs).exclude(**exclude_kwargs)
        
        if not queryset.exists():
            return []
        
        # Annotate and order
        if scope == SequenceScope.CAMPAIGN:
            ranked_queryset = cls._annotate_with_rank_campaign(queryset)
        else:
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
            return activity.campaign_id
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
            if not activity.campaign_contact_id:
                return Activity.objects.none()
            base_filter['campaign_contact_id'] = activity.campaign_contact_id
        
        return Activity.objects.filter(**base_filter).exclude(**exclude_filter)
    
    @classmethod
    def _annotate_with_rank(cls, queryset: QuerySet) -> QuerySet:
        """
        Annotate queryset with sequence rank using SQL Window Functions.

        ORDER BY:
        1. decision_step__order (nulls last = 999)
        2. status_order: COMPLETED (0) → PLANNED (1) → other (2)
        3. overdue_order: overdue PLANNED (0) → future PLANNED (1)
        4. effective_date ASC (oldest first for overdue, closest first for future)
        5. effective_time ASC (nulls last)
        6. created_at ASC (tiebreaker)

        Result for OPEN activities:
        - Overdue PLANNED first, oldest date at top (most urgent)
        - Then future PLANNED, closest date at top (soonest)
        """
        from ..constants import ActivityStatus

        today = datetime.date.today()

        annotated = queryset.annotate(
            # Status grouping: COMPLETED first, then PLANNED
            _status_order=Case(
                When(status=ActivityStatus.COMPLETED, then=Value(0)),
                When(status=ActivityStatus.PLANNED, then=Value(1)),
                default=Value(2),
                output_field=IntegerField()
            ),
            # Step order: applies to COMPLETED only.
            # PLANNED activities ignore step order (urgency > pipeline position)
            _step_order=Case(
                When(
                    status=ActivityStatus.COMPLETED,
                    then=Coalesce(
                        F('decision_step__order'),
                        Value(999),
                        output_field=IntegerField()
                    ),
                ),
                default=Value(0),
                output_field=IntegerField()
            ),
            # Within PLANNED: overdue (0) before future (1)
            _overdue_order=Case(
                When(
                    status=ActivityStatus.PLANNED,
                    scheduled_date__lt=today,
                    then=Value(0),
                ),
                When(
                    status=ActivityStatus.PLANNED,
                    scheduled_date__isnull=True,
                    due_date__lt=today,
                    then=Value(0),
                ),
                default=Value(1),
                output_field=IntegerField()
            ),
            # Effective date: completed_at for COMPLETED, else scheduled/due
            _effective_date=Case(
                When(
                    status=ActivityStatus.COMPLETED,
                    completed_at__isnull=False,
                    then=F('completed_at__date'),
                ),
                default=Coalesce(
                    F('scheduled_date'),
                    F('due_date'),
                    Value(cls._MAX_DATE),
                    output_field=DateField()
                ),
                output_field=DateField()
            ),
            # Time ordering (nulls last)
            _effective_time=Coalesce(
                F('scheduled_time'),
                Value(cls._MAX_TIME),
                output_field=TimeField()
            ),
        )

        # ROW_NUMBER window function for unique ranking
        ranked = annotated.annotate(
            _rank=Window(
                expression=RowNumber(),
                order_by=[
                    F('_step_order').asc(),
                    F('_status_order').asc(),
                    F('_overdue_order').asc(),
                    F('_effective_date').asc(),
                    F('_effective_time').asc(),
                    F('created_at').asc(),
                ]
            )
        )

        return ranked.select_related(
            'decision_step',
            'owner'
        ).only(
            'id', 'title', 'activity_type', 'status', 'outcome',
            'scheduled_date', 'scheduled_time', 'due_date',
            'completed_at', 'created_at',
            'decision_step__id', 'decision_step__order', 'decision_step__name',
            'owner__id', 'owner__first_name', 'owner__last_name'
        ).order_by('_rank')
    
    @classmethod
    def _annotate_with_rank_campaign(cls, queryset: QuerySet) -> QuerySet:
        """
        Annotate campaign-scoped activities with sequence rank.

        ORDER BY: sequence_position ASC (campaign step order), created_at as tiebreaker.
        Simpler than decision cycle ranking — campaign sequences are explicitly ordered.
        """
        ranked = queryset.annotate(
            _rank=Window(
                expression=RowNumber(),
                order_by=[
                    F('sequence_position').asc(),
                    F('created_at').asc(),
                ]
            )
        )
        return ranked.select_related(
            'owner'
        ).only(
            'id', 'title', 'activity_type', 'status', 'outcome',
            'scheduled_date', 'scheduled_time', 'due_date',
            'completed_at', 'created_at', 'sequence_position',
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
        
        if scope == SequenceScope.CAMPAIGN:
            ranked_queryset = cls._annotate_with_rank_campaign(queryset)
        else:
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
        today = datetime.date.today()
        is_overdue = False
        if activity.status == 'PLANNED':
            if activity.scheduled_date and activity.scheduled_date < today:
                is_overdue = True
            elif activity.due_date and activity.due_date < today:
                is_overdue = True

        return {
            'id': activity.id,
            'title': activity.title,
            'activity_type': activity.activity_type,
            'status': activity.status,
            'is_overdue': is_overdue,
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
    def _get_previous_activities(
        cls,
        ranked_activities: List[Dict],
        current_rank: int,
        current_status: str = None
    ) -> List[Dict]:
        """
        Get the most relevant previous activity before current rank.
        
        Returns at most 1 activity.
        
        Behavior depends on current activity status:
        - COMPLETED: previous = most recent COMPLETED before current rank
          (shows what was done before this completed work)
        - PLANNED/IN_PROGRESS: previous = closest activity before by rank,
          any non-CANCELLED status (shows sequential context)
        """
        if current_status == 'COMPLETED':
            # For completed activities, only show completed predecessors
            previous = [
                act for act in ranked_activities
                if act['_rank'] < current_rank and act.get('status') == 'COMPLETED'
            ]
        else:
            # For non-completed activities, show closest predecessor regardless of status
            previous = [
                act for act in ranked_activities
                if act['_rank'] < current_rank and act.get('status') != 'CANCELLED'
            ]
        
        if not previous:
            return []
        
        # Sort by rank descending to get the closest one first
        previous_sorted = sorted(previous, key=lambda x: x['_rank'], reverse=True)
        
        # Return only the first one (closest), formatted for API response
        return [cls._format_activity_for_response(previous_sorted[0])]
    
    
    @classmethod
    def _get_pending_activities_after_rank(
        cls, 
        ranked_activities: List[Dict], 
        current_rank: int,
        current_status: str = None
    ) -> List[Dict]:
        """
        Get PENDING activities relative to current activity.
        
        Only returns activities with status PLANNED or IN_PROGRESS.
        Skips COMPLETED and CANCELLED activities.
        
        Behavior depends on current activity status:
        - COMPLETED: ALL pending activities in scope are "next"
        (remaining work regardless of chronological rank)
        - PLANNED/IN_PROGRESS: only pending with rank > current
        (respects sequence order for non-completed activities)
        """
        pending_statuses = ('PLANNED', 'IN_PROGRESS')
        
        if current_status == 'COMPLETED':
            # For completed activities, all remaining pending work is "next"
            # regardless of rank (scheduled_date may be before completed_at)
            return [
                cls._format_activity_for_response(act)
                for act in ranked_activities
                if act['_rank'] != current_rank and act.get('status') in pending_statuses
            ]
        
        # For non-completed activities, respect sequence order
        return [
            cls._format_activity_for_response(act)
            for act in ranked_activities
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
            'is_overdue': activity_dict.get('is_overdue', False),
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