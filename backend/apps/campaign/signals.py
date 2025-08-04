# apps/campaign/signals.py

"""
Signal handlers pour l'automatisation du tracking des résultats de campagne.
Version MVP : Simple, directe, sans surcomplication.
"""

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.db import transaction
from decimal import Decimal

from apps.activities.models import Activity, ActivityCampaign
from apps.leads.models import Lead
from apps.opportunities.models import Opportunity, OpportunitySource
from apps.campaign.models import Campaign
from apps.campaign.services.campaign_tracking_service import CampaignTrackingService
from core.exceptions import StandardizedValidationError
from core.error_messages import CoreErrorMessages


# =========================================================================
# HELPER FUNCTIONS
# =========================================================================

def get_campaign_from_activity(activity):
    """
    Récupère la campagne associée à une activité.
    Vérifie via ActivityCampaign.
    """
    try:
        if hasattr(activity, 'campaign_info') and activity.campaign_info:
            return activity.campaign_info.campaign
        return None
    except Exception:
        return None


def get_campaign_from_lead(lead):
    """
    Récupère la campagne source d'un lead.
    Vérifie le champ campaign directement.
    """
    try:
        return getattr(lead, 'campaign', None)
    except Exception:
        return None


def get_campaign_from_opportunity(opportunity):
    """
    Récupère la campagne source d'une opportunité.
    Vérifie via OpportunitySource.
    """
    try:
        if hasattr(opportunity, 'source') and opportunity.source:
            return opportunity.source.source_campaign
        return None
    except Exception:
        return None


# =========================================================================
# SIGNAL HANDLERS - CRÉATION D'OBJETS
# =========================================================================

@receiver(post_save, sender=Activity)
def track_meeting_creation(sender, instance, created, **kwargs):
    """
    Track automatiquement la création de meetings liés à une campagne.
    """
    # Ne traiter que les nouvelles créations de type MEETING
    if not created or instance.activity_type != Activity.ActivityType.MEETING:
        return
    
    # Récupérer la campagne source
    campaign = get_campaign_from_activity(instance)
    if not campaign:
        return
    
    try:
        # Utiliser le service de tracking existant
        CampaignTrackingService.track_meeting_scheduled(instance, campaign)
    except Exception as e:
        # MVP : Silent fail - ne pas casser la création du meeting
        print(f"[SIGNAL] Failed to track meeting {instance.id} for campaign {campaign.id}: {str(e)}")


@receiver(post_save, sender=Lead)
def track_lead_creation(sender, instance, created, **kwargs):
    """
    Track automatiquement la création de leads liés à une campagne.
    """
    # Ne traiter que les nouvelles créations
    if not created:
        return
    
    # Récupérer la campagne source
    campaign = get_campaign_from_lead(instance)
    if not campaign:
        return
    
    try:
        # Utiliser le service de tracking existant
        CampaignTrackingService.track_lead_created(instance, campaign)
    except Exception as e:
        # MVP : Silent fail - ne pas casser la création du lead
        print(f"[SIGNAL] Failed to track lead {instance.id} for campaign {campaign.id}: {str(e)}")


@receiver(post_save, sender=Opportunity)
def track_opportunity_creation(sender, instance, created, **kwargs):
    """
    Track automatiquement la création d'opportunités liées à une campagne.
    """
    # Ne traiter que les nouvelles créations
    if not created:
        return
    
    # Récupérer la campagne source
    campaign = get_campaign_from_opportunity(instance)
    if not campaign:
        return
    
    try:
        # Récupérer le montant de l'opportunité
        amount = getattr(instance, 'amount', Decimal('0.00'))
        
        # Utiliser le service de tracking existant
        CampaignTrackingService.track_opportunity_created(instance, campaign, amount)
    except Exception as e:
        # MVP : Silent fail - ne pas casser la création de l'opportunité
        print(f"[SIGNAL] Failed to track opportunity {instance.id} for campaign {campaign.id}: {str(e)}")


# =========================================================================
# SIGNAL HANDLERS - MISE À JOUR DU PIPELINE VALUE
# =========================================================================

# Stocker l'ancienne valeur avant la sauvegarde
@receiver(pre_save, sender=Opportunity)
def store_old_opportunity_amount(sender, instance, **kwargs):
    """
    Stocke l'ancienne valeur de l'opportunité avant la mise à jour.
    """
    if instance.pk:
        try:
            old_instance = Opportunity.objects.get(pk=instance.pk)
            instance._old_amount = getattr(old_instance, 'amount', Decimal('0.00'))
            instance._old_status = old_instance.status
        except Opportunity.DoesNotExist:
            instance._old_amount = Decimal('0.00')
            instance._old_status = None
    else:
        instance._old_amount = Decimal('0.00')
        instance._old_status = None


@receiver(post_save, sender=Opportunity)
def track_opportunity_updates(sender, instance, created, **kwargs):
    """
    Track automatiquement les mises à jour du pipeline value et revenue.
    Logique simplifiée : update_opportunity_amount gère maintenant les statuts.
    """
    # Skip si création (déjà géré par track_opportunity_creation)
    if created:
        return
    
    # Récupérer la campagne source
    campaign = get_campaign_from_opportunity(instance)
    if not campaign:
        return
    
    try:
        # Récupérer les anciennes et nouvelles valeurs
        old_amount = getattr(instance, '_old_amount', Decimal('0.00'))
        new_amount = getattr(instance, 'amount', Decimal('0.00'))
        old_status = getattr(instance, '_old_status', None)
        new_status = instance.status
        
        # Toujours appeler update_opportunity_amount car elle gère les statuts
        # Elle retirera automatiquement du pipeline si CLOSED_WON ou CLOSED_LOST
        CampaignTrackingService.update_opportunity_amount(
            instance, 
            campaign, 
            old_amount, 
            new_amount
        )
        
        # Si passage à CLOSED_WON, tracker le revenue
        if new_status == Opportunity.OpportunityStatus.CLOSED_WON and old_status != new_status:
            CampaignTrackingService.track_deal_closed(instance, campaign, new_amount)
            
    except Exception as e:
        # MVP : Silent fail - ne pas casser la mise à jour de l'opportunité
        print(f"[SIGNAL] Failed to track opportunity update {instance.id} for campaign {campaign.id}: {str(e)}")


# =========================================================================
# CONFIGURATION DES SIGNAUX
# =========================================================================

def ready():
    """
    Appelé par AppConfig pour s'assurer que les signaux sont enregistrés.
    """
    # Les signaux sont automatiquement enregistrés via @receiver
    pass