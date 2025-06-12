# apps/campaign/config/variables.py
"""
Campaign Configuration Variables
Centralized location for all campaign-related settings and constants
"""

# TIER-BASED SETTINGS
TIER_MAX_ATTEMPTS = {
    'A': 3,  # Tier A accounts get 3 call attempts
    'B': 2,  # Tier B accounts get 2 call attempts
    'C': 1   # Tier C accounts get 1 call attempt
}

TIER_PRIORITY_SCORES = {
    'A': 100,  # Highest priority
    'B': 50,   # Medium priority
    'C': 10    # Lowest priority
}

# DEFAULT LIMITS
DEFAULT_PLAYLIST_LIMIT = 20
DEFAULT_SUMMARY_ACTIVITIES = 5
DEFAULT_QUEUE_BATCH_SIZE = 50
DEFAULT_BULK_OPERATION_LIMIT = 100
DEFAULT_PAGINATION_SIZE = 10
MAX_PAGINATION_SIZE = 100

# ACTIVITY TYPE PRIORITIES
ACTIVITY_TYPE_PRIORITIES = {
    'CALL': 20,
    'EMAIL': 10,
    'LINKEDIN': 5,
    'MEETING': 15,
    'TASK': 8,
    'CUSTOM': 1
}

# SEQUENCE SETTINGS
SEQUENCE_STEP_PRIORITY_BONUS = 5  # Points per step (11 - step_number) * 5
CALLBACK_PRIORITY_BOOST = 50
BUYING_AUTHORITY_PRIORITY_BOOST = 30  # Points for buying authority
OVERDUE_PENALTY_PER_DAY = 15  # Points per working day overdue

# WORKING DAYS
WORKING_DAYS = {
    'start': 0,  # Monday (0 = Monday, 6 = Sunday)
    'end': 4     # Friday
}

# DEFAULT TIMES
DEFAULT_CALL_START_HOUR = 9    # 9 AM
DEFAULT_EMAIL_START_HOUR = 10  # 10 AM
DEFAULT_MEETING_START_HOUR = 10  # 10 AM
DEFAULT_CALL_DURATION_MINUTES = 30

# ===== NOUVEAUX CONSTANTS POUR ÉLIMINER MAGIC STRINGS =====

# CAMPAIGN STATES
CAMPAIGN_FORBIDDEN_STATES = ['COMPLETED', 'CANCELLED']
CAMPAIGN_MODIFIABLE_STATES = ['DRAFT', 'ACTIVE', 'PAUSED']
CAMPAIGN_FINAL_STATES = ['COMPLETED', 'CANCELLED']

# CAMPAIGN STATUS CHOICES
CAMPAIGN_STATUSES = [
    ('DRAFT', 'Draft'),
    ('ACTIVE', 'Active'),
    ('PAUSED', 'Paused'),
    ('COMPLETED', 'Completed'),
    ('CANCELLED', 'Cancelled'),
]

# PERMISSIONS
CAMPAIGN_PERMISSIONS = {
    'VIEW': 'campaign.view_campaign',
    'ADD': 'campaign.add_campaign',
    'CHANGE': 'campaign.change_campaign',
    'DELETE': 'campaign.delete_campaign',
    'VIEW_OBJECTIVE': 'campaign.view_campaignobjective',
    'CHANGE_OBJECTIVE': 'campaign.change_campaignobjective',
    'VIEW_TARGET': 'campaign.view_campaigntarget',
    'CHANGE_TARGET': 'campaign.change_campaigntarget',
}

# FIELD NAMES (pour éviter la répétition de strings)
FIELD_NAMES = {
    'CAMPAIGN_ID': 'campaign_id',
    'CAMPAIGN': 'campaign',
    'CONTACT_ID': 'contact_id',
    'CONTACT': 'contact',
    'ACCOUNT_ID': 'account_id',
    'ACCOUNT': 'account',
    'LEAD_ID': 'lead_id',
    'LEAD': 'lead',
    'OPPORTUNITY_ID': 'opportunity_id',
    'TARGET_OPPORTUNITY': 'target_opportunity',
    'USER_ID': 'user_id',
    'USER': 'user',
    'ROLE': 'role',
    'STATUS': 'status',
    'NOTES': 'notes',
    'VALUE': 'value',
    'RESULT': 'result',
    'ADDED_AT': 'added_at',
    'ADDED_BY': 'added_by',
    'ADDED_BY_NAME': 'added_by_name',
    'USER_NAME': 'user_name',
    'ROLE_DISPLAY': 'role_display',
    'CAMPAIGN_NAME': 'campaign_name',
    'TARGET_TYPE': 'target_type',
    'TARGET_NAME': 'target_name',
    'TARGET_DETAILS': 'target_details',
    'STATUS_DISPLAY': 'status_display',
    'ACTIVITIES_GENERATED': 'activities_generated',
    'CALLBACK_DATE': 'callback_date',
    'NO_ANSWER_COUNT': 'no_answer_count',
    'LINKED_OPPORTUNITY': 'linked_opportunity',
    'CREATED_AT': 'created_at',
    'UPDATED_AT': 'updated_at',
    'CREATED_BY': 'created_by',
    'UPDATED_BY': 'updated_by',
}

