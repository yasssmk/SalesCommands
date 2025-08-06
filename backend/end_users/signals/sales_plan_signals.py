# apps/end_users/signals/sales_plan_signals.py

"""
Signal handlers pour la mise à jour automatique des Sales Plans et Milestones.
Architecture temps réel : toute modification CRM déclenche recalcul automatique.

VERSION SÉCURISÉE avec :
- Validation client_id stricte pour éviter fuites entre clients
- Limitation des plans traités pour éviter surcharge système
- Gestion d'erreur robuste pour environnement de développement
- Conservation des méthodes de debug et utilities

Déclencheurs :
- Opportunity.save() / delete() → Impact pipeline, closed_won
- Lead.save() / delete() → Impact leads_count
- Activity.save() / delete() (meetings) → Impact meetings_count  
- Campaign.save() / delete() → Impact objectifs liés
"""

import logging
from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from django.db import transaction
from django.utils import timezone
from django.core.cache import cache
from datetime import date
from decimal import Decimal
from typing import Set, List

# Models imports
from apps.opportunities.models import Opportunity
from apps.leads.models import Lead
from apps.activities.models import Activity
from apps.campaign.models import Campaign
from end_users.models import SalesPlan, SalesMilestone

logger = logging.getLogger(__name__)

# =========================================================================
# CONFIGURATION SÉCURISÉE ET HELPERS
# =========================================================================

class SalesPlanSignalConfig:
    """Configuration centralisée pour les signaux Sales Plan - VERSION SÉCURISÉE"""
    
    # Types d'activités qui impactent les meetings
    MEETING_ACTIVITY_TYPES = ['MEETING', 'CALL', 'VIDEO_CALL']
    
    # Mapping opportunité status → impact sur métriques
    OPPORTUNITY_STATUS_MAPPING = {
        'WON': 'closed_won',
        'LOST': None,  # Pas d'impact sur closed_won
        'OPEN': 'pipeline'  # Impact sur pipeline
    }
    
    # SÉCURITÉ: Limitations pour éviter surcharge et fuites
    MAX_PLANS_TO_UPDATE = 20  # Réduit de 50 à 20 pour sécurité
    BATCH_PROCESSING_SIZE = 5
    MAX_SIGNAL_PROCESSING_TIME = 30  # secondes
    
    # Cache pour éviter processing parallèle
    SIGNAL_PROCESSING_CACHE_PREFIX = "sales_plan_signal"
    SIGNAL_PROCESSING_TIMEOUT = 300  # 5 minutes
    
    @classmethod
    def get_cache_key(cls, client_id: str, trigger_type: str) -> str:
        """Génère clé cache pour éviter processing parallèle"""
        return f"{cls.SIGNAL_PROCESSING_CACHE_PREFIX}:{client_id}:{trigger_type}"


def get_affected_users_from_opportunity(opportunity) -> Set[int]:
    """
    SÉCURISÉ: Identifie les utilisateurs dont les Sales Plans peuvent être affectés 
    par les changements d'une opportunité.
    
    Ajoute validation client_id pour éviter fuites entre clients.
    """
    affected_users = set()
    
    # SÉCURITÉ: Vérification client_id avant tout traitement
    if not hasattr(opportunity, 'client_id') or not opportunity.client_id:
        logger.warning(f"Opportunity {opportunity.id} has no client_id - skipping")
        return affected_users
    
    try:
        # Propriétaire de l'opportunité (deal_owner au lieu d'assigned_to)
        if hasattr(opportunity, 'deal_owner') and opportunity.deal_owner:
            # SÉCURITÉ: Vérifier que le deal_owner appartient au même client
            if hasattr(opportunity.deal_owner, 'client_id') and str(opportunity.deal_owner.client_id) == str(opportunity.client_id):
                affected_users.add(opportunity.deal_owner.id)
            else:
                logger.warning(f"Deal owner client_id mismatch for opportunity {opportunity.id}")
        
        # Créateur de l'opportunité
        if hasattr(opportunity, 'created_by') and opportunity.created_by:
            # SÉCURITÉ: Vérifier que le créateur appartient au même client
            if hasattr(opportunity.created_by, 'client_id') and str(opportunity.created_by.client_id) == str(opportunity.client_id):
                affected_users.add(opportunity.created_by.id)
        
        # Utilisateurs de l'account lié (team members) - avec validation
        if hasattr(opportunity, 'account') and opportunity.account:
            # SÉCURITÉ: Vérifier que l'account appartient au même client
            if hasattr(opportunity.account, 'client_id') and str(opportunity.account.client_id) == str(opportunity.client_id):
                try:
                    account_users = opportunity.account.get_team_members()
                    # Double vérification : chaque utilisateur doit avoir le bon client_id
                    for user in account_users:
                        if hasattr(user, 'client_id') and str(user.client_id) == str(opportunity.client_id):
                            affected_users.add(user.id)
                except AttributeError:
                    # get_team_members() peut ne pas exister
                    logger.debug(f"Account {opportunity.account.id} has no get_team_members method")
                    pass
    
    except Exception as e:
        logger.error(f"Error getting affected users from opportunity {opportunity.id}: {e}")
    
    logger.debug(f"Found {len(affected_users)} affected users for opportunity {opportunity.id}")
    return affected_users


