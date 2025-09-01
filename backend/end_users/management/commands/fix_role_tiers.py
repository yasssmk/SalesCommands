# backend/end_users/management/commands/fix_role_tiers.py

from django.core.management.base import BaseCommand
from django.db import transaction
from end_users.models import UserRole


class Command(BaseCommand):
    help = 'Fix existing role tiers before applying constraint migration'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Run in dry-run mode (no actual changes)',
        )

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)
        
        if dry_run:
            self.stdout.write(self.style.WARNING('\n🔍 DRY RUN MODE - No changes will be saved\n'))
        
        self.stdout.write("=" * 50)
        self.stdout.write("FIXING ROLE TIERS FOR MIGRATION")
        self.stdout.write("=" * 50)
        
        roles = UserRole.objects.all()
        total = roles.count()
        fixed = 0
        already_ok = 0
        
        with transaction.atomic():
            for role in roles:
                # Check current state
                tier_count = sum([
                    role.is_admin,
                    role.is_manager,
                    role.is_individual
                ])
                
                if tier_count == 1:
                    already_ok += 1
                    self.stdout.write(f"  ✓ {role.name} - Already OK")
                    continue
                
                # Fix based on name
                name_lower = role.name.lower()
                old_state = (role.is_admin, role.is_manager, role.is_individual)
                
                if 'admin' in name_lower:
                    role.is_admin = True
                    role.is_manager = False
                    role.is_individual = False
                    tier = "ADMIN"
                elif any(word in name_lower for word in ['manager', 'supervisor', 'lead', 'direction']):
                    role.is_admin = False
                    role.is_manager = True
                    role.is_individual = False
                    tier = "MANAGER"
                else:
                    role.is_admin = False
                    role.is_manager = False
                    role.is_individual = True
                    tier = "INDIVIDUAL"
                
                if not dry_run:
                    role.save(update_fields=['is_admin', 'is_manager', 'is_individual'])
                
                client_name = role.client_account.name if role.client_account else 'N/A'
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  🔧 {role.name} → {tier} (Client: {client_name})"
                    )
                )
                fixed += 1
            
            if dry_run:
                transaction.set_rollback(True)
        
        self.stdout.write("=" * 50)
        self.stdout.write(f"📊 SUMMARY:")
        self.stdout.write(f"  Total roles: {total}")
        self.stdout.write(f"  Already correct: {already_ok}")
        self.stdout.write(f"  Fixed: {fixed}")
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING("\n⚠️  DRY RUN - No changes were saved. Run without --dry-run to apply fixes.")
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f"\n✅ Successfully fixed {fixed} roles. You can now run the migration.")
            )