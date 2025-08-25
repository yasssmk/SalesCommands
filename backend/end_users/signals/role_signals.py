from django.db.models.signals import post_save
from django.dispatch import receiver
from end_users.models import ClientAccount, UserRole

@receiver(post_save, sender=ClientAccount)
def create_default_roles(sender, instance, created, **kwargs):
    """Automatically create default roles for new client accounts."""
    if created:  # Only when a new client is created
        default_roles = [
            {"name": "Admin", "read": True, "write": True, "modify": True, "delete": True},
            {"name": "Direction", "read": True, "write": False, "modify": True, "delete": False},
            {"name": "Team Manager", "read": True, "write": True, "modify": True, "delete": False},
            {"name": "Account Executive", "read": True, "write": True, "modify": False, "delete": False},
            {"name": "Business Developer", "read": True, "write": True, "modify": False, "delete": False},
        ]
        for role_data in default_roles:
            UserRole.objects.get_or_create(client_account=instance, **role_data)
