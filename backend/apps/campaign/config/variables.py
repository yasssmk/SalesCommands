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

# ACTIVITY TYPE PRIORITIES
ACTIVITY_TYPE_PRIORITIES = {
    'CALL': 20,
    'EMAIL': 10,
    'LINKEDIN': 5
}

# SEQUENCE SETTINGS
SEQUENCE_STEP_PRIORITY_BONUS = 5  # Points per step (11 - step_number) * 5
CALLBACK_PRIORITY_BOOST = 50
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

# CAMPAIGN STATUS CHOICES
CAMPAIGN_STATUSES = [
    ('DRAFT', 'Draft'),
    ('ACTIVE', 'Active'),
    ('PAUSED', 'Paused'),
    ('COMPLETED', 'Completed'),
]

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
    'EMAIL_SENT',
    'LINKEDIN_SENT',
    'EMAIL_BOUNCED',
    'LINKEDIN_CONNECTION_REJECTED',
    'POSITIVE_RESPONSE',
    'NEGATIVE_RESPONSE',
    'UNSUBSCRIBE_OPTOUT',
    'WRONG_EMAIL'
]

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