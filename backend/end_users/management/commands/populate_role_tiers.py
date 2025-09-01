"""
Management command to populate tier flags for existing UserRoles.

Usage:
    python manage.py populate_role_tiers
    python manage.py populate_role_tiers --dry-run
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from end_users.models import UserRole
from django.db import models


class Command(BaseCommand):
    help = 'Populate is_admin, is_manager, is_individual flags for existing roles'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be updated without making changes',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        if dry_run:
            self.stdout.write("\n🔍 DRY RUN MODE - No changes will be made\n")
        else:
            self.stdout.write("\n🚀 UPDATING ROLE TIERS\n")
        
        # Get all roles
        roles = UserRole.objects.all()
        total = roles.count()
        
        if total == 0:
            self.stdout.write(self.style.WARNING("No roles found in database"))
            return
        
        self.stdout.write(f"Found {total} roles to process\n")
        self.stdout.write("-" * 50)
        
        updated = 0
        
        with transaction.atomic():
            for role in roles:
                name_lower = role.name.lower()
                old_state = (role.is_admin, role.is_manager, role.is_individual)
                
                # Determine tier based on name
                if 'admin' in name_lower:
                    new_admin, new_manager, new_individual = True, False, False
                    tier = "ADMIN"
                elif any(word in name_lower for word in ['manager', 'supervisor', 'lead', 'direction']):
                    new_admin, new_manager, new_individual = False, True, False
                    tier = "MANAGER"
                else:
                    new_admin, new_manager, new_individual = False, False, True
                    tier = "INDIVIDUAL"
                
                # Check if update needed
                if old_state != (new_admin, new_manager, new_individual):
                    if not dry_run:
                        role.is_admin = new_admin
                        role.is_manager = new_manager
                        role.is_individual = new_individual
                        role.save(update_fields=['is_admin', 'is_manager', 'is_individual'])
                    
                    self.stdout.write(
                        f"  ✓ {role.name} → {tier}\n"
                        f"    Client: {role.client_account.name}\n"
                        f"    Updated: admin={new_admin}, manager={new_manager}, individual={new_individual}"
                    )
                    updated += 1
                else:
                    self.stdout.write(
                        f"  ○ {role.name} → {tier} (already set correctly)"
                    )
        
        self.stdout.write("-" * 50)
        
        if dry_run:
            self.stdout.write(
                self.style.SUCCESS(f"\n✅ DRY RUN COMPLETE: {updated} roles would be updated")
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f"\n✅ COMPLETE: Updated {updated} of {total} roles")
            )
        
        # Show summary
        self.stdout.write("\n📊 SUMMARY BY TIER:")
        if not dry_run:
            admin_count = UserRole.objects.filter(is_admin=True).count()
            manager_count = UserRole.objects.filter(is_manager=True).count()
            individual_count = UserRole.objects.filter(is_individual=True).count()
            
            self.stdout.write(f"  Admins: {admin_count}")
            self.stdout.write(f"  Managers: {manager_count}")
            self.stdout.write(f"  Individuals: {individual_count}")
            self.stdout.write(f"  Total: {admin_count + manager_count + individual_count}")
        
        # Validate constraint
        invalid = UserRole.objects.exclude(
            models.Q(is_admin=True, is_manager=False, is_individual=False) |
            models.Q(is_admin=False, is_manager=True, is_individual=False) |
            models.Q(is_admin=False, is_manager=False, is_individual=True)
        )
        
        if invalid.exists():
            self.stdout.write(
                self.style.ERROR(f"\n⚠️  WARNING: {invalid.count()} roles have invalid tier configuration!")
            )
            for role in invalid:
                self.stdout.write(
                    f"  - {role.name}: admin={role.is_admin}, manager={role.is_manager}, individual={role.is_individual}"
                )