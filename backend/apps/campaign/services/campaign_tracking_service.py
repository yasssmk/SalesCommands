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

            if not created:
                cls._auto_validate_and_clean(result_tracking, silent=True)

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
 
            if cls._is_already_tracked(result_tracking, 'lead', lead.id):
                print(f"Lead {lead.id} already tracked for campaign {source_campaign.id}")
                return

            # Track le lead directement
            success = result_tracking.track_lead(lead.id)
            # ✅ AJOUTER : Auto-validation après modification
            if success:
                cls._auto_validate_and_clean(result_tracking, silent=True)  

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

            if cls._is_already_tracked(result_tracking, 'opportunity', opportunity.id):
                print(f"Opportunity {opportunity.id} already tracked for campaign {source_campaign.id}")
                return
            # Convertir amount en Decimal
            from decimal import Decimal
            pipeline_value = Decimal(str(amount)) if amount > 0 else None

            # Track l'opportunity directement
            success = result_tracking.track_opportunity(opportunity.id, pipeline_value=pipeline_value)
            # ✅ AJOUTER : Auto-validation après modification
            if success:
                cls._auto_validate_and_clean(result_tracking, silent=True)
                   
        except Exception as e:
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
            
            if cls._is_already_tracked(result_tracking, 'deal', opportunity.id):
                print(f"Deal {opportunity.id} already tracked for campaign {source_campaign.id}")
                return
            
            # Convertir amount en Decimal
            from decimal import Decimal
            revenue = Decimal(str(amount)) if amount > 0 else None
            
            # Track le deal directement
            success = result_tracking.track_deal_closed(opportunity.id, revenue=revenue)
            
            # ✅ AJOUTER : Auto-validation après modification
            if success:
                cls._auto_validate_and_clean(result_tracking, silent=True)
                    
        except Exception:
            # Silent fail - don't break deal closure
            print(f"Failed to track deal closure for opportunity {opportunity.id} in campaign {source_campaign.id if source_campaign else 'unknown'}")
            pass
    
    @classmethod
    def update_opportunity_amount(cls, opportunity, campaign: Campaign, old_amount: float, new_amount: float):
        """
        Met à jour le pipeline value quand le montant d'une opportunité change
        VERSION MVP : Appel direct du tracking
        """
        # Si pas de campagne, rien à faire
        if not campaign:
            return
        
        try:
            # Obtenir le result tracking
            result_tracking = cls.get_or_create_result_tracking(campaign)
            
            # Vérifier que l'opportunité est bien trackée
            if opportunity.id not in result_tracking.tracked_opportunity_ids:
                print(f"Opportunity {opportunity.id} not tracked by campaign {campaign.id}")
                return
            
            # Convertir les montants en Decimal
            from decimal import Decimal
            old_value = Decimal(str(old_amount)) if old_amount else Decimal('0.00')
            new_value = Decimal(str(new_amount)) if new_amount else Decimal('0.00')
            
            from apps.opportunities.models import Opportunity
            opp_status = opportunity.status
            
            # Si l'opportunité est fermée (WON ou LOST), elle ne doit pas être dans le pipeline
            if opp_status in [Opportunity.OpportunityStatus.CLOSED_WON, Opportunity.OpportunityStatus.CLOSED_LOST]:
                # L'opportunité est fermée, elle ne devrait pas compter dans le pipeline
                # On retire l'ancienne valeur si elle était comptée
                result_tracking.pipeline_value_created -= old_value
            else:
                # L'opportunité est ouverte, on met à jour normalement
                difference = new_value - old_value
                result_tracking.pipeline_value_created += difference
            
            # S'assurer que la valeur reste positive
            if result_tracking.pipeline_value_created < 0:
                result_tracking.pipeline_value_created = Decimal('0.00')
            
            # Sauvegarder
            result_tracking.save()
            
            # Auto-validation après modification
            cls._auto_validate_and_clean(result_tracking, silent=True)
            
            print(f"Updated pipeline value for campaign {campaign.id}: Status={opp_status}, Old={old_value}, New={new_value}, Pipeline={result_tracking.pipeline_value_created}")
            
        except Exception as e:
            # Silent fail - ne pas casser la mise à jour de l'opportunité
            print(f"Failed to update opportunity amount for campaign {campaign.id}: {str(e)}")
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
            
            if cls._is_already_tracked(result_tracking, 'meeting', activity.id):
                print(f"Meeting {activity.id} already tracked for campaign {source_campaign.id}")
                return
            
            # Track le meeting directement
            success = result_tracking.track_meeting(activity.id)
            
            # ✅ AJOUTER : Auto-validation après modification
            if success:
                cls._auto_validate_and_clean(result_tracking, silent=True)
                    
        except Exception:
            # Silent fail - don't break meeting creation
            print(f"Failed to track meeting {activity.id} for campaign {source_campaign.id if source_campaign else 'unknown'}")
            pass
    

    @classmethod
    def _is_already_tracked(cls, result_tracking: CampaignResultTracking, object_type: str, object_id: int) -> bool:
        """Vérifier si un objet est déjà tracké pour éviter les doublons"""
        try:
            if object_type == 'lead':
                return object_id in result_tracking.tracked_lead_ids
            elif object_type == 'meeting':
                return object_id in result_tracking.tracked_meeting_ids
            elif object_type == 'opportunity':
                return object_id in result_tracking.tracked_opportunity_ids
            elif object_type == 'deal':
                return object_id in result_tracking.tracked_deal_ids
            return False
        except Exception:
            return False
    
    @classmethod
    def _auto_validate_and_clean(cls, result_tracking: CampaignResultTracking, silent: bool = True):
        """
        Auto-validation et nettoyage silencieux des données de tracking
        MÉTHODE CLÉE pour maintenir l'intégrité
        """
        try:
            corrections_made = []
            
            with transaction.atomic():
                # 1. Supprimer les doublons dans les listes
                original_leads = result_tracking.tracked_lead_ids.copy()
                result_tracking.tracked_lead_ids = list(set(result_tracking.tracked_lead_ids))
                if len(original_leads) != len(result_tracking.tracked_lead_ids):
                    corrections_made.append(f"Removed {len(original_leads) - len(result_tracking.tracked_lead_ids)} duplicate leads")
                
                original_meetings = result_tracking.tracked_meeting_ids.copy()
                result_tracking.tracked_meeting_ids = list(set(result_tracking.tracked_meeting_ids))
                if len(original_meetings) != len(result_tracking.tracked_meeting_ids):
                    corrections_made.append(f"Removed {len(original_meetings) - len(result_tracking.tracked_meeting_ids)} duplicate meetings")
                
                original_opportunities = result_tracking.tracked_opportunity_ids.copy()
                result_tracking.tracked_opportunity_ids = list(set(result_tracking.tracked_opportunity_ids))
                if len(original_opportunities) != len(result_tracking.tracked_opportunity_ids):
                    corrections_made.append(f"Removed {len(original_opportunities) - len(result_tracking.tracked_opportunity_ids)} duplicate opportunities")
                
                original_deals = result_tracking.tracked_deal_ids.copy()
                result_tracking.tracked_deal_ids = list(set(result_tracking.tracked_deal_ids))
                if len(original_deals) != len(result_tracking.tracked_deal_ids):
                    corrections_made.append(f"Removed {len(original_deals) - len(result_tracking.tracked_deal_ids)} duplicate deals")
                
                # 2. Recalculer les compteurs si incohérence
                if result_tracking.leads_created_count != len(result_tracking.tracked_lead_ids):
                    old_count = result_tracking.leads_created_count
                    result_tracking.leads_created_count = len(result_tracking.tracked_lead_ids)
                    corrections_made.append(f"Fixed leads count: {old_count} -> {result_tracking.leads_created_count}")
                
                if result_tracking.meetings_secured_count != len(result_tracking.tracked_meeting_ids):
                    old_count = result_tracking.meetings_secured_count
                    result_tracking.meetings_secured_count = len(result_tracking.tracked_meeting_ids)
                    corrections_made.append(f"Fixed meetings count: {old_count} -> {result_tracking.meetings_secured_count}")
                
                if result_tracking.opportunities_created_count != len(result_tracking.tracked_opportunity_ids):
                    old_count = result_tracking.opportunities_created_count
                    result_tracking.opportunities_created_count = len(result_tracking.tracked_opportunity_ids)
                    corrections_made.append(f"Fixed opportunities count: {old_count} -> {result_tracking.opportunities_created_count}")
                
                if result_tracking.deals_closed_count != len(result_tracking.tracked_deal_ids):
                    old_count = result_tracking.deals_closed_count
                    result_tracking.deals_closed_count = len(result_tracking.tracked_deal_ids)
                    corrections_made.append(f"Fixed deals count: {old_count} -> {result_tracking.deals_closed_count}")
                
                # 3. Corriger les valeurs négatives
                if result_tracking.pipeline_value_created < 0:
                    result_tracking.pipeline_value_created = 0
                    corrections_made.append("Fixed negative pipeline value")
                
                if result_tracking.revenue_generated < 0:
                    result_tracking.revenue_generated = 0
                    corrections_made.append("Fixed negative revenue")
                
                # Sauvegarder seulement si corrections apportées
                if corrections_made:
                    result_tracking.save()
                    
                    if not silent:
                        print(f"Auto-corrections applied to campaign {result_tracking.campaign.id}: {'; '.join(corrections_made)}")
                
        except Exception as e:
            if not silent:
                print(f"Auto-validation failed for campaign {result_tracking.campaign.id}: {str(e)}")
    

    # === MÉTHODES UTILITAIRES POUR LE MVP ===
    
    @classmethod
    def get_campaign_metrics(cls, campaign: Campaign) -> dict:
        """Récupérer les métriques d'une campagne (version MVP)"""
        try:
            result_tracking = cls.get_or_create_result_tracking(campaign)

            cls._auto_validate_and_clean(result_tracking, silent=True)
            
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

                # Auto-validation complète (non-silencieuse pour ce cas)
                cls._auto_validate_and_clean(result_tracking, silent=False)
                cleanup_actions.append("Applied auto-validation corrections")

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