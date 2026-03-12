# app_modules/campaigns/config/settings.py
"""
Campaign Module Configuration Settings.

Centralized, type-safe configuration using dataclasses.
Adapted from legacy apps/campaign/config/settings.py for new architecture:
- 2 campaign types: OUTBOUND / TARGETED (replaces 8 legacy types)
- CampaignAccount as central pivot (replaces polymorphic CampaignTarget)
- CampaignMember with 4 roles (replaces CampaignStakeholder)
- 6 objective types aligned with DecisionCycle
"""

from dataclasses import dataclass, field
from typing import Dict, List


# =========================================================================
# DOMAIN CONFIGS
# =========================================================================

@dataclass(frozen=True)
class LimitsConfig:
    """Application limits and pagination settings."""

    # Pagination
    pagination_size: int = 10
    max_pagination_size: int = 100

    # Validation limits
    max_campaign_name_length: int = 100
    max_description_length: int = 500
    max_notes_length: int = 1000

    # Campaign limits
    max_accounts_per_campaign: int = 1000
    max_members_per_campaign: int = 50
    max_objectives_per_campaign: int = 5

    # Bulk operations
    bulk_operation_limit: int = 100
    max_bulk_items: int = 50
    bulk_create_batch_size: int = 50

    # Objective value bounds
    min_target_value: float = 0.01
    max_target_value: float = 999999999.99

    # Playlist / execution
    playlist_limit: int = 20
    summary_activities: int = 5
    queue_batch_size: int = 50

    # Inactivity detection
    inactivity_threshold_days: int = 30

    # Performance
    cache_timeout_seconds: int = 300
    max_prefetch_depth: int = 3
    max_retry_attempts: int = 3
    timeout_seconds: int = 30


@dataclass(frozen=True)
class PriorityConfig:
    """Priority scoring for activity ordering in playlists."""

    activity_type_priorities: Dict[str, int] = field(default_factory=lambda: {
        'CALL': 20,
        'EMAIL': 10,
        'LINKEDIN': 5,
        'MEETING': 15,
        'TASK': 8,
        'CUSTOM': 1,
    })

    sequence_step_priority_bonus: int = 5
    callback_priority_boost: int = 50
    overdue_penalty_per_day: int = 15

    weights: Dict[str, float] = field(default_factory=lambda: {
        'step_weight': 1.0,
        'overdue_weight': 1.5,
        'activity_type_weight': 0.5,
        'callback_weight': 2.0,
    })


@dataclass(frozen=True)
class TimeConfig:
    """Time and scheduling configuration."""

    working_days_start: int = 0  # Monday
    working_days_end: int = 4    # Friday

    default_call_start_hour: int = 9
    default_email_start_hour: int = 10
    default_meeting_start_hour: int = 10
    default_call_duration_minutes: int = 30

    input_date_format: str = '%Y-%m-%d'
    input_datetime_format: str = '%Y-%m-%d %H:%M:%S'
    display_date_format: str = '%B %d, %Y'
    display_datetime_format: str = '%B %d, %Y at %I:%M %p'


