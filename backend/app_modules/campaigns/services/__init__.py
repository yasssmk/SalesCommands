# app_modules/campaigns/services/__init__.py
"""
Campaign module services.

Exports:
    - CampaignCreationService: Atomic campaign creation with nested entities
    - CampaignLifecycleService: State machine transitions (start, pause, resume, complete, cancel)
    - CampaignExecutionService: Activity generation and queue management
    - CampaignAnalyticsService: Dashboard KPIs, objective progress, conversion rates
"""

from .campaign_creation_service import CampaignCreationService
from .campaign_lifecycle_service import CampaignLifecycleService
from .campaign_execution_service import CampaignExecutionService
from .campaign_analytics_service import CampaignAnalyticsService

__all__ = [
    'CampaignCreationService',
    'CampaignLifecycleService',
    'CampaignExecutionService',
    'CampaignAnalyticsService',
]