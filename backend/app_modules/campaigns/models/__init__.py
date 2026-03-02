# app_modules/campaigns/models/__init__.py
"""
Campaign module models.

Exports:
- Campaign: Main campaign entity (OUTBOUND / TARGETED)
- CampaignAccount: Pivot linking campaign to accounts
- CampaignMember: User roles within a campaign
- CampaignObjective: Measurable campaign goals
"""

from .campaign import Campaign, CampaignType, CampaignStatus, CAMPAIGN_STATUS_TRANSITIONS
from .campaign_account import CampaignAccount, CampaignAccountStatus, CAMPAIGN_ACCOUNT_TRANSITIONS
from .campaign_member import CampaignMember
from .campaign_objective import CampaignObjective, ObjectiveType

__all__ = [
    'Campaign',
    'CampaignType',
    'CampaignStatus',
    'CAMPAIGN_STATUS_TRANSITIONS',
    'CampaignAccount',
    'CampaignAccountStatus',
    'CAMPAIGN_ACCOUNT_TRANSITIONS',
    'CampaignMember',
    'CampaignObjective',
    'ObjectiveType',
]