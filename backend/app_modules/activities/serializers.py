# app_modules/activities/serializers.py
"""
Serializers for Activity module.

Follows the same patterns as CompanyAccountSerializer and DecisionCycleSerializer.
"""

from rest_framework import serializers
from core.client_scope import ClientScopeManager
from core.error_messages import CoreErrorMessages, ActivityErrorMessages, AccountErrorMessages
from core.exceptions import StandardizedValidationError
from app_modules.accounts.models import CompanyAccount
from app_modules.contacts.models import Contact
from app_modules.decision_cycles.models import DecisionCycle, DecisionStep
from end_users.models import User
from .models import Activity
from .constants import ActivityStatus, NoNextStepReason
from .services import ActivitySequenceService, SequenceScope

# ============================================================================
# HELPER SERIALIZERS
# ============================================================================

class ActivityAccountSerializer(serializers.ModelSerializer):
    """Minimal account serializer for activity responses."""
    
    class Meta:
        model = CompanyAccount
        fields = ['id', 'company_name']
        read_only_fields = fields


class ActivityContactSerializer(serializers.ModelSerializer):
    """Minimal contact serializer for activity responses."""
    
    full_name = serializers.SerializerMethodField(read_only=True)
    department_name = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = Contact
        fields = [
            'id', 'first_name', 'last_name', 'full_name',
            'email', 'phone_number', 'job_title', 'department_name'
        ]
        read_only_fields = fields
    
    def get_full_name(self, obj):
        return f"{obj.first_name or ''} {obj.last_name or ''}".strip()
    
    def get_department_name(self, obj):
        """Get department display name from standard_department."""
        if obj.standard_department:
            return obj.standard_department.get_name_display()
        return None

class ActivityUserSerializer(serializers.ModelSerializer):
    """
    Minimal user serializer for activity-related users.
    
    Used for:
        - Activity owner
        - Invited users
    """
    
    full_name = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = User
        fields = ['id', 'email', 'first_name', 'last_name', 'full_name']
        read_only_fields = fields
    
    def get_full_name(self, obj):
        return f"{obj.first_name or ''} {obj.last_name or ''}".strip()


class ActivityDecisionCycleSerializer(serializers.ModelSerializer):
    """Minimal decision cycle serializer for activity responses."""
    
    class Meta:
        model = DecisionCycle
        fields = ['id', 'name']
        read_only_fields = fields


class ActivityDecisionStepSerializer(serializers.ModelSerializer):
    """Minimal decision step serializer for activity responses."""
    
    stage_display = serializers.CharField(source='get_stage_display', read_only=True)
    
    class Meta:
        model = DecisionStep
        fields = ['id', 'name', 'stage', 'stage_display', 'status']
        read_only_fields = fields


class ActivityMinimalSerializer(serializers.ModelSerializer):
    """Minimal serializer for previous/next activity references."""
    class Meta:
        model = Activity
        fields = ['id', 'title', 'activity_type', 'status']
        read_only_fields = fields


class ActivityCompactSerializer(serializers.ModelSerializer):
    """
    Compact activity representation for cross-module embedding.

    Purpose:
        Lightweight, read-only Activity payload designed to be nested inside
        OTHER modules' serializers (Signals today, potentially Campaigns,
        Decision Cycles, etc. later). It answers the "which CRM conversation
        is this anchored to?" question without dragging the full Activity
        detail payload into every signal read.

    Payload contract:
        {
            "id":            UUID string,
            "type_display":  Human-readable activity type
                             (e.g. "Phone Call", "Meeting", "Email"),
            "subject":       Activity title (Activity.title),
            "occurred_at":   ISO-8601 datetime, or null. Derived from:
                             1. completed_at (if set — the moment the
                                activity actually took place),
                             2. else combination of scheduled_date +
                                scheduled_time (planned moment),
                             3. else null (activity has neither an
                                execution nor a scheduled moment yet).
            "contacts":      List of compact contacts on this activity:
                             [{id, first_name, last_name, job_title}, ...]
        }

    Performance notes:
        - Callers SHOULD prefetch_related('contacts') and
          select_related on the parent FK to avoid N+1.
        - The M2M `contacts` iteration uses an evaluated queryset;
          if the caller already prefetched, no extra query runs.
        - Intentionally NOT ClientScopeManager.SerializerMixin — this
          serializer is read-only and consumed via nesting; client
          scoping is the caller's responsibility (already handled by
          the parent ViewSet's ClientScopeManager).

    Wave A note:
        Added to enrich `source_activity` in BaseSignalDetailSerializer.
        Reusable by the Objective port in Wave B.
    """

    type_display = serializers.SerializerMethodField(read_only=True)
    subject = serializers.CharField(source='title', read_only=True)
    occurred_at = serializers.SerializerMethodField(read_only=True)
    contacts = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Activity
        fields = ['id', 'type_display', 'subject', 'occurred_at', 'contacts']
        read_only_fields = fields

    def get_type_display(self, obj):
        """Human-readable activity type (from TextChoices labels)."""
        return obj.get_activity_type_display() if obj.activity_type else None

    def get_occurred_at(self, obj):
        """
        Best-effort ISO-8601 timestamp for "when did this happen".

        Priority:
          1. completed_at — the activity actually took place.
          2. scheduled_date + scheduled_time — the planned moment.
             Time defaults to 00:00 when only a date is known.
          3. None — no execution nor scheduling data yet.
        """
        if obj.completed_at:
            return obj.completed_at.isoformat()

        if obj.scheduled_date:
            # Django returns datetime.date + datetime.time when both set.
            # We combine into a naive ISO string. TZ is left to the caller
            # since Activity.scheduled_date / _time are naive by design.
            from datetime import datetime, time
            time_part = obj.scheduled_time or time(0, 0)
            combined = datetime.combine(obj.scheduled_date, time_part)
            return combined.isoformat()

        return None

    def get_contacts(self, obj):
        """
        Compact list of contacts attached to this activity.

        Shape per entry: {id, first_name, last_name, job_title}.
        Empty list when the activity has no linked contacts.
        """
        return [
            {
                'id': str(contact.id),
                'first_name': contact.first_name,
                'last_name': contact.last_name,
                'job_title': getattr(contact, 'job_title', None),
            }
            for contact in obj.contacts.all()
        ]



