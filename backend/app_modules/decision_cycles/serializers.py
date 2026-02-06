# app_modules/decision_cycles/serializers.py
"""
Serializers for Decision Cycle module.

Follows the same patterns as CompanyAccountSerializer for consistency.
"""

from rest_framework import serializers
from django.utils.translation import gettext_lazy as _
from core.client_scope import ClientScopeManager
from core.error_messages import CoreErrorMessages
from core.exceptions import StandardizedValidationError
from app_modules.core_modules.models import StandardDepartment
from .models import DecisionCycle, DecisionStep, DecisionStepContact, DecisionStepDepartment
from .constants import PipelineStep, DecisionStepStatus, PIPELINE_STEPS_CONFIG


# ============================================================================
# HELPER SERIALIZERS
# ============================================================================

class ActivityTimelineSerializer(serializers.Serializer):
    """
    Minimal serializer for activity cards in pipeline timeline.
    
    Optimized for display in step columns - no deep nesting.
    Used by DecisionStepListSerializer.
    """
    id = serializers.UUIDField(read_only=True)
    title = serializers.CharField(read_only=True)
    activity_type = serializers.CharField(read_only=True)
    activity_type_display = serializers.SerializerMethodField(read_only=True)
    status = serializers.CharField(read_only=True)
    status_display = serializers.SerializerMethodField(read_only=True)
    outcome = serializers.CharField(read_only=True, allow_null=True)
    outcome_display = serializers.SerializerMethodField(read_only=True)
    scheduled_date = serializers.DateField(read_only=True, allow_null=True)
    scheduled_time = serializers.TimeField(read_only=True, allow_null=True)
    completed_at = serializers.DateTimeField(read_only=True, allow_null=True)
    contacts_count = serializers.SerializerMethodField(read_only=True)
    
    # Contact info for display
    primary_contact = serializers.SerializerMethodField(read_only=True)
    
    def get_activity_type_display(self, obj):
        return obj.get_activity_type_display() if hasattr(obj, 'get_activity_type_display') else obj.activity_type
    
    def get_status_display(self, obj):
        return obj.get_status_display() if hasattr(obj, 'get_status_display') else obj.status
    
    def get_outcome_display(self, obj):
        if not obj.outcome:
            return None
        return obj.get_outcome_display() if hasattr(obj, 'get_outcome_display') else obj.outcome
    
    def get_contacts_count(self, obj):
        if hasattr(obj, '_prefetched_contacts_count'):
            return obj._prefetched_contacts_count
        return obj.contacts.count() if hasattr(obj, 'contacts') else 0
    
    def get_primary_contact(self, obj):
        """Return first contact info for card display."""
        if hasattr(obj, '_prefetched_contacts') and obj._prefetched_contacts:
            contact = obj._prefetched_contacts[0]
        elif hasattr(obj, 'contacts'):
            contact = obj.contacts.first()
        else:
            return None
        
        if not contact:
            return None
        
        return {
            'id': str(contact.id),
            'name': f"{contact.first_name or ''} {contact.last_name or ''}".strip(),
            'job_title': contact.job_title
        }


class DecisionStepContactSerializer(serializers.ModelSerializer):
    """Serializer for junction table between DecisionStep and Contact."""
    
    contact_name = serializers.SerializerMethodField(read_only=True)
    contact_email = serializers.SerializerMethodField(read_only=True)
    contact_job_title = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = DecisionStepContact
        fields = ['id', 'contact', 'contact_name', 'contact_email', 'contact_job_title', 'created_at']
        read_only_fields = ['id', 'created_at']
    
    def get_contact_name(self, obj):
        if obj.contact:
            return f"{obj.contact.first_name or ''} {obj.contact.last_name or ''}".strip()
        return None
    
    def get_contact_email(self, obj):
        return obj.contact.email if obj.contact else None
    
    def get_contact_job_title(self, obj):
        return obj.contact.job_title if obj.contact else None

class DecisionStepDepartmentSerializer(serializers.ModelSerializer):
    """Serializer for junction table between DecisionStep and Department."""
    
    department_name = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = DecisionStepDepartment
        fields = ['id', 'department', 'department_name', 'created_at']
        read_only_fields = ['id', 'created_at']
    
    def get_department_name(self, obj):
        if obj.department:
            return obj.department.get_name_display()
        return None
    
class StepMinimalSerializer(serializers.ModelSerializer):
    """Minimal serializer for step references (previous/next)."""
    
    class Meta:
        model = DecisionStep
        fields = ['id', 'name', 'stage', 'status']
        read_only_fields = fields

