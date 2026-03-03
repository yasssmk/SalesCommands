# app_modules/campaigns/views/__init__.py
"""
Campaign module views.

Exports:
    - CampaignViewSet: CRUD + lifecycle + dashboard
    - CampaignAccountViewSet: Account enrollment CRUD + status actions
    - CampaignMemberViewSet: Member management CRUD
    - CampaignObjectiveViewSet: Objective management CRUD
"""

from .campaign_views import CampaignViewSet
from .campaign_account_views import CampaignAccountViewSet
from .campaign_member_views import CampaignMemberViewSet
from .campaign_objective_views import CampaignObjectiveViewSet

__all__ = [
    'CampaignViewSet',
    'CampaignAccountViewSet',
    'CampaignMemberViewSet',
    'CampaignObjectiveViewSet',
]