# ============================================================================
# LIST SERIALIZER (Performance optimized)
# ============================================================================

class ActivityListSerializer(ClientScopeManager.SerializerMixin, serializers.ModelSerializer):
    """
    Lightweight serializer for activity lists (performance optimized).
    
    Principles:
        - Minimum fields for table display
        - SerializerMethodField for relations (avoid N+1)
        - No deep nested serializers
    """
    
    # Display fields
    activity_type_display = serializers.SerializerMethodField(read_only=True)
    status_display = serializers.SerializerMethodField(read_only=True)
    outcome_display = serializers.SerializerMethodField(read_only=True)
    
    # Relations as simple objects
    account = serializers.SerializerMethodField(read_only=True)
    owner = serializers.SerializerMethodField(read_only=True)
    decision_step = serializers.SerializerMethodField(read_only=True)
    
    # Computed fields
    scheduled_date = serializers.SerializerMethodField(read_only=True)
    is_overdue = serializers.BooleanField(read_only=True)
    is_scheduled = serializers.BooleanField(read_only=True)
    contacts_count = serializers.SerializerMethodField(read_only=True)
    contacts = serializers.SerializerMethodField(read_only=True)
    no_answer_count = serializers.SerializerMethodField(read_only=True)
    campaign_contact_id = serializers.SerializerMethodField(read_only=True)
    campaign_contact_status = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Activity
        fields = [
            # Identity
            'id', 'title',

            # Type & Status
            'activity_type', 'activity_type_display',
            'status', 'status_display',
            'outcome', 'outcome_display',

            # Scheduling
            'scheduled_date', 'scheduled_time',
            'due_date', 'completed_at',

            # Call to action
            'call_to_action',

            # Next Step Agreement
            'next_step_agreed',

            # Relations (simple objects)
            'account', 'owner', 'decision_step',

            # Computed
            'is_overdue', 'is_scheduled', 'contacts_count', 'contacts',

            # Campaign sequence position — used by frontend to enforce step order
            'sequence_position',

            # Campaign retry tracking (CALL type)
            'no_answer_count',

            # Campaign callback context
            'is_callback_followup',
            'campaign_contact_id',
            'campaign_contact_status',

            # Timestamps
            'created_at', 'updated_at',
        ]

        read_only_fields = fields
    
    def get_activity_type_display(self, obj):
        return obj.get_activity_type_display() if obj.activity_type else None
    
    def get_status_display(self, obj):
        return obj.get_status_display() if obj.status else None
    
    def get_outcome_display(self, obj):
        return obj.get_outcome_display() if obj.outcome else None
    
    def get_account(self, obj):
        if obj.account:
            return {
                'id': str(obj.account.id),
                'company_name': obj.account.company_name
            }
        return None
    
    def get_owner(self, obj):
        if obj.owner:
            return {
                'id': str(obj.owner.id),
                'email': obj.owner.email,
                'full_name': f"{obj.owner.first_name or ''} {obj.owner.last_name or ''}".strip()
            }
        return None
    
    def get_decision_step(self, obj):
        if obj.decision_step:
            return {
                'id': str(obj.decision_step.id),
                'name': obj.decision_step.name,
                'stage': obj.decision_step.stage
            }
        return None
    
    def get_contacts_count(self, obj):
        if hasattr(obj, '_contacts_count'):
            return obj._contacts_count
        return obj.contacts.count()
    
    def get_contacts(self, obj):
        """Return minimal contact list (id, name, job_title, department) for playlist/modal use."""
        return [
            {
                'id': str(c.id),
                'first_name': c.first_name or '',
                'last_name': c.last_name or '',
                'job_title': c.job_title or '',
                'email': c.email or '',
                'department': c.standard_department.get_name_display() if c.standard_department else '',
                'standard_department_id': c.standard_department_id,
                'standard_department_name': c.standard_department.get_name_display() if c.standard_department else None,
            }
            for c in obj.contacts.all()
        ]
    
    def get_no_answer_count(self, obj):
        """Return no_answer_count directly from the activity."""
        return obj.no_answer_count

    def get_campaign_contact_id(self, obj):
        """Return campaign_contact UUID for frontend state machine actions."""
        if obj.campaign_contact_id:
            return str(obj.campaign_contact_id)
        return None

    def get_campaign_contact_status(self, obj):
        """
        Return CampaignContact status string.
        Used by the frontend to route the activity into the correct playlist
        section (PAUSED when CALLBACK_PENDING, TODAY/UPCOMING otherwise).
        campaign_contact must be in select_related for N+1 safety.
        """
        if obj.campaign_contact_id and obj.campaign_contact:
            return obj.campaign_contact.status
        return None
    
    def get_scheduled_date(self, obj):
        """Return scheduled_date. Campaign activities always have confirmed DB dates."""
        return str(obj.scheduled_date) if obj.scheduled_date else None

    def get_is_overdue(self, obj):
        """Overdue = PLANNED/IN_PROGRESS with scheduled_date in the past."""
        from django.utils import timezone

        if obj.status in (ActivityStatus.COMPLETED, ActivityStatus.CANCELLED):
            return False
        if not obj.scheduled_date:
            return False
        return obj.scheduled_date < timezone.now().date()