# URL PATTERNS
URL_PATTERNS = {
    'ADD_MANUAL_ACTIVITY': 'add-manual-activity',
    'BULK_ADD': 'bulk-add',
    'BULK_REMOVE': 'bulk-remove',
    'BULK_CREATE': 'bulk-create',
    'UPDATE_PROGRESS': 'update-progress',
    'UPDATE_STATUS': 'update-status',
}

# QUERY PARAMETERS
QUERY_PARAMS = {
    'LIMIT': 'limit',
    'MY_CAMPAIGNS': 'my_campaigns',
    'CAMPAIGN_IDS': 'campaign_ids',
    'CAMPAIGN_ID': 'campaign_id',
    'ACCOUNT_ID': 'account_id',
    'CONTACT_ID': 'contact_id',
    'STATUS': 'status',
    'OWNER': 'owner',
    'STAKEHOLDER_ROLE': 'stakeholder_role',
    'START_AFTER': 'start_after',
    'START_BEFORE': 'start_before',
}

# ACTIVITY RESULT TYPES
CALL_RESULTS = [
    'NO_ANSWER',
    'INVALID_PHONE_NUMBER',
    'NOT_RIGHT_CONTACT',
    'CALLBACK_REQUESTED',
    'CONTACT_NOT_AVAILABLE',
    'NOT_INTERESTED',
    'SUCCESSFUL'
]

EMAIL_LINKEDIN_RESULTS = [
    'SENT',
    'DELIVERED',
    'OPENED',
    'CLICKED',
    'BOUNCED',
    'NO_RESPONSE',
    'POSITIVE_RESPONSE',
    'UNSUBSCRIBE_OPTOUT',
    'WRONG_EMAIL'
]

# MESSAGE TEMPLATES
OPERATION_MESSAGES = {
    'CAMPAIGN_CREATED': 'Campaign "{name}" created successfully with {targets} targets',
    'CAMPAIGN_STARTED': 'Campaign "{name}" started successfully',
    'CAMPAIGN_PAUSED': 'Campaign "{name}" paused successfully',
    'CAMPAIGN_RESUMED': 'Campaign "{name}" resumed successfully',
    'ACTIVITY_COMPLETED': 'Activity completed successfully',
    'BULK_OPERATION_COMPLETED': 'Bulk operation completed: {successful}/{total} successful',
    'CONTACT_REMOVED': 'Contact removed from campaign successfully',
    'ACCOUNT_REMOVED': 'Account removed from campaign successfully',
}

# VALIDATION CONSTANTS
VALIDATION_LIMITS = {
    'MAX_CAMPAIGN_NAME_LENGTH': 100,
    'MAX_DESCRIPTION_LENGTH': 500,
    'MAX_NOTES_LENGTH': 1000,
    'MAX_BULK_ITEMS': 50,
    'MAX_TARGETS_PER_CAMPAIGN': 1000,
    'MIN_TARGET_VALUE': 0.01,
    'MAX_TARGET_VALUE': 999999999.99,
}

# SEQUENCE REGENERATION SETTINGS
REGENERATION_CONTINUE_FROM_NEXT_STEP = True  # Start from next step after current

# CONTACT VALIDATION FIELDS (for future use)
CONTACT_VALIDATION_FIELDS = [
    'email_is_valid',
    'phone_is_valid',
    'opted_out'
]

# ACCOUNT ENHANCEMENT FIELDS (for future use)
ACCOUNT_ENHANCEMENT_FIELDS = [
    'tier'
]

# PRIORITY SCORE CALCULATION WEIGHTS
PRIORITY_WEIGHTS = {
    'tier_weight': 1.0,           # Weight for tier-based priority
    'step_weight': 1.0,           # Weight for sequence step priority
    'overdue_weight': 1.5,        # Weight for overdue penalty (higher = more important)
    'activity_type_weight': 0.5,  # Weight for activity type priority
    'callback_weight': 2.0        # Weight for callback priority boost
}

