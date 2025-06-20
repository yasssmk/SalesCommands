# # apps/campaign/services/campaign_manager.py
# from typing import Dict, List, Optional
# from datetime import date
# from rest_framework.response import Response
# from apps.campaign.models import Campaign
# from apps.accounts.models import Contact, Account
# from apps.activities.models import Activity
# from apps.campaign.services.campaign_creation_service import CampaignCreationService
# from apps.campaign.services.campaign_analytics_service import CampaignAnalyticsService
# from .campaign_core_service import CampaignCoreService
# from django.db import transaction
# from apps.campaign.utils.standardized_responses import (
#     StandardizedSuccessResponse, 
#     CampaignResponseBuilder, 
#     CampaignSuccessMessages
# )
# from core.exceptions import StandardizedValidationError
# from core.error_messages import CampaignErrorMessages
# from apps.campaign.config.variables import FIELD_NAMES, OPERATION_MESSAGES


# class CampaignManager:
#     """
#     Main orchestrator for campaign operations - delegates to specialized services
#     Provides unified interface while maintaining separation of concerns
#     Now returns standardized Response objects with proper error handling
#     """
    
#     # ===== CAMPAIGN CREATION & LIFECYCLE =====
    
#     @classmethod
#     def create_campaign_with_activities(cls, campaign_data: Dict, 
#                                     target_accounts: List[int] = None,
#                                     target_contacts: List[int] = None,
#                                     target_leads: List[int] = None,
#                                     target_opportunities: List[int] = None,
#                                     targeting_stats: Dict = None) -> Response:
#         """Create campaign with activities - delegates to CampaignCreationService"""
#         try:
#             # CampaignCreationService now returns Response directly
#             return CampaignCreationService.create_campaign_with_activities(
#                 campaign_data=campaign_data,
#                 target_accounts=target_accounts,
#                 target_contacts=target_contacts,
#                 target_leads=target_leads,
#                 target_opportunities=target_opportunities,
#                 targeting_stats=targeting_stats
#             )
#         except StandardizedValidationError:
#             # Re-raise validation errors
#             raise
#         except Exception as e:
#             raise StandardizedValidationError(
#                 CampaignErrorMessages.CAMPAIGN_SEQUENCE_GENERATION_FAILED.format(reason=str(e))
#             )
    
#     @classmethod
#     def start_campaign(cls, campaign: Campaign) -> Response:
#         """Start campaign - delegates to CampaignCreationService"""
#         try:
#             # CampaignCreationService now returns Response directly
#             return CampaignCreationService.start_campaign(campaign)
#         except StandardizedValidationError:
#             # Re-raise validation errors
#             raise
#         except Exception as e:
#             raise StandardizedValidationError(
#                 CampaignErrorMessages.CAMPAIGN_INVALID_STATE.format(current_state=f"start failed: {str(e)}")
#             )
    
#     @classmethod
#     def pause_campaign(cls, campaign: Campaign, pause_until: date = None) -> Response:
#         """Pause campaign - delegates to CampaignCreationService"""
#         try:
#             # CampaignCreationService now returns Response directly
#             return CampaignCreationService.pause_campaign(campaign, pause_until)
#         except StandardizedValidationError:
#             # Re-raise validation errors
#             raise
#         except Exception as e:
#             raise StandardizedValidationError(
#                 CampaignErrorMessages.CAMPAIGN_INVALID_STATE.format(current_state=f"pause failed: {str(e)}")
#             )
    
#     @classmethod
#     def resume_campaign(cls, campaign: Campaign) -> Response:
#         """Resume campaign - delegates to CampaignCreationService"""
#         try:
#             # CampaignCreationService now returns Response directly
#             return CampaignCreationService.resume_campaign(campaign)
#         except StandardizedValidationError:
#             # Re-raise validation errors
#             raise
#         except Exception as e:
#             raise StandardizedValidationError(
#                 CampaignErrorMessages.CAMPAIGN_INVALID_STATE.format(current_state=f"resume failed: {str(e)}")
#             )
    
#     # ===== CAMPAIGN EXECUTION =====
    
