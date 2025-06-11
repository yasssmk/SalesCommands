# apps/campaign/models/__init__.py

"""
Campaign Models Module

This module contains all the standardized models for the campaign application.
All models use StandardizedValidationError for consistent error handling.
"""

from .campaign import Campaign
from .campaign_objective import CampaignObjective
from .campaign_target import CampaignTarget
from .campaign_stakeholder import CampaignStakeholder

__all__ = [
    # Core Campaign Models
    'Campaign',
    'CampaignObjective', 
    'CampaignTarget',
    'CampaignStakeholder',
]

# Version info for the models module
__version__ = '1.0.0'
__author__ = 'YS'
__description__ = 'Standardized campaign models with robust validation and error handling'