def get_affected_users_from_lead(lead) -> Set[int]:
    """
    SÉCURISÉ: Identifie les utilisateurs dont les Sales Plans peuvent être affectés 
    par les changements d'un lead.
    """
    affected_users = set()
    
    # SÉCURITÉ: Vérification client_id
    if not hasattr(lead, 'client_id') or not lead.client_id:
        logger.warning(f"Lead {lead.id} has no client_id - skipping")
        return affected_users
    
    try:
        # Assigné du lead
        if hasattr(lead, 'assigned_to') and lead.assigned_to:
            if hasattr(lead.assigned_to, 'client_id') and str(lead.assigned_to.client_id) == str(lead.client_id):
                affected_users.add(lead.assigned_to.id)
        
        # Créateur du lead
        if hasattr(lead, 'created_by') and lead.created_by:
            if hasattr(lead.created_by, 'client_id') and str(lead.created_by.client_id) == str(lead.client_id):
                affected_users.add(lead.created_by.id)
    
    except Exception as e:
        logger.error(f"Error getting affected users from lead {lead.id}: {e}")
    
    return affected_users


def get_affected_users_from_activity(activity) -> Set[int]:
    """
    SÉCURISÉ: Identifie les utilisateurs dont les Sales Plans peuvent être affectés 
    par les changements d'une activité (meeting).
    """
    affected_users = set()
    
    # SÉCURITÉ: Vérification client_id
    if not hasattr(activity, 'client_id') or not activity.client_id:
        logger.warning(f"Activity {activity.id} has no client_id - skipping")
        return affected_users
    
    try:
        # Assigné de l'activité
        if hasattr(activity, 'assigned_to') and activity.assigned_to:
            if hasattr(activity.assigned_to, 'client_id') and str(activity.assigned_to.client_id) == str(activity.client_id):
                affected_users.add(activity.assigned_to.id)
        
        # Créateur de l'activité
        if hasattr(activity, 'created_by') and activity.created_by:
            if hasattr(activity.created_by, 'client_id') and str(activity.created_by.client_id) == str(activity.client_id):
                affected_users.add(activity.created_by.id)
        
        # Participants (si relation M2M existe) - avec validation
        if hasattr(activity, 'participants'):
            try:
                for participant in activity.participants.all():
                    if hasattr(participant, 'client_id') and str(participant.client_id) == str(activity.client_id):
                        affected_users.add(participant.id)
            except Exception as e:
                logger.debug(f"Error accessing activity participants: {e}")
    
    except Exception as e:
        logger.error(f"Error getting affected users from activity {activity.id}: {e}")
    
    return affected_users


