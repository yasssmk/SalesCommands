# apps/campaign/serializers/__init__.py

"""
Campaign Serializers Module

This module contains all the standardized serializers for the campaign application.
All serializers use StandardizedValidationError for consistent error handling and
follow the same validation patterns with comprehensive error messages.
"""

# Campaign Serializers
from .campaign_serializer import (
    CampaignSerializer,
    CampaignListSerializer
)

# Campaign Objective Serializers
from .campaign_objective_serializer import CampaignObjectiveSerializer

# Campaign Target Serializers  
from .campaign_target_serializer import (
    CampaignTargetSerializer,
    CampaignTargetListSerializer
)

# Campaign Stakeholder Serializers
from .campaign_stakeholders_serializer import CampaignStakeholderSerializer

__all__ = [
    # Campaign Serializers
    'CampaignSerializer',
    'CampaignListSerializer',
    
    # Campaign Objective Serializers
    'CampaignObjectiveSerializer',
    
    # Campaign Target Serializers
    'CampaignTargetSerializer', 
    'CampaignTargetListSerializer',
    
    # Campaign Stakeholder Serializers
    'CampaignStakeholderSerializer',
]

# Serializer groups for easy import
CAMPAIGN_SERIALIZERS = [
    'CampaignSerializer',
    'CampaignListSerializer'
]

OBJECTIVE_SERIALIZERS = [
    'CampaignObjectiveSerializer'
]

TARGET_SERIALIZERS = [
    'CampaignTargetSerializer',
    'CampaignTargetListSerializer'
]

STAKEHOLDER_SERIALIZERS = [
    'CampaignStakeholderSerializer'
]

# Version info for the serializers module
__version__ = '1.0.0'
__author__ = 'YS'
__description__ = 'Standardized campaign serializers with robust validation and error handling'