# ============================================================================
# DETAIL SERIALIZER
# ============================================================================

class ActivitySerializer(ClientScopeManager.SerializerMixin, serializers.ModelSerializer):
    """
    Complete serializer for activity detail view.
    """
    
    # Display fields
    activity_type_display = serializers.SerializerMethodField(read_only=True)
    status_display = serializers.SerializerMethodField(read_only=True)
    outcome_display = serializers.SerializerMethodField(read_only=True)
    
    # Nested serializers for relations
    account_detail = ActivityAccountSerializer(source='account', read_only=True)
    contacts_detail = ActivityContactSerializer(source='contacts', many=True, read_only=True)
    owner_detail = ActivityUserSerializer(source='owner', read_only=True)
    invited_users_detail = ActivityUserSerializer(source='invited_users', many=True, read_only=True)
    decision_cycle_detail = ActivityDecisionCycleSerializer(source='decision_cycle', read_only=True)
    decision_step_detail = ActivityDecisionStepSerializer(source='decision_step', read_only=True)
    
    # Previous/Next activity info
    previous_activity_info = serializers.SerializerMethodField(read_only=True)
    next_activity_info = serializers.SerializerMethodField(read_only=True)

    # Sequence context (NEW - dynamic calculation based on scope)
    # Replaces manual previous/next with calculated sequence
    sequence_context = serializers.SerializerMethodField(read_only=True)

    # Next Step Agreement (computed fields for UX logic)
    no_next_step_reason_display = serializers.SerializerMethodField(read_only=True)
    has_next_in_sequence = serializers.SerializerMethodField(read_only=True)
    effective_has_next_step = serializers.SerializerMethodField(read_only=True)
    
    # Computed fields
    is_overdue = serializers.BooleanField(read_only=True)
    is_scheduled = serializers.BooleanField(read_only=True)

    completed_by_name = serializers.SerializerMethodField(read_only=True)
    campaign_detail = serializers.SerializerMethodField(read_only=True)
    source_activity_detail = serializers.SerializerMethodField(read_only=True)
    no_answer_count = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = Activity
        fields = [
            # Identity
            'id', 'title',
            
            # Type & Status
            'activity_type', 'activity_type_display',
            'status', 'status_display',
            'outcome', 'outcome_display',
            'outcome_notes',
            
            # Scheduling
            'scheduled_date', 'scheduled_time',
            'due_date', 'completed_at', 'completed_by_name',
            
            # Content
            'description', 'call_to_action',
            
            # Next Step Agreement
            'next_step_agreed', 'no_next_step_reason',
            'no_next_step_reason_display', 'has_next_in_sequence', 'effective_has_next_step',
            
            # Relations (IDs for write)
            
            # Relations (IDs for write)
            'account', 'decision_cycle', 'decision_step',
            
            # Relations (nested for read)
            'account_detail', 'contacts_detail', 'owner_detail', 
            'invited_users_detail',
            'decision_cycle_detail', 'decision_step_detail',

             # Campaign context (when activity was generated by a campaign)
            'campaign_detail',
            # Origin tracing (campaign activity that triggered this decision cycle activity)
            'source_activity_detail',
            
            # Sequence context (replaces previous/next linked list)
            'previous_activity_info', 'next_activity_info',
            
            # Sequence context (NEW - dynamic playlist calculation)
            'sequence_context',
            
            # Future fields (stubs)
            'transcript', 'preparation_notes',

            # Campaign retry tracking
            'no_answer_count',
            
            # Computed
            'is_overdue', 'is_scheduled',
            'created_by', 'updated_by', 'created_at', 'updated_at'
        ]

        read_only_fields = [
            'id', 'activity_type_display', 'status_display', 'outcome_display',
            'account_detail', 'contacts_detail', 'owner_detail',
            'decision_cycle_detail', 'decision_step_detail',
            'previous_activity_info', 'next_activity_info', 'campaign_detail',
            'no_next_step_reason_display', 'has_next_in_sequence', 'effective_has_next_step',
            'is_overdue', 'is_scheduled',
            'created_by', 'updated_by', 'created_at', 'updated_at'
        ]
    
    def get_activity_type_display(self, obj):
        return obj.get_activity_type_display() if obj.activity_type else None
    
    def get_status_display(self, obj):
        return obj.get_status_display() if obj.status else None
    
    def get_outcome_display(self, obj):
        return obj.get_outcome_display() if obj.outcome else None

    def get_campaign_detail(self, obj):
        """Return minimal campaign info when activity is linked to a campaign."""
        if not obj.campaign_id:
            return None
        campaign = obj.campaign
        if not campaign:
            return None
        return {
            'id': str(campaign.id),
            'name': campaign.name,
            'campaign_status': campaign.status,
            'sequence_position': obj.sequence_position,
        }
    
    def get_previous_activity_info(self, obj):
        if obj.decision_cycle_id:
            context = ActivitySequenceService.get_sequence_context(
                activity=obj,
                scope=SequenceScope.DECISION_CYCLE
            )
        elif obj.campaign_id:
            context = ActivitySequenceService.get_sequence_context(
                activity=obj,
                scope=SequenceScope.CAMPAIGN
            )
        else:
            return None
        if context and context.get('previous_activities'):
            return context['previous_activities'][0]
        return None
    
    def get_source_activity_detail(self, obj):
        """
        Return source attribution for this activity.

        Two cases:
        1. source_activity is set — derives context from the source activity
           (Campaign or DecisionCycle it belonged to).
        2. source_decision_cycle is set — direct DC reference, no prior activity
           (e.g. Targeted campaign enrollment triggered from a DC context).
        """
        # Case 1: source is a prior activity
        if obj.source_activity_id:
            src = obj.source_activity
            if not src:
                return None

            if src.campaign_id and src.campaign:
                source_context = {
                    'type': 'CAMPAIGN',
                    'id': str(src.campaign.id),
                    'name': src.campaign.name,
                }
            elif src.decision_cycle_id and src.decision_cycle:
                source_context = {
                    'type': 'DECISION_CYCLE',
                    'id': str(src.decision_cycle.id),
                    'name': src.decision_cycle.name,
                }
            else:
                source_context = {
                    'type': 'MANUAL',
                    'id': None,
                    'name': None,
                }

            return {
                'id': str(src.id),
                'title': src.title,
                'activity_type': src.activity_type,
                'status': src.status,
                'source_context': source_context,
            }

        # Case 2: source is a Decision Cycle directly (no prior activity)
        if obj.source_decision_cycle_id:
            dc = obj.source_decision_cycle
            if not dc:
                return None
            return {
                'id': None,
                'title': None,
                'activity_type': None,
                'status': None,
                'source_context': {
                    'type': 'DECISION_CYCLE',
                    'id': str(dc.id),
                    'name': dc.name,
                },
            }

        return None
    
    def get_next_activity_info(self, obj):
        if obj.decision_cycle_id:
            context = ActivitySequenceService.get_sequence_context(
                activity=obj,
                scope=SequenceScope.DECISION_CYCLE
            )
        elif obj.campaign_id:
            context = ActivitySequenceService.get_sequence_context(
                activity=obj,
                scope=SequenceScope.CAMPAIGN
            )
        else:
            return None

        if context and context.get('next_activities'):
            return context['next_activities'][0]

        # E3: If no next activity in sequence, check for a derived DC activity
        # created from this campaign activity (source_activity FK forward lookup).
        # This surfaces the DC follow-up created after a successful campaign outcome.
        if obj.campaign_id and not obj.decision_cycle_id:
            derived = (
                Activity.objects
                .filter(source_activity=obj)
                .exclude(status=ActivityStatus.CANCELLED)
                .select_related('decision_cycle')
                .order_by('created_at')
                .first()
            )
            if derived:
                return {
                    'id': str(derived.id),
                    'title': derived.title,
                    'activity_type': derived.activity_type,
                    'status': derived.status,
                    'is_overdue': False,
                    'outcome': derived.outcome,
                    'scheduled_date': (
                        derived.scheduled_date.isoformat()
                        if derived.scheduled_date else None
                    ),
                    'due_date': (
                        derived.due_date.isoformat()
                        if derived.due_date else None
                    ),
                    'decision_step_name': (
                        derived.decision_step.name
                        if derived.decision_step else None
                    ),
                    'source_type': 'DERIVED_DC',
                }

        return None
    
    def get_sequence_context(self, obj):
        """
        Get the dynamic sequence context for this activity.
        
        Calculates previous/next activities based on:
        - decision_step.order (pipeline position)
        - COALESCE(scheduled_date, due_date)
        - COALESCE(scheduled_time, due_time)
        - created_at (fallback)
        
        Returns None if activity doesn't belong to a decision_cycle.
        
        NOTE: Uses _get_cached_sequence_context to ensure consistency
        with get_effective_has_next_step calculations.
        """
        if not obj.decision_cycle_id and not obj.campaign_id:
            return None
        
        return self._get_cached_sequence_context(obj)
    
    def get_no_next_step_reason_display(self, obj):
        """
        Get the display label for no_next_step_reason.
        
        Handles both standard codes (CLOSE_WON, etc.) and custom "OTHER: text" format.
        """
        if not obj.no_next_step_reason:
            return None
        
        reason = obj.no_next_step_reason
        
        # Check if it's a standard code
        if reason in NoNextStepReason.values:
            return NoNextStepReason(reason).label
        
        # Handle "OTHER: custom text" format
        if reason.startswith('OTHER:'):
            return reason[6:].strip()  # Return the custom text
        
        # Fallback: return as-is
        return reason
    
    def get_has_next_in_sequence(self, obj):
        """
        Check if activity has PENDING next activities in its sequence.
        
        Returns:
            True: has pending (PLANNED) next activities
            False: no pending next activities in sequence
            None: activity is standalone (not in a cycle)
        """
        if not obj.decision_cycle_id:
            return None
        
        context = self._get_cached_sequence_context(obj)
        if context and context.get('next_activities'):
            # Only count PLANNED as valid "next steps"
            pending_next = [
                act for act in context['next_activities']
                if act.get('status') == 'PLANNED'
            ]
            return len(pending_next) > 0
        return False
    
    def get_effective_has_next_step(self, obj):
        """
        Determine the effective next step status for UX logic.
        
        Priority:
            1. If PENDING next_activities exist in sequence → True (reality wins)
            2. If next_activity FK is set and PENDING → True
            3. If next_step_agreed is explicitly set → return its value
            4. Otherwise → None (ask user to confirm)
        
        Returns:
            True: next step exists or was agreed
            False: explicitly marked as no next step AND no pending activities
            None: unknown, UI should prompt user
        """
        
        # Priority 1: Check sequence context for PENDING activities in cycle
        # Handles both decision cycle and campaign scopes via _get_cached_sequence_context.
        if obj.decision_cycle_id or obj.campaign_id:
            context = self._get_cached_sequence_context(obj)
            
            if context and context.get('next_activities'):
                all_next = context['next_activities']
                
                # Filter to only count PLANNED activities
                pending_next = [
                    act for act in all_next
                    if act.get('status') == 'PLANNED'
                ]
                
                if pending_next:
                    return True
    
        
        # Priority 2: Explicit value (only applies when no pending activities exist)
        if obj.next_step_agreed is not None:
            return obj.next_step_agreed
        return None
    
    def get_completed_by_name(self, obj):
        """Return name of user who completed/cancelled the activity (last updater at closure time)."""
        if obj.status not in ('COMPLETED', 'CANCELLED'):
            return None
        if obj.updated_by:
            name = f"{obj.updated_by.first_name or ''} {obj.updated_by.last_name or ''}".strip()
            return name or obj.updated_by.email
        return None
    
    def _get_cached_sequence_context(self, obj):
        cache_attr = '_sequence_context_cache'
        
        if not hasattr(obj, cache_attr):
            if obj.decision_cycle_id:
                # Decision cycle takes precedence when both are set
                scope = SequenceScope.DECISION_CYCLE
            elif obj.campaign_id:
                scope = SequenceScope.CAMPAIGN
            else:
                setattr(obj, cache_attr, None)
                return None
            
            setattr(obj, cache_attr, ActivitySequenceService.get_sequence_context(
                activity=obj,
                scope=scope
            ))
        
        return getattr(obj, cache_attr)
    
    def get_no_answer_count(self, obj):
        """Return no_answer_count directly from the activity."""
        return obj.no_answer_count