def get_active_sales_plans_for_users_secure(user_ids: Set[int], client_id: str) -> List['SalesPlan']:
    """
    SÉCURISÉ: Récupère les Sales Plans actifs pour les utilisateurs donnés.
    
    Ajoute validation client_id stricte et limitation pour éviter surcharge.
    """
    if not user_ids or not client_id:
        return []
    
    today = date.today()
    
    try:
        # SÉCURITÉ: Double filtrage client_id (plan ET utilisateur)
        plans = SalesPlan.objects.select_related('quota', 'user').filter(
            user_id__in=user_ids,
            client_id=client_id,  # SÉCURITÉ: plan appartient au bon client
            user__client_id=client_id,  # DOUBLE VÉRIFICATION: user appartient au bon client
            status__in=[SalesPlan.Status.ACTIVE, SalesPlan.Status.DRAFT],
            period_start__lte=today,
            period_end__gte=today
        )[:SalesPlanSignalConfig.MAX_PLANS_TO_UPDATE]  # SÉCURITÉ: Limitation
        
        plans_list = list(plans)
        logger.debug(f"Found {len(plans_list)} secure active plans for client {client_id}")
        return plans_list
    
    except Exception as e:
        logger.error(f"Error getting active sales plans for client {client_id}: {e}")
        return []


def update_milestones_for_plans_secure(sales_plans: List['SalesPlan'], trigger_source: str):
    """
    SÉCURISÉ: Met à jour les milestones pour une liste de Sales Plans.
    
    Ajoute gestion d'erreur robuste et traitement par batch.
    """
    if not sales_plans:
        return
    
    updated_count = 0
    error_count = 0
    
    # Validation finale de sécurité : tous les plans doivent avoir le même client_id
    client_ids = set(str(plan.client_id) for plan in sales_plans)
    if len(client_ids) > 1:
        logger.error(f"SECURITY BREACH PREVENTED: Mixed client_ids in plans: {client_ids}")
        return
    
    client_id = client_ids.pop() if client_ids else None
    if not client_id:
        logger.error("No valid client_id found in sales plans")
        return
    
    # Cache pour éviter processing parallèle
    cache_key = SalesPlanSignalConfig.get_cache_key(client_id, trigger_source)
    if cache.get(cache_key):
        logger.info(f"Skipping milestone update - already in progress for {client_id}")
        return
    
    try:
        # Marquer processing en cours
        cache.set(cache_key, True, SalesPlanSignalConfig.SIGNAL_PROCESSING_TIMEOUT)
        
        # Traitement par batch pour éviter surcharge
        for i in range(0, len(sales_plans), SalesPlanSignalConfig.BATCH_PROCESSING_SIZE):
            batch = sales_plans[i:i + SalesPlanSignalConfig.BATCH_PROCESSING_SIZE]
            
            with transaction.atomic():
                for plan in batch:
                    # Vérification finale client_id
                    if str(plan.client_id) != client_id:
                        logger.error(f"SECURITY: Plan {plan.id} client_id mismatch - skipping")
                        continue
                    
                    try:
                        # Récupérer tous les milestones du plan
                        milestones = plan.milestones.all()
                        
                        for milestone in milestones:
                            try:
                                # Déclencher mise à jour via méthode du modèle
                                result = milestone.update_progress()
                                if result.get('updated', False):
                                    updated_count += 1
                                    
                                    # Log pour debugging (environnement dev)
                                    logger.debug(
                                        f"Updated milestone {milestone.id} for plan {plan.id} "
                                        f"(trigger: {trigger_source})"
                                    )
                            
                            except Exception as e:
                                error_count += 1
                                logger.error(
                                    f"Failed to update milestone {milestone.id}: {str(e)}"
                                )
                                # Continue avec les autres milestones (tolérance d'erreur dev)
                                continue
                    
                    except Exception as e:
                        error_count += 1
                        logger.error(f"Failed to process plan {plan.id}: {str(e)}")
                        continue
    
    except Exception as e:
        error_count += 1
        logger.error(f"Transaction failed for milestone updates: {str(e)}")
    
    finally:
        # Libérer le cache
        cache.delete(cache_key)
    
    # Log final pour monitoring
    if updated_count > 0 or error_count > 0:
        logger.info(
            f"Milestone updates completed - Updated: {updated_count}, Errors: {error_count} "
            f"(trigger: {trigger_source}, client: {client_id})"
        )