#     @classmethod
#     def get_campaign_playlist(cls, campaign: Campaign, limit: int = None, 
#                              current_activity_type: str = None) -> Response:
#         """Get campaign playlist - returns standardized response"""
#         try:
#             # MODIFIER : Utiliser CampaignCoreService au lieu de CampaignExecutionService
#             return CampaignCoreService.get_campaign_playlist_internal(
#                 campaign=campaign,
#                 limit=limit,
#                 current_activity_type=current_activity_type
#             )
#         except StandardizedValidationError:
#             # Re-raise validation errors
#             raise
#         except Exception as e:
#             raise StandardizedValidationError(
#                 CampaignErrorMessages.PLAYLIST_EMPTY
#             )
    
#     @classmethod
#     def remove_contact_from_campaign(cls, campaign: Campaign, contact: Contact, 
#                                    notes: str = None) -> Response:
#         """Remove contact - returns standardized response"""
#         try:
#             return CampaignCoreService.remove_contact_from_campaign_internal(
#                 campaign=campaign,
#                 contact=contact,
#                 notes=notes
#             )
#         except StandardizedValidationError:
#             raise
#         except Exception as e:
#             raise StandardizedValidationError(
#                 CampaignErrorMessages.CAMPAIGN_CONTACT_MAPPING_FAILED
#             )
    
#     @classmethod
#     def remove_account_from_campaign(cls, campaign: Campaign, account: Account, 
#                                    notes: str = None) -> Response:
#         """Remove account - returns standardized response"""
#         try:
#             return CampaignCoreService.remove_account_from_campaign_internal(
#                 campaign=campaign,
#                 account=account,
#                 notes=notes
#             )
#         except StandardizedValidationError:
#             raise
#         except Exception as e:
#             raise StandardizedValidationError(
#                 CampaignErrorMessages.TARGET_NOT_FOUND_IN_CAMPAIGN
#             )
    
#     @classmethod
#     def get_campaign_contacts_with_responses(cls, campaign: Campaign) -> Response:
#         """Get contacts with responses - returns standardized response"""
#         try:
#             return CampaignCoreService.get_campaign_contacts_with_responses_internal(campaign)
#         except StandardizedValidationError:
#             raise
#         except Exception as e:
#             raise StandardizedValidationError(
#                 CampaignErrorMessages.ANALYTICS_CALCULATION_FAILED
#             )
    
#     # ===== ACTIVITY MANAGEMENT =====
    
#     @classmethod
#     def complete_activity(cls, activity: Activity, result: str, 
#                          notes: str = None, **kwargs) -> Response:
#         """
#         Complete an activity and process the result with updated playlist
#         """
#         try:
#             return CampaignCoreService.complete_activity_internal(
#                 activity=activity,
#                 result=result,
#                 notes=notes,
#                 **kwargs
#             )
            
#         except StandardizedValidationError:
#             raise
#         except Exception as e:
#             raise StandardizedValidationError(
#                 CampaignErrorMessages.RESULT_PROCESSING_FAILED.format(reason=str(e))
#             )
    
#     # ===== ANALYTICS & REPORTING =====
    
#     @classmethod
#     def get_campaign_summary(cls, campaign: Campaign) -> Response:
#         """Get campaign summary - returns standardized response"""
#         try:
#             # CampaignAnalyticsService now returns Response directly
#             return CampaignAnalyticsService.get_campaign_summary(campaign)
#         except StandardizedValidationError:
#             # Re-raise validation errors
#             raise
#         except Exception as e:
#             raise StandardizedValidationError(
#                 CampaignErrorMessages.ANALYTICS_CALCULATION_FAILED
#             )
    
#     @classmethod
#     def get_campaign_activities(cls, campaign: Campaign, status_filter: List[str] = None) -> Response:
#         """Get campaign activities - returns standardized response"""
#         try:
#             # CampaignAnalyticsService now returns Response directly
#             return CampaignAnalyticsService.get_campaign_activities(
#                 campaign=campaign,
#                 status_filter=status_filter
#             )
#         except StandardizedValidationError:
#             # Re-raise validation errors
#             raise
#         except Exception as e:
#             raise StandardizedValidationError(
#                 CampaignErrorMessages.ANALYTICS_CALCULATION_FAILED
#             )

