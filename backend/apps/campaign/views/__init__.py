# apps/campaign/views/__init__.py

"""
Campaign Views Module

This module contains all the standardized ViewSets for the campaign application.
All ViewSets return standardized Response objects and use consistent error handling
with StandardizedValidationError and standardized success/error messages.

ViewSet Architecture:
- Management ViewSets: Handle complex business operations
- CRUD ViewSets: Handle standard model operations  
- All ViewSets use CampaignManager for business logic
- Consistent error handling and response formatting
"""

# Management ViewSets (Complex Operations)
from .campaign_management_views import (
    CampaignManagementViewSet,
    ActivityResultViewSet
)

# Standard CRUD ViewSets
from .campaign_views import CampaignViewSet
from .campaign_objective_views import CampaignObjectiveViewSet
from .campaign_stakeholder_views import CampaignStakeholderViewSet
from .campaign_target_views import CampaignTargetViewSet

__all__ = [
    # Management ViewSets (Primary Interfaces)
    'CampaignManagementViewSet',
    'ActivityResultViewSet',
    
    # Standard CRUD ViewSets
    'CampaignViewSet',
    'CampaignObjectiveViewSet',
    'CampaignStakeholderViewSet', 
    'CampaignTargetViewSet',
]

# ViewSet groups for organized imports
MANAGEMENT_VIEWSETS = [
    'CampaignManagementViewSet',
    'ActivityResultViewSet'
]

CRUD_VIEWSETS = [
    'CampaignViewSet',
    'CampaignObjectiveViewSet',
    'CampaignStakeholderViewSet',
    'CampaignTargetViewSet'
]

# ViewSet functionality mapping
VIEWSET_CAPABILITIES = {
    # Management ViewSets (Complex Business Operations)
    'CampaignManagementViewSet': [
        'create_with_targets',
        'start_campaign', 
        'pause_campaign',
        'resume_campaign',
        'playlist',
        'summary',
        'remove_account',
        'remove_contact',
        'activities',
        'add_manual_activity'
    ],
    'ActivityResultViewSet': [
        'complete_activity',
        'add_email_response'
    ],
    
    # Standard CRUD ViewSets
    'CampaignViewSet': [
        'list', 'create', 'retrieve', 'update', 'destroy',
        'summary'
    ],
    'CampaignObjectiveViewSet': [
        'list', 'create', 'retrieve', 'update', 'destroy',
        'update_progress'
    ],
    'CampaignStakeholderViewSet': [
        'list', 'create', 'retrieve', 'update', 'destroy',
        'bulk_add', 'bulk_remove'
    ],
    'CampaignTargetViewSet': [
        'list', 'create', 'retrieve', 'update', 'destroy',
        'update_status', 'bulk_create'
    ]
}

# URL patterns mapping
URL_PATTERNS = {
    'management': 'campaign_management_views',
    'basic': 'campaign_views',
    'objectives': 'campaign_objective_views',
    'stakeholders': 'campaign_stakeholder_views',
    'targets': 'campaign_target_views'
}

# Version info for the views module
__version__ = '1.0.0'
__author__ = 'Campaign Team'
__description__ = 'Standardized campaign ViewSets with Response objects and robust error handling'