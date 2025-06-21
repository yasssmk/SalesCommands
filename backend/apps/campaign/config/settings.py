"""
Campaign Configuration Settings
Centralized, type-safe configuration using dataclasses
Replaces and improves apps/campaign/config/variables.py
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Union


@dataclass(frozen=True)
class TierConfig:
    """Account tier-based configuration"""
    max_attempts: Dict[str, int] = field(default_factory=lambda: {
        'A': 3,  # Tier A accounts get 3 call attempts
        'B': 2,  # Tier B accounts get 2 call attempts
        'C': 1   # Tier C accounts get 1 call attempt
    })
    
    priority_scores: Dict[str, int] = field(default_factory=lambda: {
        'A': 100,  # Highest priority
        'B': 50,   # Medium priority
        'C': 10    # Lowest priority
    })


@dataclass(frozen=True)
class LimitsConfig:
    """Application limits and pagination settings"""
    # Default limits
    playlist_limit: int = 20
    summary_activities: int = 5
    queue_batch_size: int = 50
    bulk_operation_limit: int = 100
    pagination_size: int = 10
    max_pagination_size: int = 100
    
    # Validation limits
    max_campaign_name_length: int = 100
    max_description_length: int = 500
    max_notes_length: int = 1000
    max_bulk_items: int = 50
    max_targets_per_campaign: int = 1000
    min_target_value: float = 0.01
    max_target_value: float = 999999999.99
    
    # Performance limits
    bulk_create_batch_size: int = 50
    query_batch_size: int = 100
    max_prefetch_depth: int = 3
    cache_timeout_seconds: int = 300  # 5 minutes

    # Query optimization limits 
    max_prefetch_targets: int = 100
    max_dashboard_activities: int = 10
    max_summary_items: int = 20
    
    # Error thresholds
    max_retry_attempts: int = 3
    timeout_seconds: int = 30
    max_bulk_errors: int = 10
    warning_threshold: int = 5


@dataclass(frozen=True)
class PriorityConfig:
    """Priority scoring and weighting configuration"""
    activity_type_priorities: Dict[str, int] = field(default_factory=lambda: {
        'CALL': 20,
        'EMAIL': 10,
        'LINKEDIN': 5,
        'MEETING': 15,
        'TASK': 8,
        'CUSTOM': 1
    })
    
    # Sequence and priority bonuses
    sequence_step_priority_bonus: int = 5  # Points per step (11 - step_number) * 5
    callback_priority_boost: int = 50
    buying_authority_priority_boost: int = 30
    overdue_penalty_per_day: int = 15
    
    # Priority calculation weights
    weights: Dict[str, float] = field(default_factory=lambda: {
        'tier_weight': 1.0,
        'step_weight': 1.0,
        'overdue_weight': 1.5,
        'activity_type_weight': 0.5,
        'callback_weight': 2.0
    })


@dataclass(frozen=True)
class TimeConfig:
    """Time and scheduling configuration"""
    # Working days (0 = Monday, 6 = Sunday)
    working_days_start: int = 0  # Monday
    working_days_end: int = 4    # Friday
    
    # Default times
    default_call_start_hour: int = 9     # 9 AM
    default_email_start_hour: int = 10   # 10 AM
    default_meeting_start_hour: int = 10 # 10 AM
    default_call_duration_minutes: int = 30
    
    # Date formats
    input_date_format: str = '%Y-%m-%d'
    input_datetime_format: str = '%Y-%m-%d %H:%M:%S'
    display_date_format: str = '%B %d, %Y'
    display_datetime_format: str = '%B %d, %Y at %I:%M %p'


@dataclass(frozen=True)
class ValidationConfig:
    """Business rules and validation configuration"""
    # Campaign states
    forbidden_states: List[str] = field(default_factory=lambda: ['COMPLETED', 'CANCELLED'])
    modifiable_states: List[str] = field(default_factory=lambda: ['DRAFT', 'ACTIVE', 'PAUSED'])
    final_states: List[str] = field(default_factory=lambda: ['COMPLETED', 'CANCELLED'])
    
    # Status choices
    campaign_statuses: List[tuple] = field(default_factory=lambda: [
        ('DRAFT', 'Draft'),
        ('ACTIVE', 'Active'),
        ('PAUSED', 'Paused'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
    ])
    
    # Activity results
    call_results: List[str] = field(default_factory=lambda: [
        'NO_ANSWER', 'INVALID_PHONE_NUMBER', 'NOT_RIGHT_CONTACT',
        'CALLBACK_REQUESTED', 'CONTACT_NOT_AVAILABLE', 'NOT_INTERESTED', 'SUCCESSFUL'
    ])
    
    email_linkedin_results: List[str] = field(default_factory=lambda: [
        'SENT', 'DELIVERED', 'OPENED', 'CLICKED', 'BOUNCED',
        'NO_RESPONSE', 'POSITIVE_RESPONSE', 'UNSUBSCRIBE_OPTOUT', 'WRONG_EMAIL'
    ])
    
    # Sequence settings
    regeneration_continue_from_next_step: bool = True
    
    # Enhancement fields for future use
    contact_validation_fields: List[str] = field(default_factory=lambda: [
        'email_is_valid', 'phone_is_valid', 'opted_out'
    ])
    
    account_enhancement_fields: List[str] = field(default_factory=lambda: ['tier'])

    # Integrity checks
    integrity_warning_threshold: float = 90.0
    integrity_critical_threshold: float = 50.0

@dataclass(frozen=True)
class FieldConfig:
    """Field name constants to avoid magic strings"""
    # Core entities
    campaign_id: str = 'campaign_id'
    campaign: str = 'campaign'
    contact_id: str = 'contact_id'
    contact: str = 'contact'
    account_id: str = 'account_id'
    account: str = 'account'
    lead_id: str = 'lead_id'
    lead: str = 'lead'
    opportunity_id: str = 'opportunity_id'
    target_opportunity: str = 'target_opportunity'
    
    # User and role fields
    user_id: str = 'user_id'
    user: str = 'user'
    role: str = 'role'
    status: str = 'status'
    notes: str = 'notes'
    value: str = 'value'
    result: str = 'result'
    
    # Timestamp fields
    added_at: str = 'added_at'
    added_by: str = 'added_by'
    created_at: str = 'created_at'
    updated_at: str = 'updated_at'
    created_by: str = 'created_by'
    updated_by: str = 'updated_by'
    
    # Display fields
    added_by_name: str = 'added_by_name'
    user_name: str = 'user_name'
    role_display: str = 'role_display'
    campaign_name: str = 'campaign_name'
    target_type: str = 'target_type'
    target_name: str = 'target_name'
    target_details: str = 'target_details'
    status_display: str = 'status_display'
    
    # Special fields
    activities_generated: str = 'activities_generated'
    callback_date: str = 'callback_date'
    no_answer_count: str = 'no_answer_count'
    linked_opportunity: str = 'linked_opportunity'


@dataclass(frozen=True)
class QueryConfig:
    """Query parameter constants"""
    limit: str = 'limit'
    my_campaigns: str = 'my_campaigns'
    campaign_ids: str = 'campaign_ids'
    campaign_id: str = 'campaign_id'
    account_id: str = 'account_id'
    contact_id: str = 'contact_id'
    status: str = 'status'
    owner: str = 'owner'
    stakeholder_role: str = 'stakeholder_role'
    start_after: str = 'start_after'
    start_before: str = 'start_before'


@dataclass(frozen=True)
class URLConfig:
    """URL pattern constants"""
    add_manual_activity: str = 'add-manual-activity'
    bulk_add: str = 'bulk-add'
    bulk_remove: str = 'bulk-remove'
    bulk_create: str = 'bulk-create'
    update_progress: str = 'update-progress'
    update_status: str = 'update-status'


@dataclass(frozen=True)
class SerializerConfig:
    """Serializer field configuration"""
    # Campaign fields
    campaign_fields: List[str] = field(default_factory=lambda: [
        'id', 'name', 'description', 'campaign_type', 'campaign_type_display',
        'sequence_type', 'sequence_type_display', 'has_sequence', 'is_call_list',
        'owner', 'owner_name', 'stakeholders', 'start_date', 'end_date', 'objective', 'objectives',
        'status', 'status_display', 'target_summary', 'has_mixed_targets',
        'created_at', 'updated_at', 'created_by', 'updated_by', 'result_tracking',
        'quick_metrics', 'target_summary'
    ])
    
    campaign_read_only_fields: List[str] = field(default_factory=lambda: [
        'owner_name', 'campaign_type_display', 'sequence_type_display',
        'status_display', 'has_sequence', 'is_call_list', 'target_summary',
        'has_mixed_targets', 'created_at', 'updated_at', 'created_by', 'updated_by'
    ])
    
    # Objective fields
    objective_fields: List[str] = field(default_factory=lambda: [
        'id', 'campaign_id', 'name', 'objective_type',
        'objective_type_display', 'target_value', 'current_value', 'unit',
        'is_primary', 'progress_percentage', 'last_updated', 'created_at', 'updated_at'
    ])

    objective_read_only_fields: List[str] = field(default_factory=lambda: [
        'id', 'created_at', 'updated_at', 'current_value', 'progress_percentage', 'objective_type_display'
    ])
    
    # Target fields
    target_fields: List[str] = field(default_factory=lambda: [
        'id', 'campaign', 'campaign_id', 'account', 'contact', 'lead',
        'target_opportunity', 'account_id', 'contact_id', 'lead_id',
        'target_opportunity_id', 'target_type', 'target_name', 'target_details',
        'status', 'status_display', 'activities_generated', 'callback_date',
        'no_answer_count', 'notes', 'linked_opportunity', 'created_at', 'updated_at'
    ])
    
    target_read_only_fields: List[str] = field(default_factory=lambda: [
        'target_type', 'target_name', 'target_details', 'status_display',
        'created_at', 'updated_at'
    ])
    
    target_list_fields: List[str] = field(default_factory=lambda: [
        'id', 'campaign', 'campaign_name', 'target_type', 'target_name',
        'status', 'status_display', 'activities_generated', 'created_at'
    ])
    
    # Stakeholder fields
    stakeholder_fields: List[str] = field(default_factory=lambda: [
        'id', 'campaign', 'campaign_name', 'user', 'user_name',
        'role', 'role_display', 'added_at', 'added_by', 'added_by_name'
    ])
    
    stakeholder_read_only_fields: List[str] = field(default_factory=lambda: [
        'added_at', 'added_by_name', 'user_name', 'role_display', 'campaign_name'
    ])

    # Result tracking fields

    result_tracking_fields: List[str] = field(default_factory=lambda: [
        'id', 'campaign', 'campaign_name',
        'leads_created_count', 'meetings_secured_count', 
        'opportunities_created_count', 'deals_closed_count',
        'pipeline_value_created', 'revenue_generated',
        'pipeline_value_formatted', 'revenue_formatted',
        'tracked_lead_ids', 'tracked_meeting_ids',
        'tracked_opportunity_ids', 'tracked_deal_ids',
        'last_updated', 'total_tracked_objects',
        'conversion_rates', 'integrity_score',
        'tracked_objects_summary'
    ])

    result_tracking_read_only_fields: List[str] = field(default_factory=lambda: [
        'id', 'leads_created_count', 'meetings_secured_count',
        'opportunities_created_count', 'deals_closed_count',
        'pipeline_value_created', 'revenue_generated',
        'tracked_lead_ids', 'tracked_meeting_ids',
        'tracked_opportunity_ids', 'tracked_deal_ids',
        'last_updated'
    ])

    result_tracking_list_fields: List[str] = field(default_factory=lambda: [
        'id', 'campaign', 'campaign_name',
        'leads_created_count', 'meetings_secured_count',
        'opportunities_created_count', 'deals_closed_count',
        'pipeline_value_formatted', 'revenue_formatted',
        'last_updated', 'integrity_score'
    ])


@dataclass(frozen=True)
class FilterConfig:
    """Filter and ordering configuration"""
    # Filter configurations
    campaign_filters: List[str] = field(default_factory=lambda: [
        'campaign_type', 'owner', 'status', 'sequence_type'
    ])
    objective_filters: List[str] = field(default_factory=lambda: [
        'campaign', 'objective_type', 'is_primary'
    ])
    target_filters: List[str] = field(default_factory=lambda: [
        'campaign', 'status', 'activities_generated'
    ])
    stakeholder_filters: List[str] = field(default_factory=lambda: [
        'campaign', 'user', 'role'
    ])
    
    # Ordering configurations
    campaign_ordering: List[str] = field(default_factory=lambda: [
        'name', 'start_date', 'end_date', 'created_at'
    ])
    objective_ordering: List[str] = field(default_factory=lambda: [
        'name', 'target_value', 'current_value', 'created_at'
    ])
    target_ordering: List[str] = field(default_factory=lambda: [
        'created_at', 'updated_at'
    ])
    stakeholder_ordering: List[str] = field(default_factory=lambda: [
        'added_at', 'role'
    ])
    
    # Default orderings
    default_campaign_ordering: List[str] = field(default_factory=lambda: ['-created_at'])
    default_objective_ordering: List[str] = field(default_factory=lambda: ['campaign', '-is_primary', 'created_at'])
    default_target_ordering: List[str] = field(default_factory=lambda: ['campaign', 'created_at'])
    default_stakeholder_ordering: List[str] = field(default_factory=lambda: ['campaign', 'role', 'added_at'])
    
    # Search configurations
    campaign_search: List[str] = field(default_factory=lambda: ['name', 'description'])
    target_search: List[str] = field(default_factory=lambda: ['account__company_name', 'notes'])
    stakeholder_search: List[str] = field(default_factory=lambda: [
        'user__first_name', 'user__last_name', 'user__username'
    ])


@dataclass(frozen=True)
class MessageConfig:
    """Message templates and operation messages"""
    # Operation messages
    campaign_created: str = 'Campaign "{name}" created successfully with {targets} targets'
    campaign_started: str = 'Campaign "{name}" started successfully'
    campaign_paused: str = 'Campaign "{name}" paused successfully'
    campaign_resumed: str = 'Campaign "{name}" resumed successfully'
    activity_completed: str = 'Activity completed successfully'
    bulk_operation_completed: str = 'Bulk operation completed: {successful}/{total} successful'
    contact_removed: str = 'Contact removed from campaign successfully'
    account_removed: str = 'Account removed from campaign successfully'


@dataclass(frozen=True)
class PermissionConfig:
    """Permission constants"""
    view_campaign: str = 'campaign.view_campaign'
    add_campaign: str = 'campaign.add_campaign'
    change_campaign: str = 'campaign.change_campaign'
    delete_campaign: str = 'campaign.delete_campaign'
    view_objective: str = 'campaign.view_campaignobjective'
    change_objective: str = 'campaign.change_campaignobjective'
    view_target: str = 'campaign.view_campaigntarget'
    change_target: str = 'campaign.change_campaigntarget'


@dataclass(frozen=True)
class CampaignConfig:
    """
    Centralized campaign configuration
    Replaces apps/campaign/config/variables.py with type-safe structure
    """
    
    # Configuration domains
    tiers: TierConfig = field(default_factory=TierConfig)
    limits: LimitsConfig = field(default_factory=LimitsConfig)
    priorities: PriorityConfig = field(default_factory=PriorityConfig)
    time: TimeConfig = field(default_factory=TimeConfig)
    validation: ValidationConfig = field(default_factory=ValidationConfig)
    fields: FieldConfig = field(default_factory=FieldConfig)
    queries: QueryConfig = field(default_factory=QueryConfig)
    urls: URLConfig = field(default_factory=URLConfig)
    serializers: SerializerConfig = field(default_factory=SerializerConfig)
    filters: FilterConfig = field(default_factory=FilterConfig)
    messages: MessageConfig = field(default_factory=MessageConfig)
    permissions: PermissionConfig = field(default_factory=PermissionConfig)


# =========================================================================
# SINGLETON INSTANCE - Ready to use throughout the application
# =========================================================================

# Create the main configuration instance
CONFIG = CampaignConfig()

# =========================================================================
# BACKWARD COMPATIBILITY - Maintain existing imports during migration
# =========================================================================

# Re-export key constants for backward compatibility
TIER_MAX_ATTEMPTS = CONFIG.tiers.max_attempts
TIER_PRIORITY_SCORES = CONFIG.tiers.priority_scores
DEFAULT_PLAYLIST_LIMIT = CONFIG.limits.playlist_limit
QUERY_PARAMS = {
    'LIMIT': CONFIG.queries.limit,
    'MY_CAMPAIGNS': CONFIG.queries.my_campaigns,
    'CAMPAIGN_IDS': CONFIG.queries.campaign_ids,
    'CAMPAIGN_ID': CONFIG.queries.campaign_id,
    'ACCOUNT_ID': CONFIG.queries.account_id,
    'CONTACT_ID': CONFIG.queries.contact_id,
    'STATUS': CONFIG.queries.status,
    'OWNER': CONFIG.queries.owner,
    'STAKEHOLDER_ROLE': CONFIG.queries.stakeholder_role,
    'START_AFTER': CONFIG.queries.start_after,
    'START_BEFORE': CONFIG.queries.start_before,
}
FIELD_NAMES = {
    'CAMPAIGN_ID': CONFIG.fields.campaign_id,
    'CAMPAIGN': CONFIG.fields.campaign,
    'CONTACT_ID': CONFIG.fields.contact_id,
    'CONTACT': CONFIG.fields.contact,
    'ACCOUNT_ID': CONFIG.fields.account_id,
    'ACCOUNT': CONFIG.fields.account,
    'LEAD_ID': CONFIG.fields.lead_id,
    'LEAD': CONFIG.fields.lead,
    'OPPORTUNITY_ID': CONFIG.fields.opportunity_id,
    'TARGET_OPPORTUNITY': CONFIG.fields.target_opportunity,
    'USER_ID': CONFIG.fields.user_id,
    'USER': CONFIG.fields.user,
    'ROLE': CONFIG.fields.role,
    'STATUS': CONFIG.fields.status,
    'NOTES': CONFIG.fields.notes,
    'VALUE': CONFIG.fields.value,
    'RESULT': CONFIG.fields.result,
}
CALL_RESULTS = CONFIG.validation.call_results
EMAIL_LINKEDIN_RESULTS = CONFIG.validation.email_linkedin_results
OPERATION_MESSAGES = {
    'CAMPAIGN_CREATED': CONFIG.messages.campaign_created,
    'CAMPAIGN_STARTED': CONFIG.messages.campaign_started,
    'CAMPAIGN_PAUSED': CONFIG.messages.campaign_paused,
    'CAMPAIGN_RESUMED': CONFIG.messages.campaign_resumed,
    'ACTIVITY_COMPLETED': CONFIG.messages.activity_completed,
    'BULK_OPERATION_COMPLETED': CONFIG.messages.bulk_operation_completed,
    'CONTACT_REMOVED': CONFIG.messages.contact_removed,
    'ACCOUNT_REMOVED': CONFIG.messages.account_removed,
}
FILTER_CONFIGS = {
    'CAMPAIGN_FILTERS': CONFIG.filters.campaign_filters,
    'OBJECTIVE_FILTERS': CONFIG.filters.objective_filters,
    'TARGET_FILTERS': CONFIG.filters.target_filters,
    'STAKEHOLDER_FILTERS': CONFIG.filters.stakeholder_filters,
}
SEARCH_CONFIGS = {
    'CAMPAIGN_SEARCH': CONFIG.filters.campaign_search,
    'TARGET_SEARCH': CONFIG.filters.target_search,
    'STAKEHOLDER_SEARCH': CONFIG.filters.stakeholder_search,
}
ORDERING_CONFIGS = {
    'CAMPAIGN_ORDERING': CONFIG.filters.campaign_ordering,
    'OBJECTIVE_ORDERING': CONFIG.filters.objective_ordering,
    'TARGET_ORDERING': CONFIG.filters.target_ordering,
    'STAKEHOLDER_ORDERING': CONFIG.filters.stakeholder_ordering,
}
DEFAULT_ORDERINGS = {
    'CAMPAIGNS': CONFIG.filters.default_campaign_ordering,
    'OBJECTIVES': CONFIG.filters.default_objective_ordering,
    'TARGETS': CONFIG.filters.default_target_ordering,
    'STAKEHOLDERS': CONFIG.filters.default_stakeholder_ordering,
}
DATE_FORMATS = {
    'INPUT_DATE': CONFIG.time.input_date_format,
    'INPUT_DATETIME': CONFIG.time.input_datetime_format,
    'DISPLAY_DATE': CONFIG.time.display_date_format,
    'DISPLAY_DATETIME': CONFIG.time.display_datetime_format,
}
VALIDATION_LIMITS = {
    'MAX_CAMPAIGN_NAME_LENGTH': CONFIG.limits.max_campaign_name_length,
    'MAX_DESCRIPTION_LENGTH': CONFIG.limits.max_description_length,
    'MAX_NOTES_LENGTH': CONFIG.limits.max_notes_length,
    'MAX_BULK_ITEMS': CONFIG.limits.max_bulk_items,
    'MAX_TARGETS_PER_CAMPAIGN': CONFIG.limits.max_targets_per_campaign,
    'MIN_TARGET_VALUE': CONFIG.limits.min_target_value,
    'MAX_TARGET_VALUE': CONFIG.limits.max_target_value,
}


# =========================================================================
# MODERN USAGE EXAMPLES
# =========================================================================

"""
MODERN USAGE (recommended for new code):

from apps.campaign.config.settings import CONFIG

# Type-safe access with autocomplete
max_attempts = CONFIG.tiers.max_attempts['A']
playlist_limit = CONFIG.limits.playlist_limit  
campaign_fields = CONFIG.serializers.campaign_fields
priority_boost = CONFIG.priorities.callback_priority_boost

# Organized by domain
if campaign.status in CONFIG.validation.forbidden_states:
    raise ValidationError("Cannot modify completed campaign")

# Clean field access
activity_data = {
    CONFIG.fields.campaign_id: campaign.id,
    CONFIG.fields.contact_id: contact.id,
    CONFIG.fields.result: result_value
}

LEGACY USAGE (still supported during migration):

from apps.campaign.config.settings import TIER_MAX_ATTEMPTS, FIELD_NAMES

# Old style still works
max_attempts = TIER_MAX_ATTEMPTS['A']
field_name = FIELD_NAMES['CAMPAIGN_ID']
"""