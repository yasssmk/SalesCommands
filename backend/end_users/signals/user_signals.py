# backend/end_users/signals/user_signals.py

from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from end_users.models import User
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

@receiver(pre_save, sender=User)
def sync_admin_role_with_superuser(sender, instance, **kwargs):
    """
    Synchronise automatiquement is_superuser quand un user a le rôle Admin.
    
    Règles :
    - Si role.name == "Admin" → is_superuser = True, is_staff = True
    - On ne retire jamais is_superuser automatiquement (pour éviter les problèmes)
    """
    
    # Si l'utilisateur a le rôle Admin, activer superuser
    if instance.role and instance.role.name == 'Admin':
        if not instance.is_superuser:
            instance.is_superuser = True
            instance.is_staff = True  # Pour l'accès Django admin si besoin
            

            logger.info("user_granted_superuser_from_admin_role", extra={
                'correlation_id': get_correlation_id(),
                'user_id': str(instance.id) if instance.id else '-',
                'user_email': instance.email[:3] + '***' if instance.email else '-',
                'client_id': str(instance.client_account_id) if instance.client_account_id else '-',
                'client_name': instance.client_account.name if instance.client_account else '-',
                'event': 'user_superuser_sync',
                'reason': 'admin_role'
            })
    
    # NOTE : On ne retire PAS is_superuser si on perd le rôle Admin
    # Cela évite les problèmes de permissions et permet d'avoir des superusers
    # sans le rôle Admin (ex: créés via manage.py createsuperuser)


@receiver(post_save, sender=User)
def ensure_admin_consistency(sender, instance, created, **kwargs):
    """
    Post-save : Vérifier la cohérence Admin/SuperUser après la sauvegarde.
    
    Si un user est superuser mais n'a pas de rôle, lui assigner le rôle Admin.
    Utile pour les superusers créés via manage.py createsuperuser.
    """
    
    # Skip si c'est un signal en cascade (évite les boucles infinies)
    if hasattr(instance, '_skip_signal'):
        return
    
    # Si superuser sans rôle → assigner le rôle Admin
    if instance.is_superuser and not instance.role:
        try:
            from end_users.models import UserRole
            
            # Récupérer le rôle Admin du client
            admin_role = UserRole.objects.get(
                client_account=instance.client_account,
                name='Admin'
            )
            
            # Assigner le rôle et sauvegarder
            instance.role = admin_role
            instance.role_name = 'Admin'
            
            # Flag pour éviter la récursion
            instance._skip_signal = True
            instance.save(update_fields=['role', 'role_name', 'updated_at'])
            delattr(instance, '_skip_signal')
            

            logger.info("user_assigned_admin_role_from_superuser", extra={
                'correlation_id': get_correlation_id(),
                'user_id': str(instance.id) if instance.id else '-',
                'user_email': instance.email[:3] + '***' if instance.email else '-',
                'client_id': str(instance.client_account_id) if instance.client_account_id else '-',
                'client_name': instance.client_account.name if instance.client_account else '-',
                'event': 'user_role_sync',
                'reason': 'superuser_status'
            })
            
        except UserRole.DoesNotExist:
            # Le rôle Admin n'existe pas (ne devrait pas arriver)

            logger.warning("admin_role_not_found_for_superuser", extra={
                'correlation_id': get_correlation_id(),
                'user_id': str(instance.id) if instance.id else '-',
                'user_email': instance.email[:3] + '***' if instance.email else '-',
                'client_id': str(instance.client_account_id) if instance.client_account_id else '-',
                'client_name': instance.client_account.name if instance.client_account else '-',
                'event': 'user_role_sync_failed',
                'error': 'admin_role_not_found'
            })