# app_modules/decision_cycles/serializers.py
"""
Serializers for Decision Cycle module.

Follows the same patterns as CompanyAccountSerializer for consistency.
"""

from decimal import Decimal

from rest_framework import serializers
from django.utils.translation import gettext_lazy as _
from core.client_scope import ClientScopeManager
from core.currency import TenantCurrencySerializerMixin
from core.error_messages import CoreErrorMessages
from core.exceptions import StandardizedValidationError
from app_modules.core_modules.models import StandardDepartment
from .models import DecisionCycle, DecisionStep, DecisionStepContact, DecisionStepDepartment, DealHealthSnapshot, DealProduct, ManagerNote
from .constants import PipelineStep, DecisionStepStatus, PIPELINE_STEPS_CONFIG
from .services.derivation_sql import (
    CYCLE_STATUS_ALIAS,
    CURRENT_STEP_NAME_ALIAS,
    CURRENT_STEP_STAGE_ALIAS,
)


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
    due_date = serializers.DateField(read_only=True, allow_null=True)
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
        # Step status is DERIVED on read (no stored column) — never a field here.
        fields = ['id', 'name', 'stage']
        read_only_fields = fields

# ============================================================================
# TIMELINE SERIALIZERS (Performance optimized for by_account endpoint)
# ============================================================================

