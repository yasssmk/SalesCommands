# apps/campaign/services/campaign_tracking_service.py 
from typing import Optional
from django.db import transaction
from apps.campaign.models import Campaign
from apps.campaign.models.campaign_result_tracking import CampaignResultTracking
from core.exceptions import StandardizedValidationError
from core.error_messages import CoreErrorMessages


class CampaignTrackingService:
    """
    Service for tracking campaign-originated business events
    Version MVP : Appels directs, pas de signals
    """
    
    @classmethod
    def get_or_create_result_tracking(cls, campaign: Campaign) -> CampaignResultTracking:
        """
        Obtenir ou créer le CampaignResultTracking pour une campagne
        Version MVP : Appel direct, simple et prévisible
        """
        try:
            result_tracking, created = CampaignResultTracking.objects.get_or_create(
                campaign=campaign,
                defaults={
                    'client_id': campaign.client_id
                }
            )
            return result_tracking
            
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(
                    detail=f"Failed to get result tracking for campaign {campaign.id}: {str(e)}"
                )
            )
    
    @classmethod
    def track_lead_created(cls, lead, campaign: Campaign = None):
        """
        Track when a lead is created from a campaign source
        VERSION MVP : Appel direct du tracking
        """
        # Determine campaign source
        source_campaign = campaign or getattr(lead, 'campaign', None)
        
        if not source_campaign:
            return  # No campaign attribution
        
        try:
            # Obtenir le result tracking
            result_tracking = cls.get_or_create_result_tracking(source_campaign)
            
            # Track le lead directement
            result_tracking.track_lead(lead.id)
                    
        except Exception:
            # Silent fail - don't break lead creation if tracking fails
            print(f"Failed to track lead {lead.id} for campaign {source_campaign.id if source_campaign else 'unknown'}")  
            pass
    
    @classmethod
    def track_opportunity_created(cls, opportunity, campaign: Campaign = None, amount: float = 0):
        """
        Track when an opportunity is created from a campaign source
        VERSION MVP : Appel direct du tracking
        """
        # Determine campaign source
        source_campaign = campaign
        
        if not source_campaign and hasattr(opportunity, 'source'):
            source_campaign = getattr(opportunity.source, 'source_campaign', None)
        
        if not source_campaign:
            return  # No campaign attribution
        
        try:
            # Obtenir le result tracking
            result_tracking = cls.get_or_create_result_tracking(source_campaign)
            
            # Convertir amount en Decimal
            from decimal import Decimal
            pipeline_value = Decimal(str(amount)) if amount > 0 else None
            
            # Track l'opportunity directement
            result_tracking.track_opportunity(opportunity.id, pipeline_value=pipeline_value)
                    
        except Exception:
            # Silent fail - don't break opportunity creation
            print(f"Failed to track opportunity {opportunity.id} for campaign {source_campaign.id if source_campaign else 'unknown'}")
            pass
    
    @classmethod
    def track_deal_closed(cls, opportunity, amount: float = 0):
        """
        Track when a deal is closed (opportunity won)
        VERSION MVP : Appel direct du tracking
        """
        # Find campaign source
        source_campaign = None
        
        if hasattr(opportunity, 'source'):
            source_campaign = getattr(opportunity.source, 'source_campaign', None)
        
        if not source_campaign:
            return  # No campaign attribution
        
        try:
            # Obtenir le result tracking
            result_tracking = cls.get_or_create_result_tracking(source_campaign)
            
            # Convertir amount en Decimal
            from decimal import Decimal
            revenue = Decimal(str(amount)) if amount > 0 else None
            
            # Track le deal directement
            result_tracking.track_deal_closed(opportunity.id, revenue=revenue)
                    
        except Exception:
            # Silent fail - don't break deal closure
            print(f"Failed to track deal closure for opportunity {opportunity.id} in campaign {source_campaign.id if source_campaign else 'unknown'}")
            pass
    
    @classmethod
    def track_meeting_scheduled(cls, activity, campaign: Campaign = None):
        """
        Track when a meeting is scheduled from a campaign
        VERSION MVP : Appel direct du tracking
        """
        # Determine campaign source
        source_campaign = campaign
        
        if not source_campaign and hasattr(activity, 'campaign_info'):
            source_campaign = activity.campaign_info.campaign
        
        if not source_campaign:
            return  # No campaign attribution
        
        try:
            # Obtenir le result tracking
            result_tracking = cls.get_or_create_result_tracking(source_campaign)
            
            # Track le meeting directement
            result_tracking.track_meeting(activity.id)
                    
        except Exception:
            # Silent fail - don't break meeting creation
            print(f"Failed to track meeting {activity.id} for campaign {source_campaign.id if source_campaign else 'unknown'}")
            pass
    
    # === MÉTHODES UTILITAIRES POUR LE MVP ===
    
    @classmethod
    def get_campaign_metrics(cls, campaign: Campaign) -> dict:
        """Récupérer les métriques d'une campagne (version MVP)"""
        try:
            result_tracking = cls.get_or_create_result_tracking(campaign)
            
            return {
                'leads_created': result_tracking.leads_created_count,
                'meetings_secured': result_tracking.meetings_secured_count,
                'opportunities_created': result_tracking.opportunities_created_count,
                'deals_closed': result_tracking.deals_closed_count,
                'pipeline_value': float(result_tracking.pipeline_value_created),
                'revenue_generated': float(result_tracking.revenue_generated),
                'last_updated': result_tracking.last_updated.isoformat()
            }
            
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(
                    detail=f"Failed to get metrics for campaign {campaign.id}: {str(e)}"
                )
            )
    

    @classmethod
    def cleanup_invalid_tracking_data(cls, campaign: Campaign) -> dict:
        """
        Nettoyer les données de tracking invalides (version MVP)
        
        Args:
            campaign: Campaign instance
            
        Returns:
            dict: Rapport de nettoyage simple
        """
        try:
            result_tracking = cls.get_or_create_result_tracking(campaign)
            
            # Obtenir rapport d'intégrité
            integrity_report = result_tracking.get_integrity_report()
            
            cleanup_actions = []
            
            with transaction.atomic():
                # Nettoyer leads invalides
                if integrity_report['leads'].get('deleted_ids'):
                    invalid_leads = integrity_report['leads']['deleted_ids']
                    result_tracking.tracked_lead_ids = [
                        id for id in result_tracking.tracked_lead_ids 
                        if id not in invalid_leads
                    ]
                    result_tracking.leads_created_count = len(result_tracking.tracked_lead_ids)
                    cleanup_actions.append(f"Removed {len(invalid_leads)} deleted leads")
                
                # Nettoyer meetings invalides
                if integrity_report['meetings'].get('deleted_ids'):
                    invalid_meetings = integrity_report['meetings']['deleted_ids']
                    result_tracking.tracked_meeting_ids = [
                        id for id in result_tracking.tracked_meeting_ids
                        if id not in invalid_meetings
                    ]
                    result_tracking.meetings_secured_count = len(result_tracking.tracked_meeting_ids)
                    cleanup_actions.append(f"Removed {len(invalid_meetings)} deleted meetings")
                
                # Nettoyer opportunities invalides
                if integrity_report['opportunities'].get('deleted_ids'):
                    invalid_opps = integrity_report['opportunities']['deleted_ids']
                    result_tracking.tracked_opportunity_ids = [
                        id for id in result_tracking.tracked_opportunity_ids
                        if id not in invalid_opps
                    ]
                    result_tracking.opportunities_created_count = len(result_tracking.tracked_opportunity_ids)
                    cleanup_actions.append(f"Removed {len(invalid_opps)} deleted opportunities")
                
                # Nettoyer deals invalides
                if integrity_report['deals'].get('deleted_ids'):
                    invalid_deals = integrity_report['deals']['deleted_ids']
                    result_tracking.tracked_deal_ids = [
                        id for id in result_tracking.tracked_deal_ids
                        if id not in invalid_deals
                    ]
                    result_tracking.deals_closed_count = len(result_tracking.tracked_deal_ids)
                    cleanup_actions.append(f"Removed {len(invalid_deals)} deleted deals")
                
                # Sauvegarder si des changements
                if cleanup_actions:
                    result_tracking.save()
            
            return {
                'campaign_id': campaign.id,
                'campaign_name': campaign.name,
                'cleanup_successful': len(cleanup_actions) > 0,
                'actions_taken': cleanup_actions,
                'before_integrity_score': integrity_report['integrity_score'],
                'after_integrity_score': 100.0 if cleanup_actions else integrity_report['integrity_score']
            }
            
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(
                    detail=f"Failed to cleanup tracking data for campaign {campaign.id}: {str(e)}"
                )
            )