# ============================================================================
# TIMELINE SERIALIZERS (Performance optimized for by_account endpoint)
# ============================================================================

class DecisionStepTimelineSerializer(serializers.ModelSerializer):
    """
    Ultra-lightweight serializer for timeline display in by_account endpoint.
    
    PERFORMANCE OPTIMIZED:
    - No model property access (is_stalled, completeness_score, has_parallel_steps)
    - Uses annotated counts instead of queryset methods
    - Uses prefetched activities only
    - No SerializerMethodField with DB queries
    
    Required annotations on queryset:
    - activities_count: Count('activities')
    
    Required prefetch:
    - activities (with Prefetch, limited, with contacts + contacts__standard_department)
    - step_contacts (with Prefetch, to_attr='_prefetched_step_contacts')
    - step_departments (with Prefetch, to_attr='_prefetched_step_departments')
    """
    
    stage_display = serializers.SerializerMethodField(read_only=True)
    status_display = serializers.SerializerMethodField(read_only=True)
    
    # Annotated count (set by ViewSet queryset with Count())
    activities_count = serializers.IntegerField(read_only=True, default=0)
    
    # Activities from prefetch cache
    activities = serializers.SerializerMethodField(read_only=True)

    # Aggregation from prefetched data (zero DB queries)
    all_contacts_count = serializers.SerializerMethodField(read_only=True)
    all_departments_list = serializers.SerializerMethodField(read_only=True)
    effective_start_date = serializers.SerializerMethodField(read_only=True)
    effective_end_date = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = DecisionStep
        fields = [
            # Identity & Order
            'id', 'name', 'order',
            
            # Pipeline Step
            'stage', 'stage_display',
            
            # Status
            'status', 'status_display',
            
            # Timeline
            'expected_end',
            
            # Summary (no DB queries - uses annotation)
            'stakeholder',
            'activities_count',

            # Aggregation (no DB queries - uses prefetch)
            'all_contacts_count',
            'all_departments_list',
            'effective_start_date',
            'effective_end_date',
            
            # Activities for cards (from prefetch)
            'activities',
        ]
        read_only_fields = fields
    
    def get_stage_display(self, obj):
        """Return stage label without DB query."""
        return obj.get_stage_display() if obj.stage else None

    def get_status_display(self, obj):
        """Return status label without DB query."""
        return obj.get_status_display() if obj.status else None

    def get_activities(self, obj):
        """
        Return activities from prefetch cache ONLY.

        Does NOT make any DB query - relies entirely on prefetched data.
        If not prefetched, returns empty list.

        Limited to 5 activities per step for timeline card performance.
        """
        MAX_ACTIVITIES = 5

        # Check prefetch cache first
        if hasattr(obj, '_prefetched_objects_cache') and 'activities' in obj._prefetched_objects_cache:
            activities = list(obj._prefetched_objects_cache['activities'])[:MAX_ACTIVITIES]
            return ActivityTimelineSerializer(activities, many=True).data

        # No prefetch = empty list (avoid N+1)
        return []

    # ==========================================================================
    # AGGREGATION GETTERS (reads from bulk context injected by view)
    # ==========================================================================
    # The view pre-computes bulk aggregation via StepAggregationService and
    # injects results into serializer context as 'step_aggregations'.
    # Fallback: if context not available, compute from prefetched data directly.
    # ==========================================================================

    def _get_step_aggregation(self, obj):
        """
        Get pre-computed aggregation for this step from serializer context.
        Falls back to on-the-fly computation from prefetched data if context
        is not available (e.g. when used outside by_account view).
        """
        # Try context-based bulk result first
        step_aggregations = self.context.get('step_aggregations')
        if step_aggregations and obj.id in step_aggregations:
            return step_aggregations[obj.id]

        # Fallback: compute from prefetched data using service
        from .services import StepAggregationService
        service = StepAggregationService()
        bulk = service.get_bulk_aggregation([obj])
        return bulk.get(obj.id, {})

    def get_all_contacts_count(self, obj):
        """Count of deduplicated contacts. Reads from bulk context."""
        agg = self._get_step_aggregation(obj)
        return agg.get('all_contacts_count', 0)

    def get_all_departments_list(self, obj):
        """Merged departments list. Reads from bulk context."""
        agg = self._get_step_aggregation(obj)
        return agg.get('all_departments_list', [])

    def get_effective_start_date(self, obj):
        """Real observed start date. Reads from bulk context."""
        agg = self._get_step_aggregation(obj)
        return agg.get('effective_start_date')

    def get_effective_end_date(self, obj):
        """Projected end date. Reads from bulk context."""
        agg = self._get_step_aggregation(obj)
        return agg.get('effective_end_date')


class DecisionCycleTimelineSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for cycle list in by_account endpoint.
    
    PERFORMANCE OPTIMIZED:
    - Uses DecisionStepTimelineSerializer for steps
    - Uses annotated counts (prefixed with _annotated_ to avoid property conflict)
    - Cycle-level insights from CycleAggregationService via serializer context
    - No computed properties with DB queries
    
    Required annotations on queryset:
    - _annotated_steps_count: Count('steps')
    - _annotated_validated_steps_count: Count('steps', filter=Q(steps__status='VALIDATED'))
    
    Required context (injected by view):
    - cycle_summaries: dict from CycleAggregationService.get_bulk_summaries()
    - step_aggregations: dict from StepAggregationService.get_bulk_aggregation()
    
    Required prefetch:
    - steps (ordered, with activities prefetch)
    """
    
    account_name = serializers.SerializerMethodField(read_only=True)
    
    # Use timeline-optimized step serializer
    steps = DecisionStepTimelineSerializer(many=True, read_only=True)
    
    # Annotated counts - use source to map from annotation names
    steps_count = serializers.IntegerField(source='_annotated_steps_count', read_only=True, default=0)
    validated_steps_count = serializers.IntegerField(source='_annotated_validated_steps_count', read_only=True, default=0)
    
    # Cycle-level insights (from CycleAggregationService via context)
    cycle_status = serializers.SerializerMethodField(read_only=True)
    progress = serializers.SerializerMethodField(read_only=True)
    stalled_steps_count = serializers.SerializerMethodField(read_only=True)
    is_at_risk = serializers.SerializerMethodField(read_only=True)
    has_steps_needing_attention = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = DecisionCycle
        fields = [
            'id', 'name', 'description',
            'account', 'account_name',
            'is_active',
            'steps', 'steps_count', 'validated_steps_count',
            # Cycle-level insights
            'cycle_status', 'progress',
            'stalled_steps_count', 'is_at_risk',
            'has_steps_needing_attention',
            'created_at', 'updated_at'
        ]
        read_only_fields = fields
    
    def get_account_name(self, obj):
        """Return account name from select_related (no extra query)."""
        return obj.account.company_name if obj.account else None

    # ==========================================================================
    # CYCLE-LEVEL INSIGHT GETTERS (reads from bulk context injected by view)
    # ==========================================================================

    def _get_cycle_summary(self, obj):
        """
        Get pre-computed cycle summary from serializer context.
        Falls back to on-the-fly computation if context not available.
        """
        cycle_summaries = self.context.get('cycle_summaries')
        if cycle_summaries and obj.id in cycle_summaries:
            return cycle_summaries[obj.id]

        # Fallback: compute directly (triggers DB queries)
        from .services import CycleAggregationService
        service = CycleAggregationService()
        return {
            'cycle_status': service.get_cycle_status(obj),
            'progress': service.get_progress(obj),
            'stalled_steps_count': len(service.get_stalled_steps(obj)),
            'is_at_risk': service.get_cycle_status(obj) in (
                CycleAggregationService.STATUS_AT_RISK,
                CycleAggregationService.STATUS_STALLED,
            ),
            'has_steps_needing_attention': any(
                service._stalled_detection.needs_next_step_attention(s)
                for s in obj.steps.all()
            ),
        }

    def get_cycle_status(self, obj):
        """Derived cycle status. Reads from bulk context."""
        return self._get_cycle_summary(obj).get('cycle_status', 'NOT_STARTED')

    def get_progress(self, obj):
        """Progress metrics. Reads from bulk context."""
        return self._get_cycle_summary(obj).get('progress', {
            'total_steps': 0,
            'validated_steps': 0,
            'current_step_name': None,
            'percentage': 0,
        })

    def get_stalled_steps_count(self, obj):
        """Count of stalled steps. Reads from bulk context."""
        return self._get_cycle_summary(obj).get('stalled_steps_count', 0)

    def get_is_at_risk(self, obj):
        """Whether cycle is at risk. Reads from bulk context."""
        return self._get_cycle_summary(obj).get('is_at_risk', False)

    def get_has_steps_needing_attention(self, obj):
        """Whether any step needs next step resolution. Reads from bulk context."""
        return self._get_cycle_summary(obj).get('has_steps_needing_attention', False)

# ============================================================================
# DECISION STEP SERIALIZERS
# ============================================================================

class DecisionStepListSerializer(ClientScopeManager.SerializerMixin, serializers.ModelSerializer):
    """
    Lightweight serializer for step lists (pipeline display).
    
    Steps are fixed pipeline stages - users cannot create/delete them.
    Activities are the execution unit within each step.
    
    Includes nested activities for timeline card display.
    """
    
    stage_display = serializers.SerializerMethodField(read_only=True)
    status_display = serializers.SerializerMethodField(read_only=True)
    departments_list = serializers.SerializerMethodField(read_only=True)
    previous_step_info = serializers.SerializerMethodField(read_only=True)
    next_step_info = serializers.SerializerMethodField(read_only=True)
    is_current = serializers.BooleanField(read_only=True)
    has_parallel_steps = serializers.BooleanField(read_only=True)
    contacts_count = serializers.SerializerMethodField(read_only=True)
    completeness_score = serializers.SerializerMethodField(read_only=True)
    
    # Stalled detection
    is_stalled = serializers.BooleanField(read_only=True)
    stalled_reason = serializers.CharField(read_only=True)
    
    # Next step attention
    needs_next_step_attention = serializers.BooleanField(read_only=True)
    
    # Pipeline step properties
    is_activity_optional = serializers.BooleanField(read_only=True)
    step_description = serializers.CharField(read_only=True)
    order = serializers.IntegerField(read_only=True)
    activities_count = serializers.SerializerMethodField(read_only=True)
    
    # Activities for timeline cards
    activities = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = DecisionStep
        fields = [
            # Identity & Order
            'id', 'name', 'order',
            
            # Pipeline Step
            'stage', 'stage_display',
            'is_activity_optional', 'step_description',
            
            # Status
            'status', 'status_display',
            
            # Deal Temporality
            'start_date', 'expected_end', 'completed_at',
            
            # Linked list (legacy, may remove later)
            'previous_step', 'previous_step_info',
            'next_step_info',
            
            # Flags
            'is_current', 'has_parallel_steps',
            
            # Stalled Detection
            'is_stalled', 'stalled_reason',

            # Next Step Attention
            'needs_next_step_attention',
            
            # Summary fields
            'stakeholder', 'departments_list',
            'contacts_count', 'activities_count', 'completeness_score',
            
            # Activities for timeline
            'activities',
            
            # Timestamps
            'created_at', 'updated_at'
        ]
        read_only_fields = fields
    
    def get_stage_display(self, obj):
        return obj.get_stage_display() if obj.stage else None
    
    def get_status_display(self, obj):
        return obj.get_status_display() if obj.status else None
    
    def get_departments_list(self, obj):
        """Return list of department names."""
        return [
            {
                'id': str(sd.department.id),
                'name': sd.department.get_name_display()
            }
            for sd in obj.step_departments.select_related('department').all()
        ]
    
    def get_previous_step_info(self, obj):
        if obj.previous_step:
            return {
                'id': str(obj.previous_step.id),
                'name': obj.previous_step.name
            }
        return None
    
    def get_next_step_info(self, obj):
        next_step = obj.next_step
        if next_step:
            return {
                'id': str(next_step.id),
                'name': next_step.name
            }
        return None
    
    def get_contacts_count(self, obj):
        return obj.step_contacts.count()
    
    def get_completeness_score(self, obj):
        """Calculate completeness score for the step."""
        from .services import CompletenessScoreService
        service = CompletenessScoreService()
        return service.calculate(obj)
    
    def get_activities_count(self, obj):
        """Return count of activities linked to this step."""
        return obj.activities.count() if hasattr(obj, 'activities') else 0
    
    def get_activities(self, obj):
        """
        Return activities for timeline card display.
        
        Ordered by scheduled_date (soonest first), limited to avoid overload.
        Uses prefetched data when available to avoid N+1.
        """
        MAX_ACTIVITIES_PER_STEP = 10  # Limit for performance
        
        # Use prefetched data if available
        if hasattr(obj, '_prefetched_objects_cache') and 'activities' in obj._prefetched_objects_cache:
            activities = list(obj._prefetched_objects_cache['activities'])[:MAX_ACTIVITIES_PER_STEP]
        elif hasattr(obj, 'activities'):
            activities = obj.activities.select_related('owner').prefetch_related('contacts').order_by(
                'scheduled_date', 'scheduled_time', '-created_at'
            )[:MAX_ACTIVITIES_PER_STEP]
        else:
            return []
        
        return ActivityTimelineSerializer(activities, many=True).data



class DecisionStepSerializer(ClientScopeManager.SerializerMixin, serializers.ModelSerializer):
    """
    Complete serializer for step detail view.
    
    Note: step_type, scheduled_date, scheduled_time have been removed.
    Type and scheduling now belong exclusively to Activity.
    DecisionStep is a buyer milestone - it observes execution.
    """
    
    stage_display = serializers.SerializerMethodField(read_only=True)
    status_display = serializers.SerializerMethodField(read_only=True)
    departments_list = serializers.SerializerMethodField(read_only=True)
    previous_step_info = serializers.SerializerMethodField(read_only=True)
    next_step_info = serializers.SerializerMethodField(read_only=True)
    is_current = serializers.BooleanField(read_only=True)
    has_parallel_steps = serializers.BooleanField(read_only=True)
    step_contacts = DecisionStepContactSerializer(many=True, read_only=True)
    step_departments = DecisionStepDepartmentSerializer(many=True, read_only=True)
    completeness_score = serializers.SerializerMethodField(read_only=True)
    completeness_details = serializers.SerializerMethodField(read_only=True)
    
    # Stalled detection
    is_stalled = serializers.BooleanField(read_only=True)
    stalled_reason = serializers.CharField(read_only=True)
    stalled_details = serializers.SerializerMethodField(read_only=True)

     # Next step attention
    needs_next_step_attention = serializers.BooleanField(read_only=True)
    
    # Pipeline step properties
    is_activity_optional = serializers.BooleanField(read_only=True)
    step_description = serializers.CharField(read_only=True)
    order = serializers.IntegerField(read_only=True)
    activities_count = serializers.SerializerMethodField(read_only=True)

    # Aggregation from Activities (detail view only — uses @property)
    aggregated_contacts = serializers.SerializerMethodField(read_only=True)
    aggregated_departments = serializers.SerializerMethodField(read_only=True)
    effective_start_date = serializers.SerializerMethodField(read_only=True)
    effective_end_date = serializers.SerializerMethodField(read_only=True)
    all_contacts = serializers.SerializerMethodField(read_only=True)
    all_departments = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = DecisionStep
        fields = [
            # Identity
            'id', 'name', 'cycle', 'order',
            
            # Stage & Status
            'stage', 'stage_display',
            'status', 'status_display', 'is_activity_optional', 'step_description',
            
            # Deal Temporality
            'start_date', 'expected_end', 'completed_at',
            
            # Linked list
            'previous_step', 'previous_step_info',
            'next_step_info',
            
            # Flags
            'is_current', 'has_parallel_steps',
            
            # Stalled Detection
            'is_stalled', 'stalled_reason', 'stalled_details',

            # Next Step Attention
            'needs_next_step_attention',
            
            # Details
            'stakeholder',
            'description', 'goal',
            'influence_score',
            'criterias', 'metrics', 'activities_count',

            # Manager
            'manager_notes',

            # Completeness Score
            'completeness_score',
            'completeness_details',
            
            # Departments & Contacts (manual)
            'departments_list',
            'step_departments',
            'step_contacts',

            # Aggregation from Activities
            'aggregated_contacts',
            'aggregated_departments',
            'effective_start_date',
            'effective_end_date',
            'all_contacts',
            'all_departments',
            
            # Audit
            'created_by', 'updated_by',
            'created_at', 'updated_at'
        ]

        read_only_fields = [
            'id', 'stage_display', 'status_display',
            'departments_list', 'previous_step_info', 'next_step_info', 
            'is_current', 'has_parallel_steps', 
            'is_stalled', 'stalled_reason', 'stalled_details', 'needs_next_step_attention',
            'step_contacts', 'step_departments',
            'completeness_score', 'completeness_details',
            'aggregated_contacts', 'aggregated_departments',
            'effective_start_date', 'effective_end_date',
            'all_contacts', 'all_departments',
            'created_by', 'updated_by', 'created_at', 'updated_at'
        ]
    
    def get_stage_display(self, obj):
        return obj.get_stage_display() if obj.stage else None
    
    def get_status_display(self, obj):
        return obj.get_status_display() if obj.status else None
    
    def get_departments_list(self, obj):
        """Return list of department names for quick display."""
        return [
            {
                'id': str(sd.department.id),
                'name': sd.department.get_name_display()
            }
            for sd in obj.step_departments.select_related('department').all()
        ]
    
    def get_previous_step_info(self, obj):
        if obj.previous_step:
            return {
                'id': str(obj.previous_step.id),
                'name': obj.previous_step.name
            }
        return None
    
    def get_next_step_info(self, obj):
        next_step = obj.next_step
        if next_step:
            return {
                'id': str(next_step.id),
                'name': next_step.name
            }
        return None
    
    def get_completeness_score(self, obj):
        """Calculate completeness score for the step."""
        from .services import CompletenessScoreService
        service = CompletenessScoreService()
        return service.calculate(obj)

    def get_completeness_details(self, obj):
        """Get detailed completeness breakdown."""
        from .services import CompletenessScoreService
        service = CompletenessScoreService()
        return service.get_details(obj)
    
    def get_stalled_details(self, obj):
        """Get detailed stalled information for UI display. Delegates to service."""
        from .services import StalledDetectionService
        return StalledDetectionService().get_stalled_details(obj)
    
    def get_activities_count(self, obj):
        """Return count of activities linked to this step."""
        return obj.activities.count() if hasattr(obj, 'activities') else 0
    
    # ==========================================================================
    # AGGREGATION GETTERS (detail view — delegates to StepAggregationService)
    # ==========================================================================

    def get_aggregated_contacts(self, obj):
        """Contacts derived from linked activities only. Delegates to service."""
        from .services import StepAggregationService
        return StepAggregationService().get_aggregated_contacts(obj)

    def get_aggregated_departments(self, obj):
        """Departments derived from activity contacts. Delegates to service."""
        from .services import StepAggregationService
        return StepAggregationService().get_aggregated_departments(obj)

    def get_effective_start_date(self, obj):
        """Real observed start date from first activity. Delegates to service."""
        from .services import StepAggregationService
        return StepAggregationService().get_effective_start_date(obj)

    def get_effective_end_date(self, obj):
        """Projected end date from last planned activity. Delegates to service."""
        from .services import StepAggregationService
        return StepAggregationService().get_effective_end_date(obj)

    def get_all_contacts(self, obj):
        """Merged contacts: manual + activity, with source tagging. Delegates to service."""
        from .services import StepAggregationService
        return StepAggregationService().get_all_contacts(obj)

    def get_all_departments(self, obj):
        """Merged departments: manual + activity. Delegates to service."""
        from .services import StepAggregationService
        return StepAggregationService().get_all_departments(obj)

class DecisionStepCreateSerializer(ClientScopeManager.SerializerMixin, serializers.ModelSerializer):
    """
    Serializer for step creation.
    
    Note: step_type, scheduled_date, scheduled_time have been removed.
    Type and scheduling belong to Activity. Create activities separately.
    
    expected_end is MANDATORY for deal timeline visibility.
    """
    
    cycle_id = serializers.UUIDField(write_only=True)
    previous_step_id = serializers.UUIDField(required=False, allow_null=True, write_only=True)
    contact_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        write_only=True
    )
    department_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        write_only=True
    )
    
    class Meta:
            model = DecisionStep
            fields = [
                'cycle_id',
                'name', 'stage', 'status',
                'expected_end',
                'previous_step_id',
                'stakeholder',
                'description', 'goal',
                'influence_score', 'criterias', 'metrics',
                'contact_ids',
                'department_ids',
            ]
            extra_kwargs = {
                'expected_end': {
                    'required': False,
                    'allow_null': True,
                }
            }
    
    def validate_name(self, value):
        if not value or not value.strip():
            raise StandardizedValidationError(
                CoreErrorMessages.REQUIRED_FIELD.format(field='Name')
            )
        return value.strip()
    
    def validate_stage(self, value):
        valid_stages = [choice[0] for choice in PipelineStep.choices]
        if value not in valid_stages:
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_FIELD.format(field='Pipeline Step')
            )
        return value
    
    def validate_status(self, value):
        if not value:
            return DecisionStepStatus.NOT_STARTED
        
        valid_statuses = [choice[0] for choice in DecisionStepStatus.choices]
        if value not in valid_statuses:
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_FIELD.format(field='Status')
            )
        return value
    
    def validate(self, attrs):
        """Global validation for decision step creation."""
        # Inject client_id from context
        client_id = self._get_client_id_from_context()
        attrs['client_id'] = client_id
        
        # Validate cycle exists and belongs to same client
        cycle_id = attrs.get('cycle_id')
        if cycle_id:
            try:
                cycle = DecisionCycle.objects.get(id=cycle_id)
                if str(cycle.client_id) != str(client_id):
                    raise StandardizedValidationError(
                        CoreErrorMessages.CLIENT_MISMATCH
                    )
                attrs['cycle'] = cycle
            except DecisionCycle.DoesNotExist:
                raise StandardizedValidationError(
                    CoreErrorMessages.OBJECT_NOT_FOUND
                )
        
        # Validate previous_step exists and belongs to same cycle
        previous_step_id = attrs.pop('previous_step_id', None)
        if previous_step_id:
            try:
                previous_step = DecisionStep.objects.get(id=previous_step_id)
                if previous_step.cycle_id != cycle_id:
                    raise StandardizedValidationError(
                        CoreErrorMessages.INVALID_FIELD.format(
                            field='Previous step must belong to the same cycle'
                        )
                    )
                attrs['previous_step'] = previous_step
            except DecisionStep.DoesNotExist:
                raise StandardizedValidationError(
                    CoreErrorMessages.OBJECT_NOT_FOUND
                )
        
        return attrs
    
    def create(self, validated_data):
        """Create decision step with proper audit fields."""
        # Get user from context (standard pattern)
        user = self.context.get('request').user if self.context.get('request') else None
        
        # Extract M2M fields
        contact_ids = validated_data.pop('contact_ids', [])
        department_ids = validated_data.pop('department_ids', [])
        validated_data.pop('cycle_id', None)  # Already converted to 'cycle' in validate()
        
        # Create instance without saving
        instance = DecisionStep(**validated_data)
        
        # Save with user to set created_by and updated_by
        instance.save(user=user)
        
        # Add contacts M2M via junction table
        if contact_ids:
            from app_modules.contacts.models import Contact
            contacts = Contact.objects.filter(id__in=contact_ids)
            for contact in contacts:
                DecisionStepContact.objects.create(
                    step=instance,
                    contact=contact,
                    client_id=instance.client_id
                )
        
        # Add departments M2M via junction table
        if department_ids:
            departments = StandardDepartment.objects.filter(id__in=department_ids)
            for department in departments:
                DecisionStepDepartment.objects.create(
                    step=instance,
                    department=department,
                    client_id=instance.client_id
                )
        
        # Note: Activity creation is now handled separately via ActivityModal
        # DecisionStep is a milestone, not an action. Activities are created independently.
        
        return instance



class DecisionStepUpdateSerializer(ClientScopeManager.SerializerMixin, serializers.ModelSerializer):
    """
    Serializer for step updates.
    
    Note: step_type, scheduled_date, scheduled_time have been removed.
    Type and scheduling belong to Activity.
    """
    
    previous_step_id = serializers.UUIDField(required=False, allow_null=True, write_only=True)
    contact_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        write_only=True
    )
    department_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        write_only=True
    )
    
    class Meta:
        model = DecisionStep
        fields = [
            'name', 'status',
            'expected_end',
            'stakeholder',
            'description', 'goal',
            'influence_score', 'criterias', 'metrics',
            'contact_ids', 'manager_notes',
            'department_ids'
        ]
    
    def validate(self, attrs):
        # Validate previous_step if provided
        previous_step_id = attrs.pop('previous_step_id', None)
        if previous_step_id is not None:
            if previous_step_id:
                try:
                    previous_step = DecisionStep.objects.get(id=previous_step_id)
                    if previous_step.cycle_id != self.instance.cycle_id:
                        raise StandardizedValidationError(
                            CoreErrorMessages.INVALID_FIELD.format(
                                field='Previous step must belong to the same cycle'
                            )
                        )
                    attrs['previous_step'] = previous_step
                except DecisionStep.DoesNotExist:
                    raise StandardizedValidationError(
                        CoreErrorMessages.OBJECT_NOT_FOUND
                    )
            else:
                attrs['previous_step'] = None
        
        return attrs
    
    def update(self, instance, validated_data):
        """Update decision step with proper audit fields and auto-set completed_at."""
        from django.utils import timezone
        
        user = self.context.get('request').user if self.context.get('request') else None
        
        # Extract M2M fields
        contact_ids = validated_data.pop('contact_ids', None)
        department_ids = validated_data.pop('department_ids', None)
        
        # Check for status change to auto-set completed_at
        new_status = validated_data.get('status')
        if new_status and new_status != instance.status:
            if new_status in [DecisionStepStatus.VALIDATED, DecisionStepStatus.REJECTED]:
                # Auto-set completed_at if not already set
                if not instance.completed_at:
                    validated_data['completed_at'] = timezone.now()
            elif instance.status in [DecisionStepStatus.VALIDATED, DecisionStepStatus.REJECTED]:
                # If reverting from VALIDATED/REJECTED, clear completed_at
                validated_data['completed_at'] = None
        
        # Check for status change to auto-set start_date
        if new_status and new_status != instance.status:
            if new_status == DecisionStepStatus.IN_PROGRESS and not instance.start_date:
                validated_data['start_date'] = timezone.now()
        
        # Update fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        instance.save(user=user)
        
        # Update contacts M2M if provided
        if contact_ids is not None:
            # Clear existing and add new
            instance.step_contacts.all().delete()
            if contact_ids:
                from app_modules.contacts.models import Contact
                contacts = Contact.objects.filter(id__in=contact_ids)
                for contact in contacts:
                    DecisionStepContact.objects.create(
                        step=instance,
                        contact=contact,
                        client_id=instance.client_id
                    )
        
        # Update departments M2M if provided
        if department_ids is not None:
            # Clear existing and add new
            instance.step_departments.all().delete()
            if department_ids:
                departments = StandardDepartment.objects.filter(id__in=department_ids)
                for department in departments:
                    DecisionStepDepartment.objects.create(
                        step=instance,
                        department=department,
                        client_id=instance.client_id
                    )
        
        return instance


# ============================================================================
# DECISION CYCLE SERIALIZERS
# ============================================================================

class DecisionCycleListSerializer(ClientScopeManager.SerializerMixin, serializers.ModelSerializer):
    """
    Lightweight serializer for cycle lists.
    """
    
    account_name = serializers.SerializerMethodField(read_only=True)
    steps_count = serializers.IntegerField(read_only=True)
    validated_steps_count = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = DecisionCycle
        fields = [
            'id', 'name', 'description',
            'account', 'account_name',
            'is_active',
            'steps_count', 'validated_steps_count',
            'created_at', 'updated_at'
        ]
        read_only_fields = fields
    
    def get_account_name(self, obj):
        return obj.account.company_name if obj.account else None


class DecisionCycleSerializer(ClientScopeManager.SerializerMixin, serializers.ModelSerializer):
    """
    Complete serializer for cycle detail view.
    """
    
    account_name = serializers.SerializerMethodField(read_only=True)
    steps = DecisionStepListSerializer(many=True, read_only=True)
    steps_count = serializers.IntegerField(read_only=True)
    validated_steps_count = serializers.IntegerField(read_only=True)
    estimated_timeline_days = serializers.IntegerField(read_only=True)
    has_steps_needing_attention = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = DecisionCycle
        fields = [
            'id', 'name', 'description',
            'account', 'account_name',
            'is_active',
            'steps', 'steps_count', 'validated_steps_count',
            'estimated_timeline_days',
            'has_steps_needing_attention',
            'created_by', 'updated_by',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'account_name', 'steps', 'steps_count',
            'validated_steps_count', 'estimated_timeline_days',
            'has_steps_needing_attention',
            'created_by', 'updated_by', 'created_at', 'updated_at'
        ]
    
    def get_account_name(self, obj):
        return obj.account.company_name if obj.account else None
    
    def get_has_steps_needing_attention(self, obj):
        """
        Check if any step in this cycle needs next step resolution.
        
        Uses model property on prefetched steps.
        Same performance profile as is_stalled (already called per step).
        """
        for step in obj.steps.all():
            if step.needs_next_step_attention:
                return True
        return False


class DecisionCycleCreateSerializer(ClientScopeManager.SerializerMixin, serializers.ModelSerializer):
    """
    Serializer for cycle creation.
    """
    
    account_id = serializers.UUIDField(write_only=True)
    
    class Meta:
        model = DecisionCycle
        fields = ['account_id', 'name', 'description', 'is_active']
        extra_kwargs = {
            'name': {
                'required': True,
                'error_messages': {
                    'required': CoreErrorMessages.REQUIRED_FIELD.format(field='Name'),
                }
            }
        }
    
    def validate_name(self, value):
        if not value or not value.strip():
            raise StandardizedValidationError(
                CoreErrorMessages.REQUIRED_FIELD.format(field='Name')
            )
        return value.strip()
    
    def validate(self, attrs):
        """Global validation for decision cycle creation."""
        try:
            # Inject client_id from context
            client_id = self._get_client_id_from_context()
            attrs['client_id'] = client_id
            
            # Validate account belongs to same client
            account = attrs.get('account')
            if account and str(account.client_id) != str(client_id):
                raise StandardizedValidationError(
                    CoreErrorMessages.CLIENT_MISMATCH
                )
            
            return attrs
            
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_DATA.format(detail=str(e))
            )
    
    def create(self, validated_data):
        """Create decision cycle with proper audit fields."""
        # Get user from context (standard pattern)
        user = self.context.get('request').user if self.context.get('request') else None
        
        # Create instance without saving
        instance = DecisionCycle(**validated_data)
        
        # Save with user to set created_by and updated_by
        instance.save(user=user)
        
        return instance


class DecisionCycleUpdateSerializer(ClientScopeManager.SerializerMixin, serializers.ModelSerializer):
    """
    Serializer for cycle updates.
    """
    
    class Meta:
        model = DecisionCycle
        fields = ['name', 'description', 'is_active']
    
    def update(self, instance, validated_data):
        """Update decision cycle with proper audit fields."""
        user = self.context.get('request').user if self.context.get('request') else None
        
        # Update fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        instance.save(user=user)
        return instance