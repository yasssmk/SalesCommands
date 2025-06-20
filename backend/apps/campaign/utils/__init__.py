# apps/campaign/utils/__init__.py

"""
Campaign Utils Module

This module contains utility classes and functions for the campaign application.
Includes standardized response builders and message constants for consistent
API responses and error handling.
"""

# Standardized Response Utilities
from .standardized_responses import (
    CampaignSuccessMessages,
    StandardizedSuccessResponse, 
    CampaignResponseBuilder
)
from .query_optimizer import CampaignQueryOptimizer


__all__ = [
    # Response Utilities
    'CampaignSuccessMessages',
    'StandardizedSuccessResponse',
    'CampaignResponseBuilder',
    'CampaignQueryOptimizer'
]

# Utility groups
RESPONSE_UTILITIES = [
    'CampaignSuccessMessages',
    'StandardizedSuccessResponse', 
    'CampaignResponseBuilder'
]

# Message types available
MESSAGE_TYPES = {
    'success': 'CampaignSuccessMessages',
    'responses': 'StandardizedSuccessResponse',
    'builders': 'CampaignResponseBuilder'
}

# Version info for the utils module
__version__ = '1.0.0'
__author__ = 'YS'
__description__ = 'Campaign utility functions and standardized response builders'