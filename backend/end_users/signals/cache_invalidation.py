"""
Cache invalidation signals for end_users module.

Automatically invalidates cache when Users, Teams, or Organizations are modified.
Uses tagging strategy (no KEYS pattern) for Redis-safe invalidation.
"""

from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from core.cache_utils import invalidate_tag
import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender='end_users.User')
def invalidate_users_cache_on_save(sender, instance, created, **kwargs):
    """
    Invalidate users cache when a User is created or updated.
    
    Triggers on:
    - User creation
    - User update (any field)
    
    Invalidates:
    - users_list (all user listings)
    - user_detail (specific user details)
    - users_managers (manager listings)
    - users_superusers (superuser listings)
    """
    if not instance.client_account_id:
        return
    
    try:
        deleted_count = invalidate_tag(instance.client_account_id, 'users')
        
        action = "created" if created else "updated"
        logger.info(
            f"Cache invalidated for client {instance.client_account_id}: "
            f"User {instance.id} {action} ({deleted_count} keys cleared)"
        )
    except Exception as e:
        # Graceful degradation - log but don't break the save
        logger.warning(f"Failed to invalidate cache after User save: {e}")


@receiver(post_delete, sender='end_users.User')
def invalidate_users_cache_on_delete(sender, instance, **kwargs):
    """
    Invalidate users cache when a User is deleted.
    
    Triggers on:
    - User deletion (soft or hard)
    
    Invalidates:
    - users_list
    - user_detail
    - users_managers
    - users_superusers
    """
    if not instance.client_account_id:
        return
    
    try:
        deleted_count = invalidate_tag(instance.client_account_id, 'users')
        
        logger.info(
            f"Cache invalidated for client {instance.client_account_id}: "
            f"User {instance.id} deleted ({deleted_count} keys cleared)"
        )
    except Exception as e:
        logger.warning(f"Failed to invalidate cache after User delete: {e}")


@receiver(post_save, sender='end_users.Team')
def invalidate_users_cache_on_team_change(sender, instance, created, **kwargs):
    """
    Invalidate users cache when a Team is created or updated.
    
    Triggers on:
    - Team creation
    - Team update (name, manager, etc.)
    
    Reason: Teams impact:
    - users_managers (manager listings show team info)
    - users_list (if managers_only filter used)
    
    Invalidates:
    - All users cache for the client
    """
    if not instance.organization or not instance.organization.client_account_id:
        return
    
    try:
        client_id = instance.organization.client_account_id
        deleted_count = invalidate_tag(client_id, 'users')
        
        action = "created" if created else "updated"
        logger.info(
            f"Cache invalidated for client {client_id}: "
            f"Team {instance.id} {action} ({deleted_count} keys cleared)"
        )
    except Exception as e:
        logger.warning(f"Failed to invalidate cache after Team save: {e}")


@receiver(post_delete, sender='end_users.Team')
def invalidate_users_cache_on_team_delete(sender, instance, **kwargs):
    """
    Invalidate users cache when a Team is deleted.
    
    Reason: Teams impact manager listings and user details.
    """
    if not instance.organization or not instance.organization.client_account_id:
        return
    
    try:
        client_id = instance.organization.client_account_id
        deleted_count = invalidate_tag(client_id, 'users')
        
        logger.info(
            f"Cache invalidated for client {client_id}: "
            f"Team {instance.id} deleted ({deleted_count} keys cleared)"
        )
    except Exception as e:
        logger.warning(f"Failed to invalidate cache after Team delete: {e}")


@receiver(post_save, sender='end_users.Organization')
def invalidate_users_cache_on_org_change(sender, instance, created, **kwargs):
    """
    Invalidate users cache when an Organization is created or updated.
    
    Triggers on:
    - Organization creation
    - Organization update (name, manager, etc.)
    
    Reason: Organizations impact:
    - users_managers (manager listings show org info)
    - users_list (organization field in user details)
    - user_detail (organization relationships)
    
    Invalidates:
    - All users cache for the client
    """
    if not instance.client_account_id:
        return
    
    try:
        deleted_count = invalidate_tag(instance.client_account_id, 'users')
        
        action = "created" if created else "updated"
        logger.info(
            f"Cache invalidated for client {instance.client_account_id}: "
            f"Organization {instance.id} {action} ({deleted_count} keys cleared)"
        )
    except Exception as e:
        logger.warning(f"Failed to invalidate cache after Organization save: {e}")


@receiver(post_delete, sender='end_users.Organization')
def invalidate_users_cache_on_org_delete(sender, instance, **kwargs):
    """
    Invalidate users cache when an Organization is deleted.
    
    Reason: Organizations impact manager listings and user details.
    """
    if not instance.client_account_id:
        return
    
    try:
        deleted_count = invalidate_tag(instance.client_account_id, 'users')
        
        logger.info(
            f"Cache invalidated for client {instance.client_account_id}: "
            f"Organization {instance.id} deleted ({deleted_count} keys cleared)"
        )
    except Exception as e:
        logger.warning(f"Failed to invalidate cache after Organization delete: {e}")