# apps/end_users/signals/sales_plan_signals.py

"""
Signal handlers pour la mise à jour automatique des Sales Plans et Milestones.
Architecture temps réel : toute modification CRM déclenche recalcul automatique.

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
from datetime import date
from decimal import Decimal
from typing import Set, List

# Models imports
from apps.opportunities.models import Opportunity
from apps.leads.models import Lead
from apps.activities.models import Activity
from apps.campaign.models import Campaign
from end_users.models import SalesPlan, SalesMilestone



# =========================================================================
# CONFIGURATION ET HELPERS
# =========================================================================

class SalesPlanSignalConfig:
    """Configuration centralisée pour les signaux Sales Plan"""
    
    # Types d'activités qui impactent les meetings
    MEETING_ACTIVITY_TYPES = ['MEETING', 'CALL', 'VIDEO_CALL']
    
    # Mapping opportunité status → impact sur métriques
    OPPORTUNITY_STATUS_MAPPING = {
        'WON': 'closed_won',
        'LOST': None,  # Pas d'impact sur closed_won
        'OPEN': 'pipeline'  # Impact sur pipeline
    }
    
    # Batch size pour éviter surcharge
    MAX_PLANS_TO_UPDATE = 50


def get_affected_users_from_opportunity(opportunity) -> Set[int]:
    """
    Identifie les utilisateurs dont les Sales Plans peuvent être affectés 
    par les changements d'une opportunité.
    """
    affected_users = set()
    
    # Propriétaire de l'opportunité
    if hasattr(opportunity, 'assigned_to') and opportunity.assigned_to:
        affected_users.add(opportunity.assigned_to.id)
    
    # Créateur de l'opportunité
    if hasattr(opportunity, 'created_by') and opportunity.created_by:
        affected_users.add(opportunity.created_by.id)
    
    # Utilisateurs de l'account lié (team members)
    if hasattr(opportunity, 'account') and opportunity.account:
        account_users = opportunity.account.get_team_members()
        affected_users.update([u.id for u in account_users])
    
    return affected_users


def get_affected_users_from_lead(lead) -> Set[int]:
    """
    Identifie les utilisateurs dont les Sales Plans peuvent être affectés 
    par les changements d'un lead.
    """
    affected_users = set()
    
    # Assigné du lead
    if hasattr(lead, 'assigned_to') and lead.assigned_to:
        affected_users.add(lead.assigned_to.id)
    
    # Créateur du lead
    if hasattr(lead, 'created_by') and lead.created_by:
        affected_users.add(lead.created_by.id)
    
    return affected_users


def get_affected_users_from_activity(activity) -> Set[int]:
    """
    Identifie les utilisateurs dont les Sales Plans peuvent être affectés 
    par les changements d'une activité (meeting).
    """
    affected_users = set()
    
    # Assigné de l'activité
    if hasattr(activity, 'assigned_to') and activity.assigned_to:
        affected_users.add(activity.assigned_to.id)
    
    # Créateur de l'activité
    if hasattr(activity, 'created_by') and activity.created_by:
        affected_users.add(activity.created_by.id)
    
    # Participants (si relation M2M existe)
    if hasattr(activity, 'participants'):
        affected_users.update([p.id for p in activity.participants.all()])
    
    return affected_users


def get_active_sales_plans_for_users(user_ids: Set[int]) -> List['SalesPlan']:
    """
    Récupère les Sales Plans actifs pour les utilisateurs donnés.
    Filtre par période actuelle pour optimiser.
    """
    if not user_ids:
        return []
    
    today = date.today()
    
    return list(SalesPlan.objects.select_related('quota', 'user').filter(
        user_id__in=user_ids,
        status__in=[SalesPlan.Status.ACTIVE, SalesPlan.Status.DRAFT],
        period_start__lte=today,
        period_end__gte=today
    )[:SalesPlanSignalConfig.MAX_PLANS_TO_UPDATE])


def update_milestones_for_plans(sales_plans: List['SalesPlan'], trigger_source: str):
    """
    Met à jour les milestones pour une liste de Sales Plans.
    Utilise transaction pour atomicité.
    """
    if not sales_plans:
        return
    
    updated_count = 0
    
    try:
        with transaction.atomic():
            for plan in sales_plans:
                # Récupérer tous les milestones du plan
                milestones = plan.milestones.all()
                
                for milestone in milestones:
                    try:
                        # Déclencher mise à jour via méthode du modèle
                        result = milestone.update_progress()
                        if result.get('updated', False):
                            updated_count += 1
                            
                            # Log pour debugging
                            print(
                                f"Updated milestone {milestone.id} for plan {plan.id} "
                                f"(trigger: {trigger_source})"
                            )
                    
                    except Exception as e:
                        print(
                            f"Failed to update milestone {milestone.id}: {str(e)}"
                        )
                        # Continue avec les autres milestones
                        continue
    
    except Exception as e:
        print(f"Transaction failed for milestone updates: {str(e)}")
    
    if updated_count > 0:
        print(
            f"Updated {updated_count} milestones from {trigger_source} trigger"
        )


# =========================================================================
# SIGNAL HANDLERS - OPPORTUNITIES
# =========================================================================

@receiver(pre_save, sender=Opportunity)
def store_opportunity_old_values(sender, instance, **kwargs):
    """
    Stocke les anciennes valeurs avant mise à jour pour détecter changements.
    """
    if instance.pk:
        try:
            old_instance = Opportunity.objects.get(pk=instance.pk)
            instance._old_amount = getattr(old_instance, 'amount', Decimal('0.00'))
            instance._old_status = old_instance.status
            instance._old_assigned_to = old_instance.assigned_to
        except Opportunity.DoesNotExist:
            instance._old_amount = Decimal('0.00')
            instance._old_status = None
            instance._old_assigned_to = None
    else:
        instance._old_amount = Decimal('0.00')
        instance._old_status = None
        instance._old_assigned_to = None


@receiver(post_save, sender=Opportunity)
def update_sales_plans_on_opportunity_change(sender, instance, created, **kwargs):
    """
    Met à jour les Sales Plans quand une opportunité change.
    
    Déclenche mise à jour si :
    - Nouvelle opportunité créée
    - Montant modifié
    - Statut modifié (won/lost/open)
    - Assignation modifiée
    """
    # Déterminer si mise à jour nécessaire
    update_needed = False
    trigger_reason = []
    
    if created:
        update_needed = True
        trigger_reason.append("new_opportunity")
    else:
        # Vérifier changements significatifs
        if hasattr(instance, '_old_amount'):
            if instance.amount != instance._old_amount:
                update_needed = True
                trigger_reason.append("amount_changed")
        
        if hasattr(instance, '_old_status'):
            if instance.status != instance._old_status:
                update_needed = True
                trigger_reason.append("status_changed")
        
        if hasattr(instance, '_old_assigned_to'):
            if instance.assigned_to != instance._old_assigned_to:
                update_needed = True
                trigger_reason.append("assignment_changed")
    
    if not update_needed:
        return
    
    # Identifier utilisateurs affectés
    affected_users = get_affected_users_from_opportunity(instance)
    
    # Récupérer Sales Plans actifs
    active_plans = get_active_sales_plans_for_users(affected_users)
    
    # Déclencher mise à jour
    trigger_source = f"opportunity_{instance.id}_{'+'.join(trigger_reason)}"
    update_milestones_for_plans(active_plans, trigger_source)


@receiver(post_delete, sender=Opportunity)
def update_sales_plans_on_opportunity_delete(sender, instance, **kwargs):
    """
    Met à jour les Sales Plans quand une opportunité est supprimée.
    """
    # Identifier utilisateurs affectés
    affected_users = get_affected_users_from_opportunity(instance)
    
    # Récupérer Sales Plans actifs
    active_plans = get_active_sales_plans_for_users(affected_users)
    
    # Déclencher mise à jour
    trigger_source = f"opportunity_{instance.id}_deleted"
    update_milestones_for_plans(active_plans, trigger_source)


# =========================================================================
# SIGNAL HANDLERS - LEADS
# =========================================================================

@receiver(post_save, sender=Lead)
def update_sales_plans_on_lead_change(sender, instance, created, **kwargs):
    """
    Met à jour les Sales Plans quand un lead change.
    
    Déclenche mise à jour si :
    - Nouveau lead créé
    - Statut modifié (qualified/disqualified)
    - Assignation modifiée
    """
    # Pour MVP, on déclenche sur toute modification
    # (optimisation future : détecter changements spécifiques)
    
    # Identifier utilisateurs affectés
    affected_users = get_affected_users_from_lead(instance)
    
    # Récupérer Sales Plans actifs
    active_plans = get_active_sales_plans_for_users(affected_users)
    
    # Déclencher mise à jour
    action = "created" if created else "updated"
    trigger_source = f"lead_{instance.id}_{action}"
    update_milestones_for_plans(active_plans, trigger_source)


@receiver(post_delete, sender=Lead)
def update_sales_plans_on_lead_delete(sender, instance, **kwargs):
    """
    Met à jour les Sales Plans quand un lead est supprimé.
    """
    # Identifier utilisateurs affectés
    affected_users = get_affected_users_from_lead(instance)
    
    # Récupérer Sales Plans actifs
    active_plans = get_active_sales_plans_for_users(affected_users)
    
    # Déclencher mise à jour
    trigger_source = f"lead_{instance.id}_deleted"
    update_milestones_for_plans(active_plans, trigger_source)


# =========================================================================
# SIGNAL HANDLERS - ACTIVITIES (MEETINGS)
# =========================================================================

@receiver(post_save, sender=Activity)
def update_sales_plans_on_activity_change(sender, instance, created, **kwargs):
    """
    Met à jour les Sales Plans quand une activité change.
    
    Ne déclenche que pour les types d'activités pertinents (meetings).
    """
    # Filtrer par type d'activité
    if instance.activity_type not in SalesPlanSignalConfig.MEETING_ACTIVITY_TYPES:
        return
    
    # Identifier utilisateurs affectés
    affected_users = get_affected_users_from_activity(instance)
    
    # Récupérer Sales Plans actifs
    active_plans = get_active_sales_plans_for_users(affected_users)
    
    # Déclencher mise à jour
    action = "created" if created else "updated"
    trigger_source = f"activity_{instance.activity_type}_{instance.id}_{action}"
    update_milestones_for_plans(active_plans, trigger_source)


@receiver(post_delete, sender=Activity)
def update_sales_plans_on_activity_delete(sender, instance, **kwargs):
    """
    Met à jour les Sales Plans quand une activité est supprimée.
    """
    # Filtrer par type d'activité
    if instance.activity_type not in SalesPlanSignalConfig.MEETING_ACTIVITY_TYPES:
        return
    
    # Identifier utilisateurs affectés
    affected_users = get_affected_users_from_activity(instance)
    
    # Récupérer Sales Plans actifs
    active_plans = get_active_sales_plans_for_users(affected_users)
    
    # Déclencher mise à jour
    trigger_source = f"activity_{instance.activity_type}_{instance.id}_deleted"
    update_milestones_for_plans(active_plans, trigger_source)


# =========================================================================
# SIGNAL HANDLERS - CAMPAIGNS
# =========================================================================

@receiver(post_save, sender=Campaign)
def update_sales_plans_on_campaign_change(sender, instance, created, **kwargs):
    """
    Met à jour les Sales Plans quand une campagne change.
    
    Important pour les objectifs de campagne liés aux quotas.
    """
    # Récupérer stakeholders de la campagne
    affected_users = set()
    
    # Propriétaire legacy
    if hasattr(instance, 'owner') and instance.owner:
        affected_users.add(instance.owner.id)
    
    # Stakeholders via relation M2M
    try:
        stakeholder_ids = list(instance.stakeholders.values_list('id', flat=True))
        affected_users.update(stakeholder_ids)
    except Exception:
        pass  # Relation peut ne pas être disponible immédiatement
    
    # Récupérer Sales Plans actifs
    active_plans = get_active_sales_plans_for_users(affected_users)
    
    # Déclencher mise à jour
    action = "created" if created else "updated"
    trigger_source = f"campaign_{instance.id}_{action}"
    update_milestones_for_plans(active_plans, trigger_source)


# =========================================================================
# SIGNAL HANDLERS - SALES PLAN / MILESTONE DIRECT
# =========================================================================

@receiver(post_save, sender=SalesPlan)
def update_milestones_on_plan_save(sender, instance, created, **kwargs):
    """
    Met à jour les milestones quand le plan lui-même change.
    """
    if created:
        # Nouveau plan : pas besoin de recalculer immédiatement
        return
    
    # Plan existant modifié : mettre à jour tous ses milestones
    try:
        milestones = instance.milestones.all()
        for milestone in milestones:
            milestone.update_progress()
        
        print(f"Updated all milestones for modified plan {instance.id}")
    
    except Exception as e:
        print(f"Failed to update milestones for plan {instance.id}: {str(e)}")


@receiver(post_save, sender=SalesMilestone)
def update_milestone_on_direct_save(sender, instance, created, **kwargs):
    """
    Met à jour un milestone spécifique quand il est modifié directement.
    """
    if created:
        # Nouveau milestone : calculer valeur initiale
        try:
            instance.update_progress()
        except Exception as e:
            print(f"Failed initial update for new milestone {instance.id}: {str(e)}")
    else:
        # Milestone existant : optionnel car déjà géré par les autres signaux
        pass


# =========================================================================
# UTILITIES POUR DEBUG
# =========================================================================

def trigger_manual_update_for_user(user_id: int, reason: str = "manual_trigger"):
    """
    Fonction utilitaire pour déclencher manuellement une mise à jour.
    Utile pour debugging ou correction ponctuelle.
    """
    active_plans = get_active_sales_plans_for_users({user_id})
    update_milestones_for_plans(active_plans, f"manual_{reason}")
    return len(active_plans)


def get_signal_statistics():
    """
    Fonction utilitaire pour obtenir des statistiques sur les signaux.
    Utile pour monitoring.
    """
    today = date.today()
    
    return {
        'active_sales_plans': SalesPlan.objects.filter(
            status=SalesPlan.Status.ACTIVE,
            period_start__lte=today,
            period_end__gte=today
        ).count(),
        'total_milestones': SalesMilestone.objects.count(),
        'overdue_milestones': SalesMilestone.objects.filter(
            target_date__lt=today,
            status__in=['PENDING', 'IN_PROGRESS']
        ).count()
    }