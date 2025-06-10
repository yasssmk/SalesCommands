# apps/campaign/services/campaign_manager.py - Version refactorisée
from typing import Dict, List, Optional
from datetime import date
from apps.campaign.models import Campaign
from apps.accounts.models import Contact, Account
from apps.activities.models import Activity
from .campaign_creation_service import CampaignCreationService
from .campaign_execution_service import CampaignExecutionService
from .campaign_analytics_service import CampaignAnalyticsService
from .campaign_result_service import CampaignResultService


class CampaignManager:
    """
    Main orchestrator for campaign operations - delegates to specialized services
    Provides unified interface while maintaining separation of concerns
    """
    
    # ===== CAMPAIGN CREATION & LIFECYCLE =====
    
    @classmethod
    def create_campaign_with_activities(cls, campaign_data: Dict, 
                                    target_accounts: List[int] = None,
                                    target_contacts: List[int] = None,
                                    target_leads: List[int] = None,
                                    target_opportunities: List[int] = None) -> Dict:
        """Create campaign with activities - delegates to CampaignCreationService"""
        return CampaignCreationService.create_campaign_with_activities(
            campaign_data=campaign_data,
            target_accounts=target_accounts,
            target_contacts=target_contacts,
            target_leads=target_leads,
            target_opportunities=target_opportunities
        )
    
    @classmethod
    def start_campaign(cls, campaign: Campaign) -> Dict:
        """Start campaign - delegates to CampaignCreationService"""
        return CampaignCreationService.start_campaign(campaign)
    
    @classmethod
    def pause_campaign(cls, campaign: Campaign, pause_until: date = None) -> Dict:
        """Pause campaign - delegates to CampaignCreationService"""
        return CampaignCreationService.pause_campaign(campaign, pause_until)
    
    @classmethod
    def resume_campaign(cls, campaign: Campaign) -> Dict:
        """Resume campaign - delegates to CampaignCreationService"""
        return CampaignCreationService.resume_campaign(campaign)
    
    # ===== CAMPAIGN EXECUTION =====
    
    @classmethod
    def get_campaign_playlist(cls, campaign: Campaign, limit: int = None, 
                             current_activity_type: str = None) -> Dict:
        """Get campaign playlist - delegates to CampaignExecutionService"""
        return CampaignExecutionService.get_campaign_playlist(
            campaign=campaign,
            limit=limit,
            current_activity_type=current_activity_type
        )
    
    @classmethod
    def remove_contact_from_campaign(cls, campaign: Campaign, contact: Contact, 
                                   notes: str = None) -> Dict:
        """Remove contact - delegates to CampaignExecutionService"""
        return CampaignExecutionService.remove_contact_from_campaign(
            campaign=campaign,
            contact=contact,
            notes=notes
        )
    
    @classmethod
    def remove_account_from_campaign(cls, campaign: Campaign, account: Account, 
                                   notes: str = None) -> Dict:
        """Remove account - delegates to CampaignExecutionService"""
        return CampaignExecutionService.remove_account_from_campaign(
            campaign=campaign,
            account=account,
            notes=notes
        )
    
    @classmethod
    def get_campaign_contacts_with_responses(cls, campaign: Campaign) -> List[Dict]:
        """Get contacts with responses - delegates to CampaignExecutionService"""
        return CampaignExecutionService.get_campaign_contacts_with_responses(campaign)
    
    # ===== ACTIVITY MANAGEMENT =====
    
    @classmethod
    def complete_activity(cls, activity: Activity, result: str, 
                         notes: str = None, **kwargs) -> Dict:
        """
        Complete an activity and process the result with updated playlist
        Orchestrates between CampaignResultService and CampaignExecutionService
        """
        # Process the result
        result_info = CampaignResultService.process_activity_result(
            activity, result, notes, **kwargs
        )
        
        # Get updated campaign playlist if activity belongs to a campaign
        if hasattr(activity, 'campaign_info') and activity.campaign_info:
            campaign = activity.campaign_info.campaign
            try:
                updated_playlist = cls.get_campaign_playlist(campaign, limit=10)
                result_info['updated_playlist'] = updated_playlist.get('items', [])
            except Exception:
                # If playlist generation fails, continue without it (non-critical)
                result_info['updated_playlist'] = []
                result_info['playlist_error'] = 'Failed to update playlist'
        
        return result_info
    
    # ===== ANALYTICS & REPORTING =====
    
    @classmethod
    def get_campaign_summary(cls, campaign: Campaign) -> Dict:
        """Get campaign summary - delegates to CampaignAnalyticsService"""
        return CampaignAnalyticsService.get_campaign_summary(campaign)
    
    @classmethod
    def get_campaign_activities(cls, campaign: Campaign, status_filter: List[str] = None) -> Dict:
        """Get campaign activities - delegates to CampaignAnalyticsService"""
        return CampaignAnalyticsService.get_campaign_activities(
            campaign=campaign,
            status_filter=status_filter
        )

    @classmethod
    def get_account_activities_in_campaign(cls, campaign: Campaign, account: Account, 
                                        status_filter: List[str] = None) -> Dict:
        """Get account activities - delegates to CampaignAnalyticsService"""
        return CampaignAnalyticsService.get_account_activities_in_campaign(
            campaign=campaign,
            account=account,
            status_filter=status_filter
        )

    @classmethod
    def get_contact_activities_in_campaign(cls, campaign: Campaign, contact: Contact, 
                                        status_filter: List[str] = None) -> Dict:
        """Get contact activities - delegates to CampaignAnalyticsService"""
        return CampaignAnalyticsService.get_contact_activities_in_campaign(
            campaign=campaign,
            contact=contact,
            status_filter=status_filter
        )
    
    @classmethod
    def get_campaign_performance_metrics(cls, campaign: Campaign) -> Dict:
        """Get performance metrics - delegates to CampaignAnalyticsService"""
        return CampaignAnalyticsService.get_campaign_performance_metrics(campaign)
    
    # ===== CONVENIENCE METHODS =====
    
    @classmethod
    def add_manual_activity_to_campaign(cls, campaign: Campaign, contact: Contact, 
                                      activity_type: str, result: str, notes: str = None, 
                                      user=None, **kwargs) -> Dict:
        """
        Add manual activity - delegates to CampaignExecutionService with playlist update
        Orchestrates between execution and updated playlist
        """
        # Add the manual activity
        result_info = CampaignExecutionService.add_manual_activity_to_campaign(
            campaign=campaign,
            contact=contact,
            activity_type=activity_type,
            result=result,
            notes=notes,
            user=user,
            **kwargs
        )
        
        # Get updated playlist
        try:
            updated_playlist = cls.get_campaign_playlist(campaign, limit=10)
            result_info['updated_playlist'] = updated_playlist.get('items', [])
        except Exception:
            result_info['updated_playlist'] = []
            result_info['playlist_error'] = 'Failed to update playlist'
        
        return result_info
    
    # ===== BULK OPERATIONS =====
    
    @classmethod
    def bulk_remove_contacts(cls, campaign: Campaign, contact_ids: List[int], 
                           notes: str = None) -> Dict:
        """
        Bulk remove multiple contacts from campaign
        Orchestrates multiple removal operations
        """
        from apps.accounts.models import Contact
        
        results = {
            'success': [],
            'failed': [],
            'total_activities_cancelled': 0
        }
        
        for contact_id in contact_ids:
            try:
                contact = Contact.objects.get(id=contact_id)
                result = cls.remove_contact_from_campaign(campaign, contact, notes)
                
                results['success'].append({
                    'contact_id': contact_id,
                    'contact_name': f"{contact.first_name} {contact.last_name}",
                    'activities_cancelled': result.get('activities_cancelled', 0)
                })
                results['total_activities_cancelled'] += result.get('activities_cancelled', 0)
                
            except Contact.DoesNotExist:
                results['failed'].append({
                    'contact_id': contact_id,
                    'error': 'Contact not found'
                })
            except Exception as e:
                results['failed'].append({
                    'contact_id': contact_id,
                    'error': str(e)
                })
        
        return {
            'success': True,
            'action': 'bulk_contacts_removed',
            'results': results,
            'message': f"Processed {len(contact_ids)} contacts. {len(results['success'])} successful, {len(results['failed'])} failed."
        }