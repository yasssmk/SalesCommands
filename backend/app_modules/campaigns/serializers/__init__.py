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

    # CampaignContact
    'CampaignContactListSerializer',
    'CampaignContactDetailSerializer',
    'CampaignContactSerializer',

    # CampaignMember
    'CampaignMemberListSerializer',
    'CampaignMemberSerializer',

    # CampaignObjective
    'CampaignObjectiveListSerializer',
    'CampaignObjectiveSerializer',
]