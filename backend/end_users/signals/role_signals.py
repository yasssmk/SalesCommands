# backend/end_users/signals.py

from django.db.models.signals import post_save
from django.dispatch import receiver
from end_users.models import ClientAccount, UserRole


@receiver(post_save, sender=ClientAccount)
def create_default_roles(sender, instance, created, **kwargs):
    """
    Automatically create default roles for new client accounts.
    Each role has explicit tier settings (is_admin, is_manager, is_individual).
    """
    if created:  # Only when a new client is created
        default_roles = [
            {
                "name": "Admin",
                "read": True,
                "write": True,
                "modify": True,
                "can_delete": True,
                # Tier explicite: Admin
                "is_admin": True,
                "is_manager": False,
                "is_individual": False,
                "is_locked": True
            },
            {
                "name": "Direction",
                "read": True,
                "write": False,
                "modify": True,
                "can_delete": False,
                # Tier explicite: Manager (direction = management)
                "is_admin": False,
                "is_manager": True,
                "is_individual": False
            },
            {
                "name": "Team Manager",
                "read": True,
                "write": True,
                "modify": True,
                "can_delete": False,
                # Tier explicite: Manager
                "is_admin": False,
                "is_manager": True,
                "is_individual": False
            },
            {
                "name": "Account Executive",
                "read": True,
                "write": True,
                "modify": False,
                "can_delete": False,
                # Tier explicite: Individual
                "is_admin": False,
                "is_manager": False,
                "is_individual": True
            },
            {
                "name": "Business Developer",
                "read": True,
                "write": True,
                "modify": False,
                "can_delete": False,
                # Tier explicite: Individual
                "is_admin": False,
                "is_manager": False,
                "is_individual": True
            },
        ]
        
        for role_data in default_roles:
            try:
                role, created_flag = UserRole.objects.get_or_create(
                    client_account=instance,
                    name=role_data["name"],
                    defaults={
                        "read": role_data["read"],
                        "write": role_data["write"],
                        "modify": role_data["modify"],
                        "can_delete": role_data["can_delete"],
                        "is_admin": role_data["is_admin"],
                        "is_manager": role_data["is_manager"],
                        "is_individual": role_data["is_individual"]
                    }
                )
                
                if created_flag:
                    tier = 'admin' if role.is_admin else ('manager' if role.is_manager else 'individual')
                    print(f"[ROLE CREATION] Created role '{role_data['name']}' (tier: {tier}) for client '{instance.name}'")
                    
            except Exception as e:
                print(f"[ERROR] Failed to create role '{role_data['name']}' for client '{instance.name}': {e}")