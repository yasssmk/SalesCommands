# apps/campaign/services/__init__.py

"""
Campaign Services Module

This module contains all the standardized services for the campaign application.
All services return standardized Response objects and use consistent error handling
with StandardizedValidationError and standardized success/error messages.

Service Architecture:
- CampaignManager: Main orchestrator service (facade pattern)
- Specialized Services: Handle specific domain logic
- All services return Response objects with standardized format
"""

# # Main Campaign Manager (Facade)
# from .campaign_manager import CampaignManager

# # Specialized Campaign Services
# from .campaign_creation_service import CampaignCreationService
# from .campaign_execution_service import CampaignExecutionService
# from .campaign_analytics_service import CampaignAnalyticsService
# from .campaign_result_service import CampaignResultService
# from .campaign_queue_service import CampaignQueueService

# # Supporting Services
# from .campaign_activity_service import CampaignActivityService
# from .campaign_target_service import CampaignTargetService

# __all__ = [
#     # Main Manager Service (Primary Interface)
#     'CampaignManager',
    
#     # Core Campaign Services
#     'CampaignCreationService',
#     'CampaignExecutionService', 
#     'CampaignAnalyticsService',
#     'CampaignResultService',
#     'CampaignQueueService',
    
#     # Supporting Services
#     'CampaignActivityService',
#     'CampaignTargetService',
# ]

# # Service groups for organized imports
# CORE_SERVICES = [
#     'CampaignManager',
#     'CampaignCreationService',
#     'CampaignExecutionService',
#     'CampaignAnalyticsService',
#     'CampaignResultService',
#     'CampaignQueueService'
# ]

# SUPPORTING_SERVICES = [
#     'CampaignActivityService',
#     'CampaignTargetService'
# ]

# # Service workflow mapping
# SERVICE_WORKFLOW = {
#     'campaign_creation': 'CampaignCreationService',
#     'campaign_execution': 'CampaignExecutionService', 
#     'campaign_analytics': 'CampaignAnalyticsService',
#     'campaign_results': 'CampaignResultService',
#     'campaign_queue': 'CampaignQueueService',
#     'campaign_activities': 'CampaignActivityService',
#     'campaign_targets': 'CampaignTargetService'
# }

# Version info for the services module
__version__ = '1.0.0'
__author__ = 'YS'
__description__ = 'Standardized campaign services with Response objects and robust error handling'