class DecisionStepTimelineSerializer(serializers.ModelSerializer):
    """
    Ultra-lightweight serializer for timeline display in by_account endpoint.
    
    PERFORMANCE OPTIMIZED:
    - No model property access — all computed fields from services via context
    - Uses annotated counts instead of queryset methods
    - Uses prefetched activities only
    - No SerializerMethodField with DB queries
    
    Required annotations on queryset:
    - activities_count: Count('activities')
    
    Required prefetch:
    - activities (with Prefetch, limited, with contacts + contacts__standard_department)
    - step_contacts (with Prefetch, to_attr='_prefetched_step_contacts')
    - step_departments (with Prefetch, to_attr='_prefetched_step_departments')
    
    Required context (injected by view):
    - step_derived_statuses: dict from StepStatusDerivationService.derive_bulk()
    - step_aggregations: dict from StepAggregationService.get_bulk_aggregation()
    """
    
    stage_display = serializers.SerializerMethodField(read_only=True)
    
    # Derived status (from StepStatusDerivationService via context)
    derived_status = serializers.SerializerMethodField(read_only=True)
    derived_status_display = serializers.SerializerMethodField(read_only=True)
    derived_status_color = serializers.SerializerMethodField(read_only=True)
    
    # Annotated count (set by ViewSet queryset with Count())
    activities_count = serializers.IntegerField(read_only=True, default=0)
    
    # Activities from prefetch cache
    activities = serializers.SerializerMethodField(read_only=True)

    # Aggregation from prefetched data (zero DB queries)
    all_contacts_count = serializers.SerializerMethodField(read_only=True)
    all_departments_list = serializers.SerializerMethodField(read_only=True)
    effective_start_date = serializers.SerializerMethodField(read_only=True)
    effective_end_date = serializers.SerializerMethodField(read_only=True)
    
    # Pipeline step properties (needed by frontend for column rendering)
    is_activity_optional = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = DecisionStep
        fields = [
            # Identity & Order
            'id', 'name', 'order',
            
            # Pipeline Step
            'stage', 'stage_display',
            'is_activity_optional',
            
            # Derived Status (replaces manual status)
            'derived_status', 'derived_status_display', 'derived_status_color',
            
            # Timeline (model fields)
            'start_date', 'expected_end', 'completed_at',

            # Step metadata (model fields)
            'description', 'goal', 'criterias', 'metrics',
            
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

    # ==========================================================================
    # DERIVED STATUS GETTERS (reads from bulk context injected by view)
    # ==========================================================================

    def _get_derived_status(self, obj):
        """
        Get pre-computed derived status from serializer context.
        Falls back to on-the-fly computation if context not available.
        """
        step_derived_statuses = self.context.get('step_derived_statuses')
        if step_derived_statuses and obj.id in step_derived_statuses:
            return step_derived_statuses[obj.id]

        # Fallback: compute directly (triggers DB queries)
        from .services import StepStatusDerivationService
        return StepStatusDerivationService().derive(obj)

    def get_derived_status(self, obj):
        """Derived step status. Reads from bulk context."""
        return self._get_derived_status(obj).get('status', 'NOT_STARTED')

    def get_derived_status_display(self, obj):
        """Derived step status display label. Reads from bulk context."""
        return self._get_derived_status(obj).get('status_display', 'Not Started')

    def get_derived_status_color(self, obj):
        """MUI color token for derived status. Reads from bulk context."""
        return self._get_derived_status(obj).get('color', 'secondary.light')

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


class DecisionCycleTimelineSerializer(TenantCurrencySerializerMixin,
                                      serializers.ModelSerializer):
    """
    Lightweight serializer for cycle list in by_account endpoint.
    
    PERFORMANCE OPTIMIZED:
    - Uses DecisionStepTimelineSerializer for steps
    - Uses annotated counts (prefixed with _annotated_ to avoid property conflict)
    - Cycle-level insights from CycleAggregationService via serializer context
    - No computed properties with DB queries
    
    Required annotations on queryset:
    - _annotated_steps_count: Count('steps')
    (validated_steps_count is DERIVED from step activities via the bulk context,
    not a stored-column annotation)

    Required context (injected by view):
    - cycle_summaries: dict from CycleAggregationService.get_bulk_summaries()
    - step_aggregations: dict from StepAggregationService.get_bulk_aggregation()
    
    Required prefetch:
    - steps (ordered, with activities prefetch)
    """
    
    account_name = serializers.SerializerMethodField(read_only=True)
    owner_name = serializers.SerializerMethodField(read_only=True)
    
    # Use timeline-optimized step serializer
    steps = DecisionStepTimelineSerializer(many=True, read_only=True)
    
    # steps_count = correct total (annotation). validated_steps_count comes from
    # the DERIVED progress (bulk context) — the stored-column annotation was
    # permanently stale (~0) and contradicted progress.validated_steps.
    steps_count = serializers.IntegerField(source='_annotated_steps_count', read_only=True, default=0)
    validated_steps_count = serializers.SerializerMethodField(read_only=True)
    
    # Cycle-level insights (from CycleAggregationService via context)
    cycle_status = serializers.SerializerMethodField(read_only=True)
    progress = serializers.SerializerMethodField(read_only=True)
    stalled_steps_count = serializers.SerializerMethodField(read_only=True)
    is_at_risk = serializers.SerializerMethodField(read_only=True)
    closed_by_name = serializers.SerializerMethodField(read_only=True)

    # The cycle's amount: the DERIVED product roll-up, discount included. Same
    # field, same formula as the DC list's Amount column — declared once in
    # services/deal_value_sql.py and read here off the ``_deal_value``
    # annotation the by_account queryset carries, so it costs no query per row.
    # This is the number the workspace header and the Products tab display;
    # ``estimated_value`` below stays in the payload as the legacy manual field
    # (TD-75: no runtime path populates it) and nothing reads it any more.
    total_deal_value = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True,
    )
    # The unit of that amount — the tenant's single currency, resolved at read
    # time (core.currency), memoised per serialization pass so a page of cycles
    # costs ONE resolution, not one per row.
    currency = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = DecisionCycle
        fields = [
            'id', 'name', 'description',
            'account', 'account_name',
            'owner', 'owner_name',
            'is_active',
            # Cycle outcome (two-layer architecture)
            'outcome', 'outcome_date', 'outcome_notes', 'hold_until',
            'readiness_score',
            'total_deal_value', 'currency',
            'estimated_value', 'estimated_timeline_days',
            'closed_by_name',
            'steps', 'steps_count', 'validated_steps_count',
            # Cycle-level insights
            'cycle_status', 'progress',
            'stalled_steps_count', 'is_at_risk',
            'created_at', 'updated_at'
        ]
        read_only_fields = fields
    
    def get_account_name(self, obj):
        """Return account name from select_related (no extra query)."""
        return obj.account.company_name if obj.account else None
    
    def get_closed_by_name(self, obj):
        """Return name of user who closed the cycle."""
        if obj.outcome is None:
            return None
        if obj.updated_by:
            name = f"{obj.updated_by.first_name or ''} {obj.updated_by.last_name or ''}".strip()
            return name or obj.updated_by.email
        return None
    
    def get_owner_name(self, obj):
        """Return owner full name from select_related (no extra query)."""
        if obj.owner:
            return f"{obj.owner.first_name or ''} {obj.owner.last_name or ''}".strip()
        return None

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
        cycle_status = service.get_cycle_status(obj)
        return {
            'cycle_status': service.get_cycle_status(obj),
            'progress': service.get_progress(obj),
            'stalled_steps_count': len(service.get_stalled_steps(obj)),
            'is_at_risk': cycle_status == CycleAggregationService.STATUS_STALLED,
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
            'current_step_order': None,
            'percentage': 0,
        })

    def get_validated_steps_count(self, obj):
        """DERIVED validated-step count (same source as progress.validated_steps)
        — reads the bulk context, no extra query."""
        return self._get_cycle_summary(obj).get('progress', {}).get('validated_steps', 0)

    def get_stalled_steps_count(self, obj):
        """Count of stalled steps. Reads from bulk context."""
        return self._get_cycle_summary(obj).get('stalled_steps_count', 0)

    def get_is_at_risk(self, obj):
        """Whether cycle is at risk. Reads from bulk context."""
        return self._get_cycle_summary(obj).get('is_at_risk', False)
    

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
    departments_list = serializers.SerializerMethodField(read_only=True)
    previous_step_info = serializers.SerializerMethodField(read_only=True)
    next_step_info = serializers.SerializerMethodField(read_only=True)
    is_current = serializers.BooleanField(read_only=True)
    has_parallel_steps = serializers.BooleanField(read_only=True)
    contacts_count = serializers.SerializerMethodField(read_only=True)
    completeness_score = serializers.SerializerMethodField(read_only=True)
    
    # Derived status (from StepStatusDerivationService)
    derived_status = serializers.SerializerMethodField(read_only=True)
    derived_status_display = serializers.SerializerMethodField(read_only=True)
    derived_status_color = serializers.SerializerMethodField(read_only=True)
    
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
            
            # Derived Status (replaces manual status)
            'derived_status', 'derived_status_display', 'derived_status_color',
            
            # Deal Temporality
            'start_date', 'expected_end', 'completed_at',
            
            # Linked list (legacy, may remove later)
            'previous_step', 'previous_step_info',
            'next_step_info',
            
            # Flags
            'is_current', 'has_parallel_steps',
            
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

    # ==========================================================================
    # DERIVED STATUS (single-instance — DB queries acceptable for list)
    # ==========================================================================

    def _get_derived_status(self, obj):
        """Compute derived status. Triggers DB queries."""
        if not hasattr(self, '_derived_status_cache'):
            self._derived_status_cache = {}
        if obj.id not in self._derived_status_cache:
            from .services import StepStatusDerivationService
            self._derived_status_cache[obj.id] = StepStatusDerivationService().derive(obj)
        return self._derived_status_cache[obj.id]

    def get_derived_status(self, obj):
        return self._get_derived_status(obj).get('status', 'NOT_STARTED')

    def get_derived_status_display(self, obj):
        return self._get_derived_status(obj).get('status_display', 'Not Started')

    def get_derived_status_color(self, obj):
        return self._get_derived_status(obj).get('color', 'secondary.light')
    
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
    
    Status is DERIVED automatically from activity data via StepStatusDerivationService.
    No manual status field exposed — frontend reads derived_status instead.
    """
    
    stage_display = serializers.SerializerMethodField(read_only=True)
    departments_list = serializers.SerializerMethodField(read_only=True)
    previous_step_info = serializers.SerializerMethodField(read_only=True)
    next_step_info = serializers.SerializerMethodField(read_only=True)
    is_current = serializers.BooleanField(read_only=True)
    has_parallel_steps = serializers.BooleanField(read_only=True)
    step_contacts = DecisionStepContactSerializer(many=True, read_only=True)
    step_departments = DecisionStepDepartmentSerializer(many=True, read_only=True)
    completeness_score = serializers.SerializerMethodField(read_only=True)
    completeness_details = serializers.SerializerMethodField(read_only=True)
    
    # Derived status (from StepStatusDerivationService)
    derived_status = serializers.SerializerMethodField(read_only=True)
    derived_status_display = serializers.SerializerMethodField(read_only=True)
    derived_status_color = serializers.SerializerMethodField(read_only=True)
    
    # Pipeline step properties
    is_activity_optional = serializers.BooleanField(read_only=True)
    step_description = serializers.CharField(read_only=True)
    order = serializers.IntegerField(read_only=True)
    activities_count = serializers.SerializerMethodField(read_only=True)

    # Cycle name (avoids extra fetch on frontend)
    cycle_name = serializers.SerializerMethodField(read_only=True)

    # Completed activities count (for header progression)
    completed_activities_count = serializers.SerializerMethodField(read_only=True)

    # Distinct users involved in activities (owners + other participants)
    activity_owners = serializers.SerializerMethodField(read_only=True)

    # Aggregation from Activities (detail view only — uses service)
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
            'is_activity_optional', 'step_description',
            
            # Derived Status (replaces manual status)
            'derived_status', 'derived_status_display', 'derived_status_color',
            
            # Deal Temporality
            'start_date', 'expected_end', 'completed_at',
            
            # Linked list
            'previous_step', 'previous_step_info',
            'next_step_info',
            
            # Flags
            'is_current', 'has_parallel_steps',
            
            # Details
            'stakeholder',
            'description', 'goal',
            'influence_score',
            'criterias', 'metrics', 'activities_count',
            'cycle_name', 'completed_activities_count',
            'activity_owners',

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
            'id', 'stage_display',
            'derived_status', 'derived_status_display', 'derived_status_color',
            'departments_list', 'previous_step_info', 'next_step_info',
            'is_current', 'has_parallel_steps',
            'step_contacts', 'step_departments',
            'completeness_score', 'completeness_details',
            'aggregated_contacts', 'aggregated_departments',
            'effective_start_date', 'effective_end_date',
            'all_contacts', 'all_departments', 'cycle_name', 'completed_activities_count','activity_owners',
            'created_by', 'updated_by', 'created_at', 'updated_at'
        ]
    
    def get_stage_display(self, obj):
        return obj.get_stage_display() if obj.stage else None

    # ==========================================================================
    # DERIVED STATUS (single-instance — DB queries acceptable for detail)
    # ==========================================================================

    def _get_derived_status(self, obj):
        """Compute derived status. Triggers DB queries."""
        if not hasattr(self, '_derived_status_cache'):
            self._derived_status_cache = {}
        if obj.id not in self._derived_status_cache:
            from .services import StepStatusDerivationService
            self._derived_status_cache[obj.id] = StepStatusDerivationService().derive(obj)
        return self._derived_status_cache[obj.id]

    def get_derived_status(self, obj):
        return self._get_derived_status(obj).get('status', 'NOT_STARTED')

    def get_derived_status_display(self, obj):
        return self._get_derived_status(obj).get('status_display', 'Not Started')

    def get_derived_status_color(self, obj):
        return self._get_derived_status(obj).get('color', 'secondary.light')
    
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
    
    def get_activities_count(self, obj):
        """Return count of active activities (excludes CANCELLED)."""
        if hasattr(obj, 'activities'):
            return obj.activities.exclude(status='CANCELLED').count()
        return 0
    
    def get_cycle_name(self, obj):
        """Return cycle name without extra query (uses select_related)."""
        if hasattr(obj, 'cycle') and obj.cycle:
            return obj.cycle.name
        return None

    def get_completed_activities_count(self, obj):
        """Return count of completed activities for this step."""
        if hasattr(obj, 'activities'):
            return obj.activities.filter(status='COMPLETED').count()
        return 0
    
    def get_activity_owners(self, obj):
        """
        Return distinct users involved in this step's activities.
        Includes activity owners — lightweight payload for avatar display.
        """
        if not hasattr(obj, 'activities'):
            return []

        from django.contrib.auth import get_user_model
        User = get_user_model()

        # Get distinct owner IDs from non-cancelled activities
        owner_ids = (
            obj.activities
            .exclude(status='CANCELLED')
            .values_list('owner_id', flat=True)
            .distinct()
        )

        if not owner_ids:
            return []

        users = User.objects.filter(id__in=owner_ids).only(
            'id', 'first_name', 'last_name', 'email'
        )

        return [
            {
                'id': str(u.id),
                'first_name': u.first_name or '',
                'last_name': u.last_name or '',
                'full_name': f"{u.first_name or ''} {u.last_name or ''}".strip() or u.email,
                'email': u.email
            }
            for u in users
        ]
    
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
    
    Status is DERIVED automatically — new steps start as NOT_STARTED (model default).
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
                'name', 'stage',
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
        
        return instance



class DecisionStepUpdateSerializer(ClientScopeManager.SerializerMixin, serializers.ModelSerializer):
    """
    Serializer for step updates.
    
    Note: step_type, scheduled_date, scheduled_time have been removed.
    Type and scheduling belong to Activity.
    
    Status is DERIVED automatically — not editable by user.
    """
    
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
            'name',
            'expected_end',
            'stakeholder',
            'description', 'goal',
            'influence_score', 'criterias', 'metrics',
            'contact_ids',
            'department_ids'
        ]
    
    def validate(self, attrs):
        
        return attrs
    
    def update(self, instance, validated_data):
        """Update decision step with proper audit fields."""
        user = self.context.get('request').user if self.context.get('request') else None
        
        # Extract M2M fields
        contact_ids = validated_data.pop('contact_ids', None)
        department_ids = validated_data.pop('department_ids', None)
        
        # Status is derived automatically from activities — no manual update.
        # completed_at and start_date are observed from activity data.
        
        # Update fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        instance.save(user=user)
        
        # Update contacts M2M if provided
        if contact_ids is not None:
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

class DecisionCycleListSerializer(TenantCurrencySerializerMixin,
                                  ClientScopeManager.SerializerMixin,
                                  serializers.ModelSerializer):
    """
    Lightweight serializer for cycle lists.
    """
    account_name = serializers.SerializerMethodField(read_only=True)
    # Alias of `name`, mirroring the DecisionStep serializers' `cycle_name`
    # convention so consumers can read the cycle's name under one stable key.
    cycle_name = serializers.CharField(source='name', read_only=True)
    owner_name = serializers.SerializerMethodField(read_only=True)
    # Email fallback for the owner's IDENTITY: first/last_name are nullable on
    # User, so a name-less owner would otherwise be anonymous. The manager DC
    # block shows owner_name || owner_email so "who carries this deal" is never
    # hidden behind a dash.
    owner_email = serializers.SerializerMethodField(read_only=True)
    # The owner's team (the manager DC block's Team line). null when the owner
    # has no team. Resolved from the owner__team select_related — no per-row query.
    team = serializers.SerializerMethodField(read_only=True)
    # Counts served by the 1b cycle-state annotations (annotate_cycle_state on
    # the list queryset) instead of the model properties — kills the TD-90 N+1
    # (steps.count() + a derive_bulk PER cycle). The properties stay on the model
    # for other consumers; this list serializer no longer touches them.
    steps_count = serializers.IntegerField(source='_total_steps_count', read_only=True)
    validated_steps_count = serializers.IntegerField(
        source='_validated_steps_count', read_only=True
    )
    # Effective status + current step, from the 1a/1b annotations, so the
    # frontend list can drop the per-row dc_cycle_state KPI call. Names mirror
    # the KPI meta keys (cycle_status / current_stage / current_step_name).
    cycle_status = serializers.CharField(
        source=CYCLE_STATUS_ALIAS, read_only=True, allow_null=True
    )
    current_stage = serializers.CharField(
        source=CURRENT_STEP_STAGE_ALIAS, read_only=True, allow_null=True
    )
    current_step_name = serializers.CharField(
        source=CURRENT_STEP_NAME_ALIAS, read_only=True, allow_null=True
    )
    # The Amount column: the DERIVED product roll-up. Reads the _deal_value
    # annotation the list queryset carries (annotate_deal_value), so it costs no
    # extra query per row. estimated_value stays in the payload as the legacy
    # manual field — no runtime path populates it, so nothing displays it.
    total_deal_value = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True,
    )
    # The unit of that amount — the tenant's single currency, resolved at read
    # time (core.currency). One per tenant, no conversion.
    currency = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = DecisionCycle
        fields = [
            'id', 'name', 'cycle_name', 'description',
            'account', 'account_name',
            'owner', 'owner_name', 'owner_email', 'team',
            'is_active',
            'total_deal_value', 'currency',
            'estimated_value',
            # Cycle outcome (two-layer architecture)
            'outcome', 'outcome_date', 'outcome_notes', 'hold_until',
            # Effective status + current step (derived, from annotations)
            'cycle_status', 'current_stage', 'current_step_name',
            'steps_count', 'validated_steps_count',
            'created_at', 'updated_at'
        ]
        read_only_fields = fields

    def get_account_name(self, obj):
        return obj.account.company_name if obj.account else None

    def get_owner_name(self, obj):
        if obj.owner:
            return f"{obj.owner.first_name or ''} {obj.owner.last_name or ''}".strip()
        return None

    def get_owner_email(self, obj):
        return obj.owner.email if obj.owner else None

    def get_team(self, obj):
        team = getattr(obj.owner, 'team', None) if obj.owner else None
        return {'id': str(team.id), 'name': team.name} if team else None


class DecisionCycleSerializer(TenantCurrencySerializerMixin,
                              ClientScopeManager.SerializerMixin,
                              serializers.ModelSerializer):
    """
    Complete serializer for cycle detail view.

    Cycle-level attention flags (has_steps_needing_attention) are now
    provided by CycleAggregationService via timeline context, not here.
    """

    account_name = serializers.SerializerMethodField(read_only=True)
    owner_name = serializers.SerializerMethodField(read_only=True)
    steps = DecisionStepListSerializer(many=True, read_only=True)
    steps_count = serializers.IntegerField(read_only=True)
    validated_steps_count = serializers.IntegerField(read_only=True)
    estimated_timeline_days = serializers.IntegerField(read_only=True)
    source_campaign_detail = serializers.SerializerMethodField(read_only=True)
    # The cycle's amount — the SAME derived roll-up the list and the workspace
    # payload serve (services/deal_value_sql.py). Read off the ``_deal_value``
    # annotation the retrieve queryset carries; the property falls back to one
    # query if an unannotated caller ever serializes a lone instance.
    # estimated_value is deliberately NOT added here: it has never been in this
    # payload, and nothing populates it (TD-75).
    total_deal_value = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True,
    )
    # The unit of that amount — the tenant's single currency (core.currency).
    currency = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = DecisionCycle
        fields = [
            'id', 'name', 'description',
            'account', 'account_name',
            'owner', 'owner_name',
            'is_active',
            # Cycle outcome (two-layer architecture)
            'outcome', 'outcome_date', 'outcome_notes', 'hold_until',
            'total_deal_value', 'currency',
            'steps', 'steps_count', 'validated_steps_count',
            'estimated_timeline_days', 'source_campaign_detail',
            'created_by', 'updated_by',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'account_name', 'owner', 'owner_name', 'steps', 'steps_count',
            'validated_steps_count', 'estimated_timeline_days',
            'total_deal_value', 'currency',
            'outcome', 'outcome_date', 'outcome_notes', 'hold_until',
            'created_by', 'updated_by', 'created_at', 'updated_at'
        ]
    
    def get_account_name(self, obj):
        return obj.account.company_name if obj.account else None
    
    def get_owner_name(self, obj):
        if obj.owner:
            return f"{obj.owner.first_name or ''} {obj.owner.last_name or ''}".strip()
        return None
    
    def get_source_campaign_detail(self, obj):
        """Return minimal info about the campaign that generated this cycle."""
        if not obj.source_campaign_id:
            return None
        campaign = obj.source_campaign
        if not campaign:
            return None
        return {
            'id': str(campaign.id),
            'name': campaign.name,
            'status': campaign.status,
        }


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

            # A DecisionCycle is always owned by its creator; the API entry
            # point must carry an authenticated user so owner is resolvable.
            request = self.context.get('request')
            user = getattr(request, 'user', None) if request else None
            if not user or not getattr(user, 'is_authenticated', False):
                raise StandardizedValidationError(
                    CoreErrorMessages.REQUIRED_FIELD.format(field='Owner (creator)')
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
        # Get user from context (standard pattern). validate() guarantees an
        # authenticated user, so owner is always the creator here.
        user = self.context.get('request').user if self.context.get('request') else None

        # owner = the creator, always.
        validated_data['owner'] = user

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


# ============================================================================
# DEAL HEALTH SNAPSHOT SERIALIZERS (read-only)
# ============================================================================

class DealHealthSnapshotListSerializer(ClientScopeManager.SerializerMixin, serializers.ModelSerializer):
    """
    Lightweight read-only serializer for DealHealthSnapshot list views.
    """

    class Meta:
        model = DealHealthSnapshot
        fields = [
            'id',
            'decision_cycle',
            'diagnostic',
            'snapshot_date',
            'pipeline_run',
            'created_at',
        ]
        read_only_fields = fields


class DealHealthSnapshotDetailSerializer(ClientScopeManager.SerializerMixin, serializers.ModelSerializer):
    """
    Full read-only serializer for DealHealthSnapshot retrieve views.
    """

    pipeline_run_summary = serializers.SerializerMethodField()

    class Meta:
        model = DealHealthSnapshot
        fields = [
            'id',
            'decision_cycle',
            'diagnostic',
            'snapshot_date',
            'pipeline_run',
            'pipeline_run_summary',
            'created_by',
            'updated_by',
            'created_at',
            'updated_at',
        ]
        read_only_fields = fields

    def get_pipeline_run_summary(self, obj):
        run = obj.pipeline_run
        if not run:
            return None
        return {
            'id': str(run.id),
            'pipeline_type': getattr(run, 'pipeline_type', None),
            'status': getattr(run, 'status', None),
            'created_at': run.created_at.isoformat() if run.created_at else None,
        }


# ============================================================================
# DEAL PRODUCT SERIALIZERS
# ============================================================================

DISCOUNT_PERCENT_MIN = Decimal('0')
DISCOUNT_PERCENT_MAX = Decimal('100')


def validate_discount_percent_range(value):
    """TD-74 — the discount must stay within [0, 100].

    Enforced here so an out-of-range value is a clean business-rule 400 instead
    of the IntegrityError the DB CheckConstraint
    (``deal_product_discount_percent_bounds``) would otherwise raise. Shared by
    the create and update serializers so the rule is stated once.

    Mirrors the project's ``validate_<field>`` + StandardizedValidationError +
    CoreErrorMessages convention (e.g. DecisionCycleCreateSerializer.validate_name).
    """
    if value is None:
        return value
    if value < DISCOUNT_PERCENT_MIN or value > DISCOUNT_PERCENT_MAX:
        raise StandardizedValidationError(
            CoreErrorMessages.INVALID_FIELD.format(
                field='discount_percent must be between 0 and 100'
            )
        )
    return value


class DealProductListSerializer(TenantCurrencySerializerMixin,
                                ClientScopeManager.SerializerMixin,
                                serializers.ModelSerializer):
    """
    Read-only serializer for DealProduct list views.
    """

    product_catalog_entry_detail = serializers.SerializerMethodField()
    line_total = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True,
    )
    # The unit of unit_price / line_total. Resolved from the TENANT at read
    # time (core.currency), never stored on the line — one currency per tenant,
    # no conversion.
    currency = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = DealProduct
        fields = [
            'id',
            'decision_cycle',
            'product_catalog_entry',
            'product_catalog_entry_detail',
            'quantity',
            'unit_price',
            'discount_percent',
            'line_total',
            'currency',
            'notes',
            'created_at',
            'updated_at',
        ]
        read_only_fields = fields

    def get_product_catalog_entry_detail(self, obj):
        entry = obj.product_catalog_entry
        if not entry:
            return None
        return {
            'id': str(entry.id),
            'name': entry.name,
            'default_unit_price': str(entry.default_unit_price) if entry.default_unit_price is not None else None,
        }


class DealProductCreateSerializer(ClientScopeManager.SerializerMixin, serializers.ModelSerializer):
    """
    Write serializer for DealProduct creation.

    decision_cycle is NOT a serializer field — it is injected from the
    view context (URL kwargs) in validate(). This matches the pattern
    where the resource is nested under a cycle endpoint.

    validators=[] bypasses the DRF auto-generated UniqueTogetherValidator
    from the composite constraint (decision_cycle, product_catalog_entry,
    client_id). Uniqueness is enforced explicitly via
    validate_client_scoped_uniqueness().
    """

    class Meta:
        model = DealProduct
        fields = [
            'product_catalog_entry',
            'quantity',
            'unit_price',
            'discount_percent',
            'notes',
        ]
        validators = []
        extra_kwargs = {
            'product_catalog_entry': {'required': True},
            'quantity': {'required': False},
            'unit_price': {'required': False, 'allow_null': True},
            'discount_percent': {'required': False},
            'notes': {'required': False, 'allow_blank': True},
        }

    def validate_discount_percent(self, value):
        return validate_discount_percent_range(value)

    def validate(self, attrs):
        client_id = self._get_client_id_from_context()
        attrs['client_id'] = client_id

        decision_cycle = self.context.get('decision_cycle')
        if not decision_cycle:
            raise StandardizedValidationError(
                CoreErrorMessages.REQUIRED_FIELD.format(field='decision_cycle')
            )
        attrs['decision_cycle'] = decision_cycle

        self.validate_client_scoped_uniqueness(
            data=attrs,
            unique_fields=['decision_cycle', 'product_catalog_entry'],
            model_class=DealProduct,
            error_message=CoreErrorMessages.UNIQUE_CONSTRAINT.format(
                fields='decision_cycle, product_catalog_entry'
            ),
        )

        return attrs

    def create(self, validated_data):
        user = self.context.get('request').user if self.context.get('request') else None
        instance = DealProduct(**validated_data)
        instance.save(user=user)
        return instance


class DealProductUpdateSerializer(ClientScopeManager.SerializerMixin, serializers.ModelSerializer):
    """
    Restricted PATCH serializer for DealProduct.

    product_catalog_entry is not changeable after creation.
    decision_cycle is immutable — not exposed.

    validators=[] bypasses the DRF auto-generated UniqueTogetherValidator.
    """

    class Meta:
        model = DealProduct
        fields = [
            'quantity',
            'unit_price',
            'discount_percent',
            'notes',
        ]
        validators = []
        extra_kwargs = {
            'quantity': {'required': False},
            'unit_price': {'required': False, 'allow_null': True},
            'discount_percent': {'required': False},
            'notes': {'required': False, 'allow_blank': True},
        }

    def validate_discount_percent(self, value):
        return validate_discount_percent_range(value)

    def update(self, instance, validated_data):
        user = self.context.get('request').user if self.context.get('request') else None
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save(user=user)
        return instance


# ============================================================================
# MANAGER NOTE SERIALIZERS
# ============================================================================

class ManagerNoteListSerializer(ClientScopeManager.SerializerMixin, serializers.ModelSerializer):
    """
    Read-only serializer for ManagerNote list views.
    """

    author_name = serializers.SerializerMethodField()

    class Meta:
        model = ManagerNote
        fields = [
            'id',
            'decision_cycle',
            'content',
            'created_by',
            'author_name',
            'created_at',
            'updated_at',
        ]
        read_only_fields = fields

    def get_author_name(self, obj):
        user = obj.created_by
        if not user:
            return None
        name = f"{user.first_name or ''} {user.last_name or ''}".strip()
        return name or user.email


class ManagerNoteCreateSerializer(ClientScopeManager.SerializerMixin, serializers.ModelSerializer):
    """
    Write serializer for ManagerNote creation.

    decision_cycle is injected from the view context (URL kwargs).
    """

    class Meta:
        model = ManagerNote
        fields = [
            'content',
        ]
        extra_kwargs = {
            'content': {'required': True, 'allow_blank': False},
        }

    def validate(self, attrs):
        client_id = self._get_client_id_from_context()
        attrs['client_id'] = client_id

        decision_cycle = self.context.get('decision_cycle')
        if not decision_cycle:
            raise StandardizedValidationError(
                CoreErrorMessages.REQUIRED_FIELD.format(field='decision_cycle')
            )
        attrs['decision_cycle'] = decision_cycle

        return attrs

    def create(self, validated_data):
        user = self.context.get('request').user if self.context.get('request') else None
        instance = ManagerNote(**validated_data)
        instance.save(user=user)
        return instance
