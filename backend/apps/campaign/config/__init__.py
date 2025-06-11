# apps/campaign/config/__init__.py

"""
Campaign Configuration Module

This module contains configuration constants and variables used throughout
the campaign application for consistent behavior and easy maintenance.
"""

# Import all configuration variables
from .variables import (
    # Priority and scoring constants
    TIER_PRIORITY_SCORES,
    ACTIVITY_TYPE_PRIORITIES,
    OVERDUE_PENALTY_PER_DAY,
    CALLBACK_PRIORITY_BOOST,
    SEQUENCE_STEP_PRIORITY_BONUS,
    BUYING_AUTHORITY_PRIORITY_BOOST,
    
    # Tier-based configuration
    TIER_MAX_ATTEMPTS,
    
    # Working days configuration
    WORKING_DAYS,
    
    # Default limits
    DEFAULT_PLAYLIST_LIMIT,
)

__all__ = [
    # Priority and Scoring
    'TIER_PRIORITY_SCORES',
    'ACTIVITY_TYPE_PRIORITIES', 
    'OVERDUE_PENALTY_PER_DAY',
    'CALLBACK_PRIORITY_BOOST',
    'SEQUENCE_STEP_PRIORITY_BONUS',
    'BUYING_AUTHORITY_PRIORITY_BOOST',
    
    # Tier Configuration
    'TIER_MAX_ATTEMPTS',
    
    # Time Configuration  
    'WORKING_DAYS',
    
    # Limits
    'DEFAULT_PLAYLIST_LIMIT',
]

# Configuration groups for easy access
PRIORITY_CONFIG = [
    'TIER_PRIORITY_SCORES',
    'ACTIVITY_TYPE_PRIORITIES',
    'OVERDUE_PENALTY_PER_DAY',
    'CALLBACK_PRIORITY_BOOST', 
    'SEQUENCE_STEP_PRIORITY_BONUS',
    'BUYING_AUTHORITY_PRIORITY_BOOST'
]

TIER_CONFIG = [
    'TIER_MAX_ATTEMPTS',
    'TIER_PRIORITY_SCORES'
]

TIME_CONFIG = [
    'WORKING_DAYS'
]

LIMIT_CONFIG = [
    'DEFAULT_PLAYLIST_LIMIT'
]

# Configuration metadata
CONFIG_INFO = {
    'priority': 'Campaign priority scoring and weighting',
    'tier': 'Account tier-based configuration',
    'time': 'Working days and time-based settings',
    'limits': 'Default limits and pagination'
}

# Version info for the config module
__version__ = '1.0.0'
__author__ = 'YS'
__description__ = 'Campaign configuration constants and variables'