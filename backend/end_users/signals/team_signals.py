# backend/end_users/signals/team_signals.py

from django.db.models.signals import post_save, pre_save, pre_delete
from django.dispatch import receiver
from django.db import transaction
from end_users.models import Team, User
import logging

# Import robuste de get_correlation_id
try:
    from backend.core.logging.context import get_correlation_id
except ImportError:
    try:
        from core.logging.context import get_correlation_id
    except ImportError:
        def get_correlation_id():
            return '-'

logger = logging.getLogger(__name__)

# Cache pour stocker l'ancien manager (clé: instance.pk)
_old_managers = {}


@receiver(pre_save, sender=Team)
def capture_old_manager(sender, instance, **kwargs):
    """
    Capture l'ancien manager AVANT la sauvegarde.
    Stocké dans _old_managers dict pour utilisation dans post_save.
    """
    # Skip si nouveau (pas encore de pk)
    if not instance.pk:
        return
    
    # Skip during bulk operations
    from core.cache_utils import are_signals_disabled
    if are_signals_disabled():
        return
    
    try:
        old_instance = Team.objects.get(pk=instance.pk)
        _old_managers[instance.pk] = old_instance.manager_id
    except Team.DoesNotExist:
        _old_managers[instance.pk] = None


@receiver(post_save, sender=Team)
def sync_manager_team_assignment(sender, instance, created, **kwargs):
    """
    Automatically assign user.team when a user becomes manager of a team.
    
    Business Rules:
    - If user becomes manager of team X → user.team = X
    - If manager is removed from team → user.team = None (if no other managed teams)
    - Prevents infinite loops with _skip_team_signal flag
    - Skips if signals are disabled (bulk operations)
    
    Triggers on:
    - Team creation with manager
    - Team manager update
    """
    
    # Skip if signal recursion prevention flag is set
    if hasattr(instance, '_skip_team_signal'):
        return
    
    # Skip during bulk operations
    from core.cache_utils import are_signals_disabled
    if are_signals_disabled():
        return
    
    try:
        current_manager_id = instance.manager_id
        old_manager_id = _old_managers.pop(instance.pk, None) if not created else None
        
        # Rien à faire si le manager n'a pas changé
        if not created and old_manager_id == current_manager_id:
            return
        
        # === TRAITER L'ANCIEN MANAGER (si update) ===
        if not created and old_manager_id and old_manager_id != current_manager_id:
            try:
                old_manager = User.objects.get(pk=old_manager_id)
                
                # Vérifier si l'ancien manager gère d'autres équipes
                other_managed_teams = Team.objects.filter(
                    manager_id=old_manager_id,
                    client_account=old_manager.client_account
                ).exclude(id=instance.id).exists()
                
                # Retirer l'affectation team SEULEMENT si plus d'équipes gérées
                if not other_managed_teams and old_manager.team_id == instance.id:
                    old_manager._skip_team_signal = True
                    old_manager.team = None
                    old_manager.save(update_fields=['team', 'updated_at'])
                    
                    logger.info("manager_team_removed", extra={
                        'correlation_id': get_correlation_id(),
                        'user_id': str(old_manager.id),
                        'user_email': old_manager.email[:3] + '***',
                        'team_id': str(instance.id),
                        'team_name': instance.name,
                        'event': 'manager_team_sync',
                        'reason': 'manager_changed'
                    })
                    
            except User.DoesNotExist:
                pass
        
        # === TRAITER LE NOUVEAU MANAGER ===
        if current_manager_id:
            try:
                new_manager = User.objects.get(pk=current_manager_id)
                
                # Assigner l'équipe au nouveau manager si pas déjà fait
                if new_manager.team_id != instance.id:
                    new_manager._skip_team_signal = True
                    new_manager.team = instance
                    new_manager.save(update_fields=['team', 'updated_at'])
                    
                    logger.info("manager_team_assigned", extra={
                        'correlation_id': get_correlation_id(),
                        'user_id': str(new_manager.id),
                        'user_email': new_manager.email[:3] + '***',
                        'team_id': str(instance.id),
                        'team_name': instance.name,
                        'client_id': str(instance.client_account_id),
                        'event': 'manager_team_sync',
                        'reason': 'manager_assigned'
                    })
                    
            except User.DoesNotExist:
                logger.warning("manager_not_found", extra={
                    'correlation_id': get_correlation_id(),
                    'manager_id': str(current_manager_id),
                    'team_id': str(instance.id),
                    'event': 'manager_team_sync_error'
                })
                
    except Exception as e:
        logger.error("manager_team_sync_failed", extra={
            'correlation_id': get_correlation_id(),
            'team_id': str(instance.id),
            'team_name': instance.name,
            'error': str(e),
            'event': 'manager_team_sync_error'
        }, exc_info=True)


@receiver(pre_delete, sender=Team)
def cleanup_manager_team_on_delete(sender, instance, **kwargs):
    """
    Remove team assignment from manager when team is deleted.
    
    Business Rule:
    - If team is deleted and manager.team == this team → set manager.team = None
    
    Triggers on:
    - Team deletion
    """
    
    # Skip if signal recursion prevention flag is set
    if hasattr(instance, '_skip_team_signal'):
        return
    
    # Skip during bulk operations
    from core.cache_utils import are_signals_disabled
    if are_signals_disabled():
        return
    
    if not instance.manager:
        return
    
    try:
        manager = instance.manager
        
        # Only update if manager's current team is this team
        if manager.team_id == instance.id:
            manager._skip_team_signal = True
            manager.team = None
            manager.save(update_fields=['team', 'updated_at'])
            
            logger.info("manager_team_removed_on_delete", extra={
                'correlation_id': get_correlation_id(),
                'user_id': str(manager.id),
                'user_email': manager.email[:3] + '***',
                'team_id': str(instance.id),
                'team_name': instance.name,
                'event': 'manager_team_sync',
                'reason': 'team_deleted'
            })
            
    except Exception as e:
        logger.error("manager_team_cleanup_failed", extra={
            'correlation_id': get_correlation_id(),
            'team_id': str(instance.id),
            'team_name': instance.name,
            'error': str(e),
            'event': 'manager_team_cleanup_error'
        }, exc_info=True)