# ============================================================================
# CREATE SERIALIZER
# ============================================================================

class ActivityCreateSerializer(ClientScopeManager.SerializerMixin, serializers.ModelSerializer):
    """
    Serializer for activity creation.
    """
    
    account_id = serializers.UUIDField(write_only=True)
    contact_ids = serializers.ListField(
        child=serializers.UUIDField(),
        write_only=True,
        required=False,
        default=list
    )
    invited_user_ids = serializers.ListField(
        child=serializers.UUIDField(),
        write_only=True,
        required=False,
        default=list
    )
    decision_cycle_id = serializers.UUIDField(write_only=True, required=False, allow_null=True)
    decision_step_id = serializers.UUIDField(write_only=True, required=False, allow_null=True)
    source_activity_id = serializers.UUIDField(write_only=True, required=False, allow_null=True)

    class Meta:
        model = Activity
        fields = [
            # Required
            'title', 'activity_type', 'account_id',

            # Optional
            'description', 'call_to_action',
            'status', 'outcome', 'outcome_notes',
            'scheduled_date', 'scheduled_time', 'due_date',

            # Relations
            'contact_ids', 'invited_user_ids',
            'decision_cycle_id', 'decision_step_id',
            'source_activity_id',

            # Future fields
            'transcript', 'preparation_notes'
        ]
        extra_kwargs = {
            'title': {
                'required': True,
                'error_messages': {
                    'required': CoreErrorMessages.REQUIRED_FIELD.format(field='Title'),
                }
            },
            'activity_type': {
                'required': True,
                'error_messages': {
                    'required': CoreErrorMessages.REQUIRED_FIELD.format(field='Activity Type'),
                }
            }
        }
    
    def validate_title(self, value):
        if not value or not value.strip():
            raise StandardizedValidationError(
                CoreErrorMessages.REQUIRED_FIELD.format(field='Title')
            )
        return value.strip()
    
    def validate_status(self, value):
        """New activities must always be created with PLANNED status."""
        from .constants import ActivityStatus
        if value and value != ActivityStatus.PLANNED:
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_FIELD.format(
                    field='status (new activities must be created with status PLANNED)'
                )
            )
        return value
    
    def validate(self, attrs):
        """Global validation for activity creation."""
        try:
            client_id = self._get_client_id_from_context()
            attrs['client_id'] = client_id
            
            # =================================================================
            # Validate account
            # =================================================================
            account_id = attrs.pop('account_id')
            try:
                account = CompanyAccount.objects.get(id=account_id, client_id=client_id)
                attrs['account'] = account
            except CompanyAccount.DoesNotExist:
                raise StandardizedValidationError(
                    AccountErrorMessages.ACCOUNT_NOT_FOUND
                )
            
            # =================================================================
            # REQUIRED: At least one contact
            # =================================================================
            contact_ids = attrs.pop('contact_ids', [])
            if not contact_ids:
                raise StandardizedValidationError(
                    CoreErrorMessages.REQUIRED_FIELD.format(field='At least one contact')
                )
            
            contacts = Contact.objects.filter(
                id__in=contact_ids,
                client_id=client_id,
                account=account
            )
            if contacts.count() != len(contact_ids):
                raise StandardizedValidationError(
                    CoreErrorMessages.INVALID_FIELD.format(field='Some contacts not found or do not belong to this account')
                )
            attrs['_contacts'] = list(contacts)
            
            # =================================================================
            # REQUIRED: At least one date (scheduled_date OR due_date)
            # =================================================================
            scheduled_date = attrs.get('scheduled_date')
            due_date = attrs.get('due_date')
            
            if not scheduled_date and not due_date:
                raise StandardizedValidationError(
                    CoreErrorMessages.REQUIRED_FIELD.format(field='Scheduled date or due date')
                )
            
            # =================================================================
            # Validate invited_users (optional)
            # =================================================================
            invited_user_ids = attrs.pop('invited_user_ids', [])
            if invited_user_ids:
                invited_users = User.objects.filter(
                    id__in=invited_user_ids,
                    client_account_id=client_id
                )
                if invited_users.count() != len(invited_user_ids):
                    raise StandardizedValidationError(
                        CoreErrorMessages.INVALID_FIELD.format(field='Some invited users not found')
                    )
                attrs['_invited_users'] = list(invited_users)
            
            # =================================================================
            # Validate decision_cycle (optional)
            # =================================================================
            decision_cycle_id = attrs.pop('decision_cycle_id', None)
            if decision_cycle_id:
                try:
                    decision_cycle = DecisionCycle.objects.get(
                        id=decision_cycle_id,
                        client_id=client_id,
                        account=account
                    )
                    attrs['decision_cycle'] = decision_cycle
                except DecisionCycle.DoesNotExist:
                    raise StandardizedValidationError(
                        CoreErrorMessages.OBJECT_NOT_FOUND
                    )
            
            # =================================================================
            # Validate decision_step (optional, requires cycle)
            # =================================================================
            decision_step_id = attrs.pop('decision_step_id', None)
            if decision_step_id:
                decision_cycle = attrs.get('decision_cycle')
                if not decision_cycle:
                    raise StandardizedValidationError(
                        ActivityErrorMessages.CYCLE_REQUIRED_FOR_STEP
                    )
                try:
                    decision_step = DecisionStep.objects.get(
                        id=decision_step_id,
                        cycle=decision_cycle
                    )
                    attrs['decision_step'] = decision_step
                except DecisionStep.DoesNotExist:
                    raise StandardizedValidationError(
                        CoreErrorMessages.OBJECT_NOT_FOUND
                    )
            
            # RULE: If cycle is provided, step is REQUIRED (pipeline steps are fixed)
            if attrs.get('decision_cycle') and not attrs.get('decision_step'):
                raise StandardizedValidationError(
                    ActivityErrorMessages.STEP_REQUIRES_CYCLE
                )
            
            # =================================================================
            # Validate source_activity (optional — traceability FK)
            # =================================================================
            source_activity_id = attrs.pop('source_activity_id', None)
            if source_activity_id:
                try:
                    source_activity = Activity.objects.get(
                        id=source_activity_id,
                        client_id=client_id,
                    )
                    attrs['source_activity'] = source_activity
                except Activity.DoesNotExist:
                    raise StandardizedValidationError(
                        CoreErrorMessages.OBJECT_NOT_FOUND
                    )

            return attrs
            
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_DATA.format(detail=str(e))
            )
    
    def create(self, validated_data):
        """Create activity with proper audit fields and M2M."""
        user = self.context.get('request').user if self.context.get('request') else None
        contacts = validated_data.pop('_contacts', [])
        invited_users = validated_data.pop('_invited_users', [])
        client_id = validated_data.pop('client_id', None)
        
        # Set owner to current user
        validated_data['owner'] = user
        
        # Create instance
        instance = Activity(**validated_data)
        instance.save(user=user, client_id=client_id)
        
        # Set M2M contacts
        if contacts:
            instance.contacts.set(contacts)
        
        # Set M2M invited_users
        if invited_users:
            instance.invited_users.set(invited_users)
        
        return instance


