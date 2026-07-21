# app_modules/campaigns/views/__init__.py
"""
Campaign module views.

Exports:
    - CampaignViewSet: CRUD + lifecycle + dashboard
    - CampaignAccountViewSet: Account enrollment CRUD + status actions
    - CampaignObjectiveViewSet: Objective management CRUD
"""

from .campaign_views import CampaignViewSet
from .campaign_bulk_views import CampaignBulkViewSet
from .campaign_account_views import CampaignAccountViewSet
from .campaign_contact_views import CampaignContactViewSet
from .campaign_objective_views import CampaignObjectiveViewSet

__all__ = [
    'CampaignViewSet',
    'CampaignBulkViewSet',
    'CampaignAccountViewSet',
    'CampaignContactViewSet',
    'CampaignObjectiveViewSet',
]