# =========================================================================
# SIGNAL HANDLERS - OPPORTUNITIES (SÉCURISÉS)
# =========================================================================

@receiver(pre_save, sender=Opportunity)
def store_opportunity_old_values(sender, instance, **kwargs):
    """
    Stocke les anciennes valeurs avant mise à jour pour détecter changements.
    INCHANGÉ - pas de risque sécurité.
    """
    if instance.pk:
        try:
            old_instance = Opportunity.objects.get(pk=instance.pk)
            instance._old_amount = getattr(old_instance, 'amount', Decimal('0.00'))
            instance._old_status = old_instance.status
            instance._old_deal_owner = getattr(old_instance, 'deal_owner', None)  # Corrigé: deal_owner au lieu d'assigned_to
        except Opportunity.DoesNotExist:
            instance._old_amount = Decimal('0.00')
            instance._old_status = None
            instance._old_deal_owner = None
    else:
        instance._old_amount = Decimal('0.00')
        instance._old_status = None
        instance._old_deal_owner = None


@receiver(post_save, sender=Opportunity)
def update_sales_plans_on_opportunity_change(sender, instance, created, **kwargs):
    """
    SÉCURISÉ: Met à jour les Sales Plans quand une opportunité change.
    
    Ajoute validation client_id stricte et gestion d'erreur robuste.
    """
    try:
        # SÉCURITÉ: Vérification client_id immédiate
        if not hasattr(instance, 'client_id') or not instance.client_id:
            logger.warning(f"Opportunity {instance.id} has no client_id - skipping signal")
            return
        
        client_id = str(instance.client_id)
        
        # Déterminer si mise à jour nécessaire
        update_needed = False
        trigger_reason = []
        
        if created:
            update_needed = True
            trigger_reason.append("new_opportunity")
        else:
            # Vérifier changements significatifs
            if hasattr(instance, '_old_amount'):
                if getattr(instance, 'amount', Decimal('0.00')) != instance._old_amount:
                    update_needed = True
                    trigger_reason.append("amount_changed")
            
            if hasattr(instance, '_old_status'):
                if instance.status != instance._old_status:
                    update_needed = True
                    trigger_reason.append("status_changed")
            
            if hasattr(instance, '_old_deal_owner'):
                if getattr(instance, 'deal_owner', None) != instance._old_deal_owner:
                    update_needed = True
                    trigger_reason.append("assignment_changed")
        
        if not update_needed:
            logger.debug(f"No significant changes for opportunity {instance.id} - skipping")
            return
        
        # Identifier utilisateurs affectés (avec validation client_id)
        affected_users = get_affected_users_from_opportunity(instance)
        
        if not affected_users:
            logger.debug(f"No affected users found for opportunity {instance.id}")
            return
        
        # Récupérer Sales Plans actifs (avec validation client_id stricte)
        active_plans = get_active_sales_plans_for_users_secure(affected_users, client_id)
        
        # Déclencher mise à jour sécurisée
        trigger_source = f"opportunity_{instance.id}_{'+'.join(trigger_reason)}"
        update_milestones_for_plans_secure(active_plans, trigger_source)
    
    except Exception as e:
        # Tolérance d'erreur pour environnement dev
        logger.error(f"Sales plan opportunity signal failed for opportunity {instance.id}: {e}")


@receiver(post_delete, sender=Opportunity)
def update_sales_plans_on_opportunity_delete(sender, instance, **kwargs):
    """
    SÉCURISÉ: Met à jour les Sales Plans quand une opportunité est supprimée.
    """
    try:
        # SÉCURITÉ: Vérification client_id
        if not hasattr(instance, 'client_id') or not instance.client_id:
            logger.warning(f"Deleted opportunity {instance.id} had no client_id")
            return
        
        client_id = str(instance.client_id)
        
        # Identifier utilisateurs affectés
        affected_users = get_affected_users_from_opportunity(instance)
        
        if not affected_users:
            return
        
        # Récupérer Sales Plans actifs
        active_plans = get_active_sales_plans_for_users_secure(affected_users, client_id)
        
        # Déclencher mise à jour
        trigger_source = f"opportunity_{instance.id}_deleted"
        update_milestones_for_plans_secure(active_plans, trigger_source)
    
    except Exception as e:
        logger.error(f"Sales plan opportunity delete signal failed: {e}")