# ============================================================================
# UPDATE SERIALIZER
# ============================================================================

class ActivityUpdateSerializer(ClientScopeManager.SerializerMixin, serializers.ModelSerializer):
    """
    Serializer for activity updates.
    
    Business Rules:
        - contacts cannot be empty (at least 1 required)
        - outcome is only valid when status=COMPLETED
        - reopening (from COMPLETED to other status) clears outcome
    """

    owner_id = serializers.UUIDField(write_only=True, required=False)
    
    contact_ids = serializers.ListField(
        child=serializers.UUIDField(),
        write_only=True,
        required=False
    )
    invited_user_ids = serializers.ListField(
        child=serializers.UUIDField(),
        write_only=True,
        required=False
    )
    decision_cycle_id = serializers.UUIDField(write_only=True, required=False, allow_null=True)
    decision_step_id = serializers.UUIDField(write_only=True, required=False, allow_null=True)
    
    class Meta:
        model = Activity
        fields = [
            # Editable
            'title', 'activity_type',
            'description', 'call_to_action',
            'status', 'outcome', 'outcome_notes',
            'scheduled_date', 'scheduled_time', 'due_date',
            
            # Next Step Agreement
            'next_step_agreed', 'no_next_step_reason',
            
            # Relations
            'owner_id', 'contact_ids', 'invited_user_ids',
            'decision_cycle_id', 'decision_step_id',
            
            # Future fields
            'transcript', 'preparation_notes'
        ]
    
    def validate(self, attrs):
        """Validate update data with status/outcome business rules."""
        try:
            client_id = self._get_client_id_from_context()
            instance = self.instance
            account = instance.account
            
            # =================================================================
            # STATUS CHANGE LOGIC
            # =================================================================
            new_status = attrs.get('status')
            current_status = instance.status
            
            if new_status and new_status != current_status:
                # Rule: If reopening (from COMPLETED to non-COMPLETED), clear outcome
                if current_status == ActivityStatus.COMPLETED and new_status != ActivityStatus.COMPLETED:
                    attrs['outcome'] = None
                    attrs['outcome_notes'] = None
                    attrs['completed_at'] = None
                
                # Rule: If completing, set completed_at
                if new_status == ActivityStatus.COMPLETED and current_status != ActivityStatus.COMPLETED:
                    from django.utils import timezone
                    attrs['completed_at'] = timezone.now()
            
            # =================================================================
            # OUTCOME VALIDATION
            # =================================================================
            new_outcome = attrs.get('outcome')
            final_status = new_status if new_status else current_status
            
            # Rule: outcome is only valid if status is COMPLETED
            if new_outcome and final_status != ActivityStatus.COMPLETED:
                raise StandardizedValidationError(
                    CoreErrorMessages.INVALID_DATA.format(
                        detail='Outcome can only be set when activity is completed'
                    )
                )
            
            # =================================================================
            # DATE VALIDATION (at least one date must survive after update)
            # =================================================================
            # Compute final state: if field in attrs, user explicitly changed it;
            # otherwise keep current instance value.
            # This allows switching from scheduled_date to due_date (or vice versa)
            # by clearing one and setting the other in the same request.
            final_scheduled = attrs['scheduled_date'] if 'scheduled_date' in attrs else instance.scheduled_date
            final_due = attrs['due_date'] if 'due_date' in attrs else instance.due_date

            if not final_scheduled and not final_due:
                raise StandardizedValidationError(
                    CoreErrorMessages.REQUIRED_FIELD.format(field='Scheduled date or due date')
                )

            # Auto-clear scheduled_time when scheduled_date is removed
            if 'scheduled_date' in attrs and not attrs['scheduled_date']:
                attrs['scheduled_time'] = None
            
            # =================================================================
            # CONTACTS VALIDATION (cannot be empty)
            # =================================================================
            if 'contact_ids' in attrs:
                contact_ids = attrs.pop('contact_ids')
                if contact_ids is not None:
                    if len(contact_ids) == 0:
                        raise StandardizedValidationError(
                            CoreErrorMessages.REQUIRED_FIELD.format(field='At least one contact')
                        )
                    contacts = Contact.objects.filter(
                        id__in=contact_ids,
                        client_id=client_id,
                        account=account
                    )
                    if contacts.count() != len(contact_ids):
                        raise StandardizedValidationError(
                            CoreErrorMessages.INVALID_FIELD.format(field='Some contacts not found')
                        )
                    attrs['_contacts'] = list(contacts)
            
            # =================================================================
            # OWNER VALIDATION
            # =================================================================
            if 'owner_id' in attrs:
                owner_id = attrs.pop('owner_id')
                if owner_id:
                    try:
                        owner = User.objects.get(id=owner_id)
                        if not owner.is_active:
                            raise StandardizedValidationError(
                                CoreErrorMessages.INVALID_FIELD.format(field='Owner (inactive user)')
                            )
                        if str(owner.client_account_id) != str(client_id):
                            raise StandardizedValidationError(
                                CoreErrorMessages.INVALID_FIELD.format(field='Owner (different client)')
                            )
                        attrs['owner'] = owner
                    except User.DoesNotExist:
                        raise StandardizedValidationError(
                            CoreErrorMessages.OBJECT_NOT_FOUND
                        )
                    
            # =================================================================
            # INVITED USERS VALIDATION
            # =================================================================
            if 'invited_user_ids' in attrs:
                invited_user_ids = attrs.pop('invited_user_ids')
                if invited_user_ids is not None:
                    if invited_user_ids:
                        invited_users = User.objects.filter(
                            id__in=invited_user_ids,
                            client_account_id=client_id
                        )
                        if invited_users.count() != len(invited_user_ids):
                            raise StandardizedValidationError(
                                CoreErrorMessages.INVALID_FIELD.format(field='Some invited users not found')
                            )
                        attrs['_invited_users'] = list(invited_users)
                    else:
                        attrs['_invited_users'] = []
            
            # =================================================================
            # DECISION CYCLE VALIDATION
            # =================================================================
            if 'decision_cycle_id' in attrs:
                decision_cycle_id = attrs.pop('decision_cycle_id')
                if decision_cycle_id:
                    try:
                        decision_cycle = DecisionCycle.objects.get(
                            id=decision_cycle_id,
                            client_id=client_id,
                            account=account
                        )
                        attrs['decision_cycle'] = decision_cycle
                    except DecisionCycle.DoesNotExist:
                        raise StandardizedValidationError(
                            CoreErrorMessages.OBJECT_NOT_FOUND
                        )
                else:
                    attrs['decision_cycle'] = None
                    # Clear step if cycle is cleared
                    if 'decision_step_id' not in attrs:
                        attrs['decision_step'] = None
            
            # =================================================================
            # DECISION STEP VALIDATION
            # =================================================================
            if 'decision_step_id' in attrs:
                decision_step_id = attrs.pop('decision_step_id')
                if decision_step_id:
                    # Get cycle from attrs or instance
                    decision_cycle = attrs.get('decision_cycle', instance.decision_cycle)
                    if not decision_cycle:
                        raise StandardizedValidationError(
                            ActivityErrorMessages.CYCLE_REQUIRED_FOR_STEP
                        )
                    try:
                        decision_step = DecisionStep.objects.get(
                            id=decision_step_id,
                            cycle=decision_cycle
                        )
                        attrs['decision_step'] = decision_step
                    except DecisionStep.DoesNotExist:
                        raise StandardizedValidationError(
                            CoreErrorMessages.OBJECT_NOT_FOUND
                        )
                else:
                    attrs['decision_step'] = None
            
            # =================================================================
            # RULE: Cycle requires step (partial-update aware)
            # =================================================================
            effective_cycle = attrs.get('decision_cycle', instance.decision_cycle)
            effective_step = attrs.get('decision_step', instance.decision_step)
            # Handle explicit None set via attrs (user clearing the step)
            if 'decision_step' in attrs:
                effective_step = attrs['decision_step']
            if effective_cycle and not effective_step:
                raise StandardizedValidationError(
                    ActivityErrorMessages.STEP_REQUIRED_FOR_CYCLE
                )
        
            
            return attrs
            
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_DATA.format(detail=str(e))
            )
    
    def update(self, instance, validated_data):
        """Update activity with proper audit fields and M2M."""
        user = self.context.get('request').user if self.context.get('request') else None
        
        # Handle M2M contacts
        contacts = validated_data.pop('_contacts', None)
        if contacts is not None:
            instance.contacts.set(contacts)
        
        # Handle M2M invited_users
        invited_users = validated_data.pop('_invited_users', None)
        if invited_users is not None:
            instance.invited_users.set(invited_users)
        
        # Update other fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        instance.save(user=user)
        return instance