# SERIALIZER FIELD CONFIGURATIONS
SERIALIZER_CONFIGS = {
    'CAMPAIGN_FIELDS': [
        'id', 'name', 'description', 'campaign_type', 'campaign_type_display',
        'sequence_type', 'sequence_type_display', 'has_sequence', 'is_call_list',
        'owner', 'owner_name', 'stakeholders', 'start_date', 'end_date',
        'status', 'status_display', 'target_summary', 'has_mixed_targets',
        'created_at', 'updated_at', 'created_by', 'updated_by'
    ],
    'CAMPAIGN_READ_ONLY_FIELDS': [
        'owner_name', 'campaign_type_display', 'sequence_type_display',
        'status_display', 'has_sequence', 'is_call_list', 'target_summary',
        'has_mixed_targets', 'created_at', 'updated_at', 'created_by', 'updated_by'
    ],
    'OBJECTIVE_FIELDS': [
        'id', 'campaign_id', 'name', 'description', 'objective_type',
        'objective_type_display', 'target_value', 'current_value', 'unit',
        'is_primary', 'progress_percentage', 'last_updated', 'created_at', 'updated_at'
    ],
    'TARGET_FIELDS': [
        'id', 'campaign', 'campaign_id', 'account', 'contact', 'lead',
        'target_opportunity', 'account_id', 'contact_id', 'lead_id',
        'target_opportunity_id', 'target_type', 'target_name', 'target_details',
        'status', 'status_display', 'activities_generated', 'callback_date',
        'no_answer_count', 'notes', 'linked_opportunity', 'created_at', 'updated_at'
    ],
    'TARGET_READ_ONLY_FIELDS': [
        'target_type',
        'target_name',
        'target_details',
        'status_display',
        'created_at',
        'updated_at'
    ],
    'TARGET_LIST_FIELDS': [
        'id',
        'campaign',
        'campaign_name',
        'target_type',
        'target_name',
        'status',
        'status_display',
        'activities_generated',
        'created_at'
    ],
    'STAKEHOLDER_FIELDS': [
        'id', 'campaign', 'campaign_name', 'user', 'user_name',
        'role', 'role_display', 'added_at', 'added_by', 'added_by_name'
    ],
    'STAKEHOLDER_READ_ONLY_FIELDS': [
        'added_at', 'added_by_name', 'user_name', 'role_display', 'campaign_name'
    ],
}

# FILTER CONFIGURATIONS
FILTER_CONFIGS = {
    'CAMPAIGN_FILTERS': ['campaign_type', 'owner', 'status', 'sequence_type'],
    'OBJECTIVE_FILTERS': ['campaign', 'objective_type', 'is_primary'],
    'TARGET_FILTERS': ['campaign', 'status', 'activities_generated'],
    'STAKEHOLDER_FILTERS': ['campaign', 'user', 'role'],
}

# ORDERING CONFIGURATIONS
ORDERING_CONFIGS = {
    'CAMPAIGN_ORDERING': ['name', 'start_date', 'end_date', 'created_at'],
    'OBJECTIVE_ORDERING': ['name', 'target_value', 'current_value', 'created_at'],
    'TARGET_ORDERING': ['created_at', 'updated_at'],
    'STAKEHOLDER_ORDERING': ['added_at', 'role'],
}

# DEFAULT ORDERINGS
DEFAULT_ORDERINGS = {
    'CAMPAIGNS': ['-created_at'],
    'OBJECTIVES': ['campaign', '-is_primary', 'created_at'],
    'TARGETS': ['campaign', 'created_at'],
    'STAKEHOLDERS': ['campaign', 'role', 'added_at'],
}

# SEARCH CONFIGURATIONS
SEARCH_CONFIGS = {
    'CAMPAIGN_SEARCH': ['name', 'description'],
    'TARGET_SEARCH': ['account__company_name', 'notes'],
    'STAKEHOLDER_SEARCH': ['user__first_name', 'user__last_name', 'user__username'],
}

# DATE FORMAT PATTERNS
DATE_FORMATS = {
    'INPUT_DATE': '%Y-%m-%d',
    'INPUT_DATETIME': '%Y-%m-%d %H:%M:%S',
    'DISPLAY_DATE': '%B %d, %Y',
    'DISPLAY_DATETIME': '%B %d, %Y at %I:%M %p',
}

# ERROR THRESHOLD CONSTANTS
ERROR_THRESHOLDS = {
    'MAX_RETRY_ATTEMPTS': 3,
    'TIMEOUT_SECONDS': 30,
    'MAX_BULK_ERRORS': 10,
    'WARNING_THRESHOLD': 5,
}

# PERFORMANCE CONSTANTS
PERFORMANCE_LIMITS = {
    'BULK_CREATE_BATCH_SIZE': 50,
    'QUERY_BATCH_SIZE': 100,
    'MAX_PREFETCH_DEPTH': 3,
    'CACHE_TIMEOUT_SECONDS': 300,  # 5 minutes
}