#     @classmethod
#     def get_account_activities_in_campaign(cls, campaign: Campaign, account: Account, 
#                                         status_filter: List[str] = None) -> Response:
#         """Get account activities - returns standardized response"""
#         try:
#             # CampaignAnalyticsService now returns Response directly
#             return CampaignAnalyticsService.get_account_activities_in_campaign(
#                 campaign=campaign,
#                 account=account,
#                 status_filter=status_filter
#             )
#         except StandardizedValidationError:
#             # Re-raise validation errors
#             raise
#         except Exception as e:
#             raise StandardizedValidationError(
#                 CampaignErrorMessages.ANALYTICS_CALCULATION_FAILED
#             )

#     @classmethod
#     def get_contact_activities_in_campaign(cls, campaign: Campaign, contact: Contact, 
#                                         status_filter: List[str] = None) -> Response:
#         """Get contact activities - returns standardized response"""
#         try:
#             # CampaignAnalyticsService now returns Response directly
#             return CampaignAnalyticsService.get_contact_activities_in_campaign(
#                 campaign=campaign,
#                 contact=contact,
#                 status_filter=status_filter
#             )
#         except StandardizedValidationError:
#             # Re-raise validation errors
#             raise
#         except Exception as e:
#             raise StandardizedValidationError(
#                 CampaignErrorMessages.ANALYTICS_CALCULATION_FAILED
#             )
    
#     @classmethod
#     def get_campaign_performance_metrics(cls, campaign: Campaign) -> Response:
#         """Get performance metrics - returns standardized response"""
#         try:
#             # CampaignAnalyticsService now returns Response directly
#             return CampaignAnalyticsService.get_campaign_performance_metrics(campaign)
#         except StandardizedValidationError:
#             # Re-raise validation errors
#             raise
#         except Exception as e:
#             raise StandardizedValidationError(
#                 CampaignErrorMessages.ANALYTICS_CALCULATION_FAILED
#             )
    
#     # ===== CONVENIENCE METHODS =====
    
#     @classmethod
#     def add_manual_activity_to_campaign(cls, campaign: Campaign, contact: Contact, 
#                                       activity_type: str, result: str, notes: str = None, 
#                                       user=None, **kwargs) -> Response:
#         """
#         Add manual activity - RÉÉCRIRE directement sans import CampaignExecutionService
#         """
#         try:
#             # Verify this is a non-sequence campaign
#             if campaign.sequence_type:
#                 raise StandardizedValidationError(
#                     "This operation is only for campaigns without sequences"
#                 )
            
#             # Validate activity type
#             valid_types = [choice[0] for choice in Activity.ActivityType.choices]
#             if activity_type not in valid_types:
#                 raise StandardizedValidationError(
#                     CampaignErrorMessages.ACTIVITY_INVALID_RESULT.format(result=activity_type)
#                 )
            
#             # Get the campaign target for this contact
#             target = None
#             for t in campaign.targets.all():
#                 if (t.contact_id == contact.id or 
#                     (t.account_id == contact.account_id) or
#                     (t.lead and t.lead.account_id == contact.account_id) or
#                     (t.target_opportunity and t.target_opportunity.account_id == contact.account_id)):
#                     target = t
#                     break
            
#             if not target:
#                 raise StandardizedValidationError(CampaignErrorMessages.TARGET_NOT_FOUND_IN_CAMPAIGN)
            
#             from django.utils import timezone
#             from apps.activities.models import ActivityCampaign, ActivitySequence
            
#             # Create activity in transaction
#             with transaction.atomic():
#                 # Create activity
#                 activity = Activity.objects.create(
#                     title=f"{Activity.ActivityType(activity_type).label} with {contact.first_name} {contact.last_name}",
#                     activity_type=activity_type,
#                     description=notes or '',
#                     account=contact.account,
#                     owner=user,
#                     status=Activity.Status.COMPLETED,
#                     scheduled_start=timezone.now(),
#                     completed_at=timezone.now(),
#                     outcome_notes=notes or '',
#                     client_id=campaign.client_id
#                 )
                
#                 # Add contact relationship
#                 activity.contacts.add(contact)
                
#                 # Create campaign relationship
#                 ActivityCampaign.objects.create(
#                     activity=activity,
#                     campaign=campaign,
#                     campaign_target=target,
#                     client_id=campaign.client_id
#                 )
                
