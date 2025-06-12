# apps/campaign/services/campaign_manager.py
from typing import Dict, List, Optional
from datetime import date
from rest_framework.response import Response
from apps.campaign.models import Campaign
from apps.accounts.models import Contact, Account
from apps.activities.models import Activity
from .campaign_creation_service import CampaignCreationService
from .campaign_execution_service import CampaignExecutionService
from .campaign_analytics_service import CampaignAnalyticsService
from .campaign_result_service import CampaignResultService
from apps.campaign.utils.standardized_responses import (
    StandardizedSuccessResponse, 
    CampaignResponseBuilder, 
    CampaignSuccessMessages
)
from core.exceptions import StandardizedValidationError
from core.error_messages import CampaignErrorMessages

# Import configuration variables
from apps.campaign.config.variables import (
    FIELD_NAMES,
    OPERATION_MESSAGES
)


class CampaignManager:
    """
    Main orchestrator for campaign operations - delegates to specialized services
    Provides unified interface while maintaining separation of concerns
    Now returns standardized Response objects with proper error handling
    """
    
    # ===== CAMPAIGN CREATION & LIFECYCLE =====
    
    @classmethod
    def create_campaign_with_activities(cls, campaign_data: Dict, 
                                    target_accounts: List[int] = None,
                                    target_contacts: List[int] = None,
                                    target_leads: List[int] = None,
                                    target_opportunities: List[int] = None,
                                    targeting_stats: Dict = None) -> Response:
        """Create campaign with activities - delegates to CampaignCreationService"""
        try:
            # CampaignCreationService now returns Response directly
            return CampaignCreationService.create_campaign_with_activities(
                campaign_data=campaign_data,
                target_accounts=target_accounts,
                target_contacts=target_contacts,
                target_leads=target_leads,
                target_opportunities=target_opportunities,
                targeting_stats=targeting_stats
            )
        except StandardizedValidationError:
            # Re-raise validation errors
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CampaignErrorMessages.CAMPAIGN_SEQUENCE_GENERATION_FAILED.format(reason=str(e))
            )
    
    @classmethod
    def start_campaign(cls, campaign: Campaign) -> Response:
        """Start campaign - delegates to CampaignCreationService"""
        try:
            # CampaignCreationService now returns Response directly
            return CampaignCreationService.start_campaign(campaign)
        except StandardizedValidationError:
            # Re-raise validation errors
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CampaignErrorMessages.CAMPAIGN_INVALID_STATE.format(current_state=f"start failed: {str(e)}")
            )
    
    @classmethod
    def pause_campaign(cls, campaign: Campaign, pause_until: date = None) -> Response:
        """Pause campaign - delegates to CampaignCreationService"""
        try:
            # CampaignCreationService now returns Response directly
            return CampaignCreationService.pause_campaign(campaign, pause_until)
        except StandardizedValidationError:
            # Re-raise validation errors
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CampaignErrorMessages.CAMPAIGN_INVALID_STATE.format(current_state=f"pause failed: {str(e)}")
            )
    
    @classmethod
    def resume_campaign(cls, campaign: Campaign) -> Response:
        """Resume campaign - delegates to CampaignCreationService"""
        try:
            # CampaignCreationService now returns Response directly
            return CampaignCreationService.resume_campaign(campaign)
        except StandardizedValidationError:
            # Re-raise validation errors
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CampaignErrorMessages.CAMPAIGN_INVALID_STATE.format(current_state=f"resume failed: {str(e)}")
            )
    
    # ===== CAMPAIGN EXECUTION =====
    
    @classmethod
    def get_campaign_playlist(cls, campaign: Campaign, limit: int = None, 
                             current_activity_type: str = None) -> Response:
        """Get campaign playlist - returns standardized response"""
        try:
            # CampaignExecutionService now returns Response directly
            return CampaignExecutionService.get_campaign_playlist(
                campaign=campaign,
                limit=limit,
                current_activity_type=current_activity_type
            )
        except StandardizedValidationError:
            # Re-raise validation errors
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CampaignErrorMessages.PLAYLIST_EMPTY
            )
    
    @classmethod
    def remove_contact_from_campaign(cls, campaign: Campaign, contact: Contact, 
                                   notes: str = None) -> Response:
        """Remove contact - returns standardized response"""
        try:
            # CampaignExecutionService now returns Response directly
            return CampaignExecutionService.remove_contact_from_campaign(
                campaign=campaign,
                contact=contact,
                notes=notes
            )
        except StandardizedValidationError:
            # Re-raise validation errors
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CampaignErrorMessages.CAMPAIGN_CONTACT_MAPPING_FAILED
            )
    
    @classmethod
    def remove_account_from_campaign(cls, campaign: Campaign, account: Account, 
                                   notes: str = None) -> Response:
        """Remove account - returns standardized response"""
        try:
            # CampaignExecutionService now returns Response directly
            return CampaignExecutionService.remove_account_from_campaign(
                campaign=campaign,
                account=account,
                notes=notes
            )
        except StandardizedValidationError:
            # Re-raise validation errors
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CampaignErrorMessages.TARGET_NOT_FOUND_IN_CAMPAIGN
            )
    
    @classmethod
    def get_campaign_contacts_with_responses(cls, campaign: Campaign) -> Response:
        """Get contacts with responses - returns standardized response"""
        try:
            # CampaignExecutionService now returns Response directly
            return CampaignExecutionService.get_campaign_contacts_with_responses(campaign)
        except StandardizedValidationError:
            # Re-raise validation errors
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CampaignErrorMessages.ANALYTICS_CALCULATION_FAILED
            )
    
    # ===== ACTIVITY MANAGEMENT =====
    
    @classmethod
    def complete_activity(cls, activity: Activity, result: str, 
                         notes: str = None, **kwargs) -> Response:
        """
        Complete an activity and process the result with updated playlist
        Orchestrates between CampaignResultService and CampaignExecutionService
        """
        try:
            # Process the result using CampaignResultService (returns Response)
            result_response = CampaignResultService.process_activity_result(
                activity, result, notes, **kwargs
            )
            
            # Extract result info from the standardized Response
            result_info = {}
            if hasattr(result_response, 'data') and 'data' in result_response.data:
                result_info = result_response.data['data']
            
            # Get updated campaign playlist if activity belongs to a campaign
            next_activities = []
            if hasattr(activity, 'campaign_info') and activity.campaign_info:
                campaign = activity.campaign_info.campaign
                try:
                    updated_playlist_response = cls.get_campaign_playlist(campaign, limit=10)
                    # Extract items from the standardized Response
                    if hasattr(updated_playlist_response, 'data') and 'data' in updated_playlist_response.data:
                        playlist_data = updated_playlist_response.data['data']
                        next_activities = playlist_data.get('items', [])
                except Exception:
                    # If playlist generation fails, continue without it (non-critical)
                    pass
            
            # Use CampaignResponseBuilder for activity completion
            return CampaignResponseBuilder.activity_completed(
                result_action=result_info.get('action', 'completed'),
                activity_id=activity.id,
                next_activities=next_activities,
                additional_info=result_info
            )
            
        except StandardizedValidationError:
            # Re-raise validation errors
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CampaignErrorMessages.RESULT_PROCESSING_FAILED.format(reason=str(e))
            )
    
    # ===== ANALYTICS & REPORTING =====
    
    @classmethod
    def get_campaign_summary(cls, campaign: Campaign) -> Response:
        """Get campaign summary - returns standardized response"""
        try:
            # CampaignAnalyticsService now returns Response directly
            return CampaignAnalyticsService.get_campaign_summary(campaign)
        except StandardizedValidationError:
            # Re-raise validation errors
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CampaignErrorMessages.ANALYTICS_CALCULATION_FAILED
            )
    
    @classmethod
    def get_campaign_activities(cls, campaign: Campaign, status_filter: List[str] = None) -> Response:
        """Get campaign activities - returns standardized response"""
        try:
            # CampaignAnalyticsService now returns Response directly
            return CampaignAnalyticsService.get_campaign_activities(
                campaign=campaign,
                status_filter=status_filter
            )
        except StandardizedValidationError:
            # Re-raise validation errors
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CampaignErrorMessages.ANALYTICS_CALCULATION_FAILED
            )

    @classmethod
    def get_account_activities_in_campaign(cls, campaign: Campaign, account: Account, 
                                        status_filter: List[str] = None) -> Response:
        """Get account activities - returns standardized response"""
        try:
            # CampaignAnalyticsService now returns Response directly
            return CampaignAnalyticsService.get_account_activities_in_campaign(
                campaign=campaign,
                account=account,
                status_filter=status_filter
            )
        except StandardizedValidationError:
            # Re-raise validation errors
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CampaignErrorMessages.ANALYTICS_CALCULATION_FAILED
            )

    @classmethod
    def get_contact_activities_in_campaign(cls, campaign: Campaign, contact: Contact, 
                                        status_filter: List[str] = None) -> Response:
        """Get contact activities - returns standardized response"""
        try:
            # CampaignAnalyticsService now returns Response directly
            return CampaignAnalyticsService.get_contact_activities_in_campaign(
                campaign=campaign,
                contact=contact,
                status_filter=status_filter
            )
        except StandardizedValidationError:
            # Re-raise validation errors
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CampaignErrorMessages.ANALYTICS_CALCULATION_FAILED
            )
    
    @classmethod
    def get_campaign_performance_metrics(cls, campaign: Campaign) -> Response:
        """Get performance metrics - returns standardized response"""
        try:
            # CampaignAnalyticsService now returns Response directly
            return CampaignAnalyticsService.get_campaign_performance_metrics(campaign)
        except StandardizedValidationError:
            # Re-raise validation errors
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CampaignErrorMessages.ANALYTICS_CALCULATION_FAILED
            )
    
    # ===== CONVENIENCE METHODS =====
    
    @classmethod
    def add_manual_activity_to_campaign(cls, campaign: Campaign, contact: Contact, 
                                      activity_type: str, result: str, notes: str = None, 
                                      user=None, **kwargs) -> Response:
        """
        Add manual activity - returns standardized response with playlist update
        """
        try:
            # CampaignExecutionService handles creation and result processing
            result_response = CampaignExecutionService.add_manual_activity_to_campaign(
                campaign=campaign,
                contact=contact,
                activity_type=activity_type,
                result=result,
                notes=notes,
                user=user,
                **kwargs
            )
            
            # Extract result info from the standardized Response
            result_info = {}
            if hasattr(result_response, 'data') and 'data' in result_response.data:
                result_info = result_response.data['data']
            
            # Get updated playlist
            next_activities = []
            try:
                updated_playlist_response = cls.get_campaign_playlist(campaign, limit=10)
                if hasattr(updated_playlist_response, 'data') and 'data' in updated_playlist_response.data:
                    playlist_data = updated_playlist_response.data['data']
                    next_activities = playlist_data.get('items', [])
            except Exception:
                # If playlist fails, continue without it (non-critical)
                pass
            
            # Enhance the response with playlist data
            enhanced_data = result_info.copy()
            enhanced_data['next_activities'] = next_activities
            
            meta = {
                'operation': 'manual_activity_creation',
                'activity_type': activity_type,
                'playlist_updated': len(next_activities) > 0
            }
            
            return StandardizedSuccessResponse.success(
                message=f"Manual {activity_type.lower()} activity added successfully",
                data=enhanced_data,
                meta=meta
            )
            
        except StandardizedValidationError:
            # Re-raise validation errors
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CampaignErrorMessages.ACTIVITY_INVALID_STATE.format(current_state=f"creation failed: {str(e)}")
            )
    
    # ===== BULK OPERATIONS =====
    
    @classmethod
    def bulk_remove_contacts(cls, campaign: Campaign, contact_ids: List[int], 
                           notes: str = None) -> Response:
        """
        Bulk remove multiple contacts from campaign
        """
        try:
            from apps.accounts.models import Contact
            
            successful = []
            failed = []
            total_activities_cancelled = 0
            
            for contact_id in contact_ids:
                try:
                    contact = Contact.objects.get(id=contact_id)
                    result_response = cls.remove_contact_from_campaign(campaign, contact, notes)
                    
                    # Extract data from the standardized response
                    if hasattr(result_response, 'data') and 'data' in result_response.data:
                        response_data = result_response.data['data']
                        activities_cancelled = response_data.get('activities_cancelled', 0)
                        
                        successful.append({
                            f"{FIELD_NAMES['CONTACT']}_id": contact_id,
                            f"{FIELD_NAMES['CONTACT']}_name": f"{contact.first_name} {contact.last_name}",
                            'activities_cancelled': activities_cancelled
                        })
                        total_activities_cancelled += activities_cancelled
                    
                except Contact.DoesNotExist:
                    failed.append({
                        f"{FIELD_NAMES['CONTACT']}_id": contact_id,
                        'error': 'Contact not found'
                    })
                except Exception as e:
                    failed.append({
                        f"{FIELD_NAMES['CONTACT']}_id": contact_id,
                        'error': str(e)
                    })
            
            # Use bulk operation response with operation message from config
            message = OPERATION_MESSAGES['BULK_OPERATION_COMPLETED'].format(
                successful=len(successful),
                total=len(contact_ids)
            )
            
            return CampaignResponseBuilder.bulk_operation(
                operation_type='contact_removal',
                successful_items=successful,
                failed_items=failed,
                custom_message=message
            )
            
        except StandardizedValidationError:
            # Re-raise validation errors
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CampaignErrorMessages.BULK_OPERATION_FAILED.format(operation="contact removal")
            )