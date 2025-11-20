# backend/end_users/signals/team_signals.py

from django.db.models.signals import post_save, pre_delete
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
    
    # Only process if team has a manager
    if not instance.manager:
        return
    
    try:
        # Get the manager user
        manager = instance.manager
        
        # Check if manager changed (for updates)
        if not created and instance.pk:
            try:
                old_instance = Team.objects.get(pk=instance.pk)
                old_manager = old_instance.manager
                
                # Manager didn't change, nothing to do
                if old_manager and old_manager.id == manager.id:
                    return
                
                # Remove team assignment from old manager if they have no other managed teams
                if old_manager:
                    other_managed_teams = Team.objects.filter(
                        manager=old_manager,
                        client_account=old_manager.client_account
                    ).exclude(id=instance.id).exists()
                    
                    if not other_managed_teams and old_manager.team_id == instance.id:
                        old_manager._skip_team_signal = True
                        old_manager.team = None
                        old_manager.save(update_fields=['team', 'updated_at'])
                        delattr(old_manager, '_skip_team_signal')
                        
                        logger.info("manager_team_removed", extra={
                            'correlation_id': get_correlation_id(),
                            'user_id': str(old_manager.id),
                            'user_email': old_manager.email[:3] + '***',
                            'team_id': str(instance.id),
                            'team_name': instance.name,
                            'event': 'manager_team_sync',
                            'reason': 'manager_removed'
                        })
                        
            except Team.DoesNotExist:
                # Team is being created, no old instance
                pass
        
        # Assign team to new manager if not already assigned
        if manager.team_id != instance.id:
            manager._skip_team_signal = True
            manager.team = instance
            manager.save(update_fields=['team', 'updated_at'])
            delattr(manager, '_skip_team_signal')
            
            logger.info("manager_team_assigned", extra={
                'correlation_id': get_correlation_id(),
                'user_id': str(manager.id),
                'user_email': manager.email[:3] + '***',
                'team_id': str(instance.id),
                'team_name': instance.name,
                'client_id': str(instance.client_account_id),
                'event': 'manager_team_sync',
                'reason': 'manager_assigned'
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
            delattr(manager, '_skip_team_signal')
            
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