@dataclass(frozen=True)
class ValidationConfig:
    """Business rules and validation constants."""

    # Campaign lifecycle states
    campaign_statuses: List[tuple] = field(default_factory=lambda: [
        ('DRAFT', 'Draft'),
        ('ACTIVE', 'Active'),
        ('PAUSED', 'Paused'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
    ])
    modifiable_states: List[str] = field(default_factory=lambda: [
        'DRAFT', 'ACTIVE', 'PAUSED',
    ])
    final_states: List[str] = field(default_factory=lambda: [
        'COMPLETED', 'CANCELLED',
    ])

    # Campaign types
    campaign_types: List[tuple] = field(default_factory=lambda: [
        ('OUTBOUND', 'Outbound Campaign'),
        ('TARGETED', 'Targeted Campaign'),
    ])

    # CampaignAccount status (state machine)
    campaign_account_statuses: List[tuple] = field(default_factory=lambda: [
        ('PENDING', 'Pending'),
        ('IN_PROGRESS', 'In Progress'),
        ('CALLBACK_PENDING', 'Callback Pending'),
        ('COMPLETED', 'Completed'),
        ('STOPPED', 'Stopped'),
    ])
    campaign_account_final_states: List[str] = field(default_factory=lambda: [
        'COMPLETED', 'STOPPED',
    ])

    # Valid state transitions for CampaignAccount
    campaign_account_transitions: Dict[str, List[str]] = field(default_factory=lambda: {
        'PENDING': ['IN_PROGRESS', 'STOPPED'],
        'IN_PROGRESS': ['CALLBACK_PENDING', 'COMPLETED', 'STOPPED'],
        'CALLBACK_PENDING': ['IN_PROGRESS', 'COMPLETED', 'STOPPED'],
        'COMPLETED': [],
        'STOPPED': [],
    })

    # CampaignMember roles
    member_roles: List[tuple] = field(default_factory=lambda: [
        ('OWNER', 'Campaign Owner'),
        ('EXECUTOR', 'Executor'),
        ('RECEIVER', 'Receiver'),
        ('OBSERVER', 'Observer'),
    ])

    # Objective types (aligned with DecisionCycle)
    objective_types: List[tuple] = field(default_factory=lambda: [
        ('MEETINGS', 'Number of Meetings'),
        ('DECISION_CYCLES', 'Decision Cycles Opened'),
        ('CONTACTS_REACHED', 'Contacts Reached'),
        ('PIPELINE_VALUE', 'Pipeline Value'),
        ('REVENUE_WON', 'Revenue Won'),
        ('NEW_LOGOS', 'New Logos'),
    ])

    # Activity results
    call_results: List[str] = field(default_factory=lambda: [
        'NO_ANSWER', 'INVALID_PHONE_NUMBER', 'NOT_RIGHT_CONTACT',
        'CALLBACK_REQUESTED', 'CONTACT_NOT_AVAILABLE', 'NOT_INTERESTED', 'SUCCESSFUL',
    ])
    email_linkedin_results: List[str] = field(default_factory=lambda: [
        'SENT', 'DELIVERED', 'OPENED', 'CLICKED', 'BOUNCED',
        'NO_RESPONSE', 'POSITIVE_RESPONSE', 'UNSUBSCRIBE_OPTOUT', 'WRONG_EMAIL',
    ])

    # Sequence settings
    regeneration_continue_from_next_step: bool = True


@dataclass(frozen=True)
class FieldConfig:
    """Field name constants to avoid magic strings."""

    # Core entities
    campaign_id: str = 'campaign_id'
    campaign: str = 'campaign'
    account_id: str = 'account_id'
    account: str = 'account'
    contact_id: str = 'contact_id'
    contact: str = 'contact'
    territory_ids: str = 'territory_ids'
    territories: str = 'territories'

    # User and role
    user_id: str = 'user_id'
    user: str = 'user'
    role: str = 'role'
    status: str = 'status'
    notes: str = 'notes'

    # Timestamps
    created_at: str = 'created_at'
    updated_at: str = 'updated_at'
    created_by: str = 'created_by'
    updated_by: str = 'updated_by'

    # Display fields
    campaign_name: str = 'campaign_name'
    status_display: str = 'status_display'
    user_name: str = 'user_name'
    role_display: str = 'role_display'

    # CampaignAccount specific
    callback_date: str = 'callback_date'
    activities_generated: str = 'activities_generated'
    sequence_position: str = 'sequence_position'


@dataclass(frozen=True)
class QueryConfig:
    """Query parameter constants."""

    limit: str = 'limit'
    campaign_id: str = 'campaign_id'
    account_id: str = 'account_id'
    territory_id: str = 'territory_id'
    status: str = 'status'
    campaign_type: str = 'campaign_type'
    owner: str = 'owner'
    member_role: str = 'member_role'
    start_after: str = 'start_after'
    start_before: str = 'start_before'
    my_campaigns: str = 'my_campaigns'


@dataclass(frozen=True)
class URLConfig:
    """URL pattern constants for custom actions."""

    start: str = 'start'
    pause: str = 'pause'
    resume: str = 'resume'
    complete: str = 'complete'
    cancel: str = 'cancel'
    summary: str = 'summary'
    dashboard: str = 'dashboard'
    playlist: str = 'playlist'
    bulk_add_accounts: str = 'bulk-add-accounts'
    bulk_remove_accounts: str = 'bulk-remove-accounts'


@dataclass(frozen=True)
class SerializerConfig:
    """Serializer field configuration."""

    # Campaign fields
    campaign_fields: List[str] = field(default_factory=lambda: [
        'id', 'name', 'description', 'campaign_type', 'campaign_type_display',
        'sequence_type', 'sequence_type_display', 'has_sequence',
        'territories', 'territory_name',
        'status', 'status_display',
        'start_date', 'end_date',
        'accounts_count', 'members_summary', 'primary_objective',
        'created_at', 'updated_at', 'created_by', 'updated_by',
    ])
    campaign_read_only_fields: List[str] = field(default_factory=lambda: [
        'id', 'campaign_type_display', 'sequence_type_display', 'has_sequence',
        'territory_name', 'status_display',
        'accounts_count', 'members_summary', 'primary_objective',
        'created_at', 'updated_at', 'created_by', 'updated_by',
    ])

    # CampaignAccount fields
    campaign_account_fields: List[str] = field(default_factory=lambda: [
        'id', 'campaign', 'campaign_name',
        'account', 'account_name',
        'status', 'status_display',
        'notes', 'callback_date', 'activities_generated',
        'target_departments', 'target_contacts',
        'created_at', 'updated_at',
    ])
    campaign_account_read_only_fields: List[str] = field(default_factory=lambda: [
        'id', 'campaign_name', 'account_name', 'status_display',
        'activities_generated', 'created_at', 'updated_at',
    ])

    # CampaignMember fields
    member_fields: List[str] = field(default_factory=lambda: [
        'id', 'campaign', 'campaign_name',
        'user', 'user_name',
        'role', 'role_display',
        'is_primary_owner',
        'added_at', 'added_by', 'added_by_name',
    ])
    member_read_only_fields: List[str] = field(default_factory=lambda: [
        'id', 'campaign_name', 'user_name', 'role_display',
        'added_at', 'added_by_name',
    ])

    # Objective fields
    objective_fields: List[str] = field(default_factory=lambda: [
        'id', 'campaign', 'campaign_name',
        'name', 'objective_type', 'objective_type_display',
        'target_value', 'current_value', 'progress_percentage',
        'is_primary',
        'created_at', 'updated_at',
    ])
    objective_read_only_fields: List[str] = field(default_factory=lambda: [
        'id', 'campaign_name', 'objective_type_display',
        'current_value', 'progress_percentage',
        'created_at', 'updated_at',
    ])


@dataclass(frozen=True)
class FilterConfig:
    """Filter and ordering configuration."""

    # Filter fields
    campaign_filters: List[str] = field(default_factory=lambda: [
        'status', 'campaign_type', 'sequence_type', 'territories',
    ])
    campaign_account_filters: List[str] = field(default_factory=lambda: [
        'campaign', 'account', 'status', 'activities_generated',
    ])
    member_filters: List[str] = field(default_factory=lambda: [
        'campaign', 'user', 'role',
    ])
    objective_filters: List[str] = field(default_factory=lambda: [
        'campaign', 'objective_type', 'is_primary',
    ])

    # Default orderings
    default_campaign_ordering: List[str] = field(default_factory=lambda: ['-created_at'])
    default_campaign_account_ordering: List[str] = field(default_factory=lambda: ['campaign', 'created_at'])
    default_member_ordering: List[str] = field(default_factory=lambda: ['campaign', 'role', 'added_at'])
    default_objective_ordering: List[str] = field(default_factory=lambda: ['campaign', '-is_primary', 'created_at'])

    # Search fields
    campaign_search: List[str] = field(default_factory=lambda: ['name', 'description'])
    campaign_account_search: List[str] = field(default_factory=lambda: ['account__company_name', 'notes'])
    member_search: List[str] = field(default_factory=lambda: [
        'user__first_name', 'user__last_name', 'user__email',
    ])


@dataclass(frozen=True)
class MessageConfig:
    """Message templates for operations."""

    campaign_created: str = 'Campaign "{name}" created successfully'
    campaign_started: str = 'Campaign "{name}" started successfully'
    campaign_paused: str = 'Campaign "{name}" paused successfully'
    campaign_resumed: str = 'Campaign "{name}" resumed successfully'
    campaign_completed: str = 'Campaign "{name}" completed successfully'
    campaign_cancelled: str = 'Campaign "{name}" cancelled successfully'
    account_added: str = 'Account added to campaign successfully'
    account_removed: str = 'Account removed from campaign successfully'
    member_added: str = 'Member added to campaign successfully'
    member_removed: str = 'Member removed from campaign successfully'
    activity_completed: str = 'Activity completed successfully'
    bulk_operation_completed: str = 'Bulk operation completed: {successful}/{total} successful'


@dataclass(frozen=True)
class PermissionConfig:
    """Permission constants."""

    view_campaign: str = 'module_campaigns.view_campaign'
    add_campaign: str = 'module_campaigns.add_campaign'
    change_campaign: str = 'module_campaigns.change_campaign'
    delete_campaign: str = 'module_campaigns.delete_campaign'
    view_campaign_account: str = 'module_campaigns.view_campaignaccount'
    change_campaign_account: str = 'module_campaigns.change_campaignaccount'
    view_member: str = 'module_campaigns.view_campaignmember'
    change_member: str = 'module_campaigns.change_campaignmember'
    view_objective: str = 'module_campaigns.view_campaignobjective'
    change_objective: str = 'module_campaigns.change_campaignobjective'


# =========================================================================
# MAIN CONFIG — SINGLETON
# =========================================================================

@dataclass(frozen=True)
class CampaignModuleConfig:
    """
    Centralized campaign module configuration.

    Usage:
        from app_modules.campaigns.config.settings import CONFIG

        if status in CONFIG.validation.final_states:
            raise ...
        limit = CONFIG.limits.max_accounts_per_campaign
    """

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


CONFIG = CampaignModuleConfig()