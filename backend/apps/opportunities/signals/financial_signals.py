# apps/opportunities/signals/financial_signals.py

import logging
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from core.exceptions import StandardizedValidationError
from ..models import OpportunityLineItem, Opportunity, OpportunityFinancialSummary




@receiver(post_save, sender=OpportunityLineItem)
def update_financials_on_line_item_save(sender, instance, created, **kwargs):
    """
    Automatiquement mettre à jour les totaux financiers quand un line item est créé/modifié
    """
    try:
        instance.opportunity.update_financials()
        
        # Créer entrée d'historique pour traçabilité
        action = "Added" if created else "Updated"
        instance.opportunity.create_history_entry(
            'CUSTOM',
            f"{action} line item: {instance.product.product_name} ({instance.quantity}x)"
        )
        
    except Exception as e:
        print(f"Error updating financials for opportunity {instance.opportunity.id}: {str(e)}")
        # Ne pas faire échouer la transaction principale


@receiver(post_delete, sender=OpportunityLineItem)
def update_financials_on_line_item_delete(sender, instance, **kwargs):
    """
    Automatiquement mettre à jour les totaux financiers quand un line item est supprimé
    """
    try:
        # L'instance existe encore pendant post_delete
        instance.opportunity.update_financials()
        
        # Créer entrée d'historique
        instance.opportunity.create_history_entry(
            'CUSTOM',
            f"Removed line item: {instance.product.product_name}"
        )
        
    except Exception as e:
        print(f"Error updating financials after deletion for opportunity {instance.opportunity.id}: {str(e)}")
        # Ne pas faire échouer la transaction principale


@receiver(post_save, sender=Opportunity)
def create_financial_summary_on_opportunity_create(sender, instance, created, **kwargs):
    """
    Automatiquement créer un financial summary quand une opportunité est créée
    """
    if created:
        try:
            # Créer financial summary si il n'existe pas
            OpportunityFinancialSummary.objects.get_or_create(
                opportunity=instance,
                defaults={
                    'client_id': instance.client_id,
                    'probability': 0,
                    'forecast_category': OpportunityFinancialSummary.ForecastCategory.PIPELINE
                }
            )
            
        except Exception as e:
            print(f"Error creating financial summary for opportunity {instance.id}: {str(e)}")
            # Ne pas faire échouer la création de l'opportunité


@receiver(post_save, sender=Opportunity)
def update_financial_summary_on_status_change(sender, instance, created, **kwargs):
    """
    Automatiquement mettre à jour forecast_category basé sur le statut de l'opportunité
    """
    if not created and hasattr(instance, 'financial_summary'):
        try:
            summary = instance.financial_summary
            
            # Mapper les statuts vers les forecast categories
            status_to_forecast = {
                Opportunity.OpportunityStatus.WON: OpportunityFinancialSummary.ForecastCategory.CLOSED_WON,
                Opportunity.OpportunityStatus.LOST: OpportunityFinancialSummary.ForecastCategory.CLOSED_LOST,
            }
            
            # Mettre à jour si nécessaire
            if instance.status in status_to_forecast:
                new_category = status_to_forecast[instance.status]
                if summary.forecast_category != new_category:
                    summary.forecast_category = new_category
                    
                    # Ajuster probabilité selon le statut
                    if instance.status == Opportunity.OpportunityStatus.WON:
                        summary.probability = 100
                    elif instance.status == Opportunity.OpportunityStatus.LOST:
                        summary.probability = 0
                    
                    summary.save()
                    
                    # Historique
                    instance.create_history_entry(
                        'STATUS_CHANGE',
                        f"Status changed to {instance.get_status_display()}, forecast updated to {summary.get_forecast_category_display()}"
                    )
            
        except Exception as e:
            print(f"Error updating forecast category for opportunity {instance.id}: {str(e)}")