#                 # Add sequence info for consistent tracking
#                 ActivitySequence.objects.create(
#                     activity=activity,
#                     source_type=ActivitySequence.SourceType.MANUAL,
#                     sequence_position=1,
#                     min_delay_days=0,
#                     client_id=campaign.client_id
#                 )
                
#                 # MODIFIER : Utiliser CampaignCoreService pour traiter le résultat
#                 result_response = CampaignCoreService.complete_activity_internal(
#                     activity=activity,
#                     result=result,
#                     notes=notes,
#                     **kwargs
#                 )
                
#                 # Extract result info from the standardized response
#                 result_info = {}
#                 if hasattr(result_response, 'data') and 'data' in result_response.data:
#                     result_info = result_response.data['data']
            
#             # Get updated playlist using CampaignCoreService
#             next_activities = []
#             try:
#                 updated_playlist_response = CampaignCoreService.get_campaign_playlist_internal(
#                     campaign=campaign, 
#                     limit=10
#                 )
#                 if hasattr(updated_playlist_response, 'data') and 'data' in updated_playlist_response.data:
#                     playlist_data = updated_playlist_response.data['data']
#                     next_activities = playlist_data.get('items', [])
#             except Exception:
#                 pass
            
#             # Enhance the response with playlist data
#             enhanced_data = result_info.copy()
#             enhanced_data['next_activities'] = next_activities
            
#             meta = {
#                 'operation': 'manual_activity_creation',
#                 'activity_type': activity_type,
#                 'playlist_updated': len(next_activities) > 0
#             }

#             message = OPERATION_MESSAGES['ACTIVITY_COMPLETED']
            
#             return StandardizedSuccessResponse.success(
#                 message=message,
#                 data=enhanced_data,
#                 meta=meta
#             )
            
#         except StandardizedValidationError:
#             raise
#         except Exception as e:
#             raise StandardizedValidationError(
#                 CampaignErrorMessages.ACTIVITY_INVALID_STATE.format(current_state=f"creation failed: {str(e)}")
#             )
    
#     # ===== BULK OPERATIONS =====
    
#     @classmethod
#     def bulk_remove_contacts(cls, campaign: Campaign, contact_ids: List[int], 
#                            notes: str = None) -> Response:
#         """
#         Bulk remove multiple contacts from campaign
#         """
#         try:
#             from apps.accounts.models import Contact
            
#             successful = []
#             failed = []
#             total_activities_cancelled = 0
            
#             for contact_id in contact_ids:
#                 try:
#                     contact = Contact.objects.get(id=contact_id)
#                     result_response = cls.remove_contact_from_campaign(campaign, contact, notes)
                    
#                     # Extract data from the standardized response
#                     if hasattr(result_response, 'data') and 'data' in result_response.data:
#                         response_data = result_response.data['data']
#                         activities_cancelled = response_data.get('activities_cancelled', 0)
                        
#                         successful.append({
#                             f"{FIELD_NAMES['CONTACT']}_id": contact_id,
#                             f"{FIELD_NAMES['CONTACT']}_name": f"{contact.first_name} {contact.last_name}",
#                             'activities_cancelled': activities_cancelled
#                         })
#                         total_activities_cancelled += activities_cancelled
                    
#                 except Contact.DoesNotExist:
#                     failed.append({
#                         f"{FIELD_NAMES['CONTACT']}_id": contact_id,
#                         'error': 'Contact not found'
#                     })
#                 except Exception as e:
#                     failed.append({
#                         f"{FIELD_NAMES['CONTACT']}_id": contact_id,
#                         'error': str(e)
#                     })
            
#             # Use bulk operation response with operation message from config
#             message = OPERATION_MESSAGES['BULK_OPERATION_COMPLETED'].format(
#                 successful=len(successful),
#                 total=len(contact_ids)
#             )
            
#             return CampaignResponseBuilder.bulk_operation(
#                 operation_type='contact_removal',
#                 successful_items=successful,
#                 failed_items=failed,
#                 custom_message=message
#             )
            
#         except StandardizedValidationError:
#             # Re-raise validation errors
#             raise
#         except Exception as e:
#             raise StandardizedValidationError(
#                 CampaignErrorMessages.BULK_OPERATION_FAILED.format(operation="contact removal")
#             )