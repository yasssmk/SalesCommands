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

# CampaignMember serializers
from .campaign_member_serializer import (
    CampaignMemberListSerializer,
    CampaignMemberSerializer,
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

    # CampaignMember
    'CampaignMemberListSerializer',
    'CampaignMemberSerializer',

    # CampaignObjective
    'CampaignObjectiveListSerializer',
    'CampaignObjectiveSerializer',
]