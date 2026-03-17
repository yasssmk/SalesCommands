# app_modules/campaigns/serializers/__init__.py
"""
Campaign module serializers.

Exports all serializers for Campaign, CampaignAccount, CampaignMember, CampaignObjective.
"""

# Campaign serializers
from .campaign_serializer import (
    CampaignListSerializer,
    CampaignDetailSerializer,
    CampaignCreateSerializer,
    CampaignUpdateSerializer,
)

# CampaignAccount serializers
from .campaign_account_serializer import (
    CampaignAccountListSerializer,
    CampaignAccountDetailSerializer,
    CampaignAccountSerializer,
)

from .campaign_contact_serializer import (
    CampaignContactListSerializer,
    CampaignContactDetailSerializer,
    CampaignContactSerializer,
)
# CampaignObjective serializers
from .campaign_objective_serializer import (
    CampaignObjectiveListSerializer,
    CampaignObjectiveSerializer,
)

__all__ = [
    # Campaign
    'CampaignListSerializer',
    'CampaignDetailSerializer',
    'CampaignCreateSerializer',
    'CampaignUpdateSerializer',
    # CampaignAccount
    'CampaignAccountListSerializer',
    'CampaignAccountDetailSerializer',
    'CampaignAccountSerializer',
    # CampaignContact
    'CampaignContactListSerializer',
    'CampaignContactDetailSerializer',
    'CampaignContactSerializer',
    # CampaignObjective
    'CampaignObjectiveListSerializer',
    'CampaignObjectiveSerializer',
]