# =========================================================================
# SIGNAL HANDLERS - LEADS (SÉCURISÉS)
# =========================================================================

@receiver(post_save, sender=Lead)
def update_sales_plans_on_lead_change(sender, instance, created, **kwargs):
    """
    SÉCURISÉ: Met à jour les Sales Plans quand un lead change.
    """
    try:
        # SÉCURITÉ: Vérification client_id
        if not hasattr(instance, 'client_id') or not instance.client_id:
            logger.warning(f"Lead {instance.id} has no client_id - skipping signal")
            return
        
        client_id = str(instance.client_id)
        
        # Identifier utilisateurs affectés
        affected_users = get_affected_users_from_lead(instance)
        
        if not affected_users:
            return
        
        # Récupérer Sales Plans actifs
        active_plans = get_active_sales_plans_for_users_secure(affected_users, client_id)
        
        # Déclencher mise à jour
        action = "created" if created else "updated"
        trigger_source = f"lead_{instance.id}_{action}"
        update_milestones_for_plans_secure(active_plans, trigger_source)
    
    except Exception as e:
        logger.error(f"Sales plan lead signal failed for lead {instance.id}: {e}")


@receiver(post_delete, sender=Lead)
def update_sales_plans_on_lead_delete(sender, instance, **kwargs):
    """
    SÉCURISÉ: Met à jour les Sales Plans quand un lead est supprimé.
    """
    try:
        # SÉCURITÉ: Vérification client_id
        if not hasattr(instance, 'client_id') or not instance.client_id:
            logger.warning(f"Deleted lead {instance.id} had no client_id")
            return
        
        client_id = str(instance.client_id)
        
        # Identifier utilisateurs affectés
        affected_users = get_affected_users_from_lead(instance)
        
        if not affected_users:
            return
        
        # Récupérer Sales Plans actifs
        active_plans = get_active_sales_plans_for_users_secure(affected_users, client_id)
        
        # Déclencher mise à jour
        trigger_source = f"lead_{instance.id}_deleted"
        update_milestones_for_plans_secure(active_plans, trigger_source)
    
    except Exception as e:
        logger.error(f"Sales plan lead delete signal failed: {e}")


# =========================================================================
# SIGNAL HANDLERS - ACTIVITIES (MEETINGS) (SÉCURISÉS)
# =========================================================================

@receiver(post_save, sender=Activity)
def update_sales_plans_on_activity_change(sender, instance, created, **kwargs):
    """
    SÉCURISÉ: Met à jour les Sales Plans quand une activité change.
    
    Ne déclenche que pour les types d'activités pertinents (meetings).
    """
    try:
        # Filtrer par type d'activité
        if not hasattr(instance, 'activity_type') or instance.activity_type not in SalesPlanSignalConfig.MEETING_ACTIVITY_TYPES:
            return
        
        # SÉCURITÉ: Vérification client_id
        if not hasattr(instance, 'client_id') or not instance.client_id:
            logger.warning(f"Activity {instance.id} has no client_id - skipping signal")
            return
        
        client_id = str(instance.client_id)
        
        # Identifier utilisateurs affectés
        affected_users = get_affected_users_from_activity(instance)
        
        if not affected_users:
            return
        
        # Récupérer Sales Plans actifs
        active_plans = get_active_sales_plans_for_users_secure(affected_users, client_id)
        
        # Déclencher mise à jour
        action = "created" if created else "updated"
        trigger_source = f"activity_{instance.activity_type}_{instance.id}_{action}"
        update_milestones_for_plans_secure(active_plans, trigger_source)
    
    except Exception as e:
        logger.error(f"Sales plan activity signal failed for activity {instance.id}: {e}")


