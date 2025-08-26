# backend/end_users/signals/user_signals.py

from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from end_users.models import User

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
            

            print(
                f"User {instance.email} granted superuser status due to Admin role "
                f"(client: {instance.client_account.name})"
            )
    
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
            

            print(
                f"User {instance.email} assigned Admin role due to superuser status "
                f"(client: {instance.client_account.name})"
            )
            
        except UserRole.DoesNotExist:
            # Le rôle Admin n'existe pas (ne devrait pas arriver)

            print(
                f"Could not assign Admin role to superuser {instance.email}: "
                f"Admin role not found for client {instance.client_account.name}"
            )