@receiver(post_delete, sender=Activity)
def update_sales_plans_on_activity_delete(sender, instance, **kwargs):
    """
    SÉCURISÉ: Met à jour les Sales Plans quand une activité est supprimée.
    """
    try:
        # Filtrer par type d'activité
        if not hasattr(instance, 'activity_type') or instance.activity_type not in SalesPlanSignalConfig.MEETING_ACTIVITY_TYPES:
            return
        
        # SÉCURITÉ: Vérification client_id
        if not hasattr(instance, 'client_id') or not instance.client_id:
            logger.warning(f"Deleted activity {instance.id} had no client_id")
            return
        
        client_id = str(instance.client_id)
        
        # Identifier utilisateurs affectés
        affected_users = get_affected_users_from_activity(instance)
        
        if not affected_users:
            return
        
        # Récupérer Sales Plans actifs
        active_plans = get_active_sales_plans_for_users_secure(affected_users, client_id)
        
        # Déclencher mise à jour
        trigger_source = f"activity_{instance.activity_type}_{instance.id}_deleted"
        update_milestones_for_plans_secure(active_plans, trigger_source)
    
    except Exception as e:
        logger.error(f"Sales plan activity delete signal failed: {e}")


# =========================================================================
# SIGNAL HANDLERS - CAMPAIGNS (SÉCURISÉS)
# =========================================================================

@receiver(post_save, sender=Campaign)
def update_sales_plans_on_campaign_change(sender, instance, created, **kwargs):
    """
    SÉCURISÉ: Met à jour les Sales Plans quand une campagne change.
    
    Important pour les objectifs de campagne liés aux quotas.
    """
    try:
        # SÉCURITÉ: Vérification client_id
        if not hasattr(instance, 'client_id') or not instance.client_id:
            logger.warning(f"Campaign {instance.id} has no client_id - skipping signal")
            return
        
        client_id = str(instance.client_id)
        
        # Récupérer stakeholders de la campagne avec validation client_id
        affected_users = set()
        
        # Propriétaire legacy
        if hasattr(instance, 'owner') and instance.owner:
            if hasattr(instance.owner, 'client_id') and str(instance.owner.client_id) == client_id:
                affected_users.add(instance.owner.id)
        
        # Créateur
        if hasattr(instance, 'created_by') and instance.created_by:
            if hasattr(instance.created_by, 'client_id') and str(instance.created_by.client_id) == client_id:
                affected_users.add(instance.created_by.id)
        
        # Stakeholders via relation M2M (avec validation)
        try:
            stakeholders = instance.stakeholders.all()
            for stakeholder in stakeholders:
                if hasattr(stakeholder, 'client_id') and str(stakeholder.client_id) == client_id:
                    affected_users.add(stakeholder.id)
        except Exception as e:
            logger.debug(f"Error accessing campaign stakeholders: {e}")
        
        if not affected_users:
            return
        
        # Récupérer Sales Plans actifs
        active_plans = get_active_sales_plans_for_users_secure(affected_users, client_id)
        
        # Déclencher mise à jour
        action = "created" if created else "updated"
        trigger_source = f"campaign_{instance.id}_{action}"
        update_milestones_for_plans_secure(active_plans, trigger_source)
    
    except Exception as e:
        logger.error(f"Sales plan campaign signal failed for campaign {instance.id}: {e}")


# =========================================================================
# SIGNAL HANDLERS - SALES PLAN / MILESTONE DIRECT (INCHANGÉS)
# =========================================================================

@receiver(post_save, sender=SalesPlan)
def update_milestones_on_plan_save(sender, instance, created, **kwargs):
    """
    Met à jour les milestones quand le plan lui-même change.
    INCHANGÉ - pas de risque sécurité car c'est interne au plan.
    """
    if created:
        # Nouveau plan : pas besoin de recalculer immédiatement
        return
    
    # Plan existant modifié : mettre à jour tous ses milestones
    try:
        milestones = instance.milestones.all()
        for milestone in milestones:
            milestone.update_progress()
        
        logger.debug(f"Updated all milestones for modified plan {instance.id}")
    
    except Exception as e:
        logger.error(f"Failed to update milestones for plan {instance.id}: {str(e)}")


@receiver(post_save, sender=SalesMilestone)
def update_milestone_on_direct_save(sender, instance, created, **kwargs):
    """
    Met à jour un milestone spécifique quand il est modifié directement.
    INCHANGÉ - pas de risque sécurité car c'est interne au milestone.
    """
    if created:
        # Nouveau milestone : calculer valeur initiale
        try:
            instance.update_progress()
        except Exception as e:
            logger.error(f"Failed initial update for new milestone {instance.id}: {str(e)}")
    else:
        # Milestone existant : optionnel car déjà géré par les autres signaux
        pass


# =========================================================================
# UTILITIES POUR DEBUG ET DÉVELOPPEMENT (CONSERVÉES)
# =========================================================================

def trigger_manual_update_for_user(user_id: int, client_id: str, reason: str = "manual_trigger"):
    """
    SÉCURISÉ: Fonction utilitaire pour déclencher manuellement une mise à jour.
    
    Utile pour debugging ou correction ponctuelle en développement.
    Ajoute validation client_id pour sécurité.
    """
    try:
        if not client_id:
            logger.error("client_id required for manual trigger")
            return 0
        
        active_plans = get_active_sales_plans_for_users_secure({user_id}, client_id)
        update_milestones_for_plans_secure(active_plans, f"manual_{reason}")
        
        logger.info(f"Manual trigger executed for user {user_id}, client {client_id}: {len(active_plans)} plans updated")
        return len(active_plans)
    
    except Exception as e:
        logger.error(f"Manual trigger failed for user {user_id}: {e}")
        return 0


def get_signal_statistics(client_id: str = None):
    """
    SÉCURISÉ: Fonction utilitaire pour obtenir des statistiques sur les signaux.
    
    Utile pour monitoring en développement.
    Ajoute filtrage par client_id pour sécurité.
    """
    today = date.today()
    
    try:
        base_filter = {}
        if client_id:
            base_filter['client_id'] = client_id
        
        stats = {
            'active_sales_plans': SalesPlan.objects.filter(
                status=SalesPlan.Status.ACTIVE,
                period_start__lte=today,
                period_end__gte=today,
                **base_filter
            ).count(),
            'total_milestones': SalesMilestone.objects.filter(**base_filter).count(),
            'overdue_milestones': SalesMilestone.objects.filter(
                target_date__lt=today,
                status__in=['PENDING', 'IN_PROGRESS'],
                **base_filter
            ).count()
        }
        
        if client_id:
            stats['client_id'] = client_id
        
        return stats
    
    except Exception as e:
        logger.error(f"Error getting signal statistics: {e}")
        return {'error': str(e)}


def debug_affected_users_for_opportunity(opportunity_id: int):
    """
    NOUVEAU: Fonction debug pour tester identification utilisateurs affectés
    """
    try:
        opportunity = Opportunity.objects.get(id=opportunity_id)
        affected_users = get_affected_users_from_opportunity(opportunity)
        
        return {
            'opportunity_id': opportunity_id,
            'client_id': str(opportunity.client_id) if hasattr(opportunity, 'client_id') else None,
            'affected_user_ids': list(affected_users),
            'affected_users_count': len(affected_users)
        }
    except Opportunity.DoesNotExist:
        return {'error': 'Opportunity not found'}
    except Exception as e:
        return {'error': str(e)}


def debug_active_plans_for_client(client_id: str):
    """
    NOUVEAU: Fonction debug pour voir tous les plans actifs d'un client
    """
    try:
        today = date.today()
        
        plans = SalesPlan.objects.filter(
            client_id=client_id,
            status__in=[SalesPlan.Status.ACTIVE, SalesPlan.Status.DRAFT],
            period_start__lte=today,
            period_end__gte=today
        ).select_related('user', 'quota')
        
        return {
            'client_id': client_id,
            'total_active_plans': plans.count(),
            'plans': [
                {
                    'id': plan.id,
                    'user': plan.user.email if plan.user else None,
                    'status': plan.status,
                    'period': f"{plan.period_start} to {plan.period_end}"
                }
                for plan in plans
            ]
        }
    except Exception as e:
        return {'error': str(e)}