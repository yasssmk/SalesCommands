"""
Management command to create a new tenant (ClientAccount) for the CRM.
This command creates a ClientAccount and optionally a superuser admin.

UTILISATION:

# Créer un tenant simple
python manage.py create_tenant --name "Client Alpha"

# Créer un tenant avec domaine (pour information)
python manage.py create_tenant --name "Client Beta" --domain "beta.app.local"

# Créer un tenant avec un admin
python manage.py create_tenant --name "Client Gamma" --create-admin

# Avec tous les paramètres
python manage.py create_tenant --name "Client Delta" --domain "delta.app.local" --max-users 50 --create-admin
"""

from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import transaction
from getpass import getpass
from end_users.models import ClientAccount, User, UserRole


class Command(BaseCommand):
    help = 'Creates a new tenant (ClientAccount) for the multi-tenant CRM'

    def add_arguments(self, parser):
        parser.add_argument(
            '--name',
            type=str,
            required=True,
            help='Name of the tenant/client company (required)',
        )
        parser.add_argument(
            '--domain',
            type=str,
            help='Domain for the tenant (for information purposes)',
        )
        parser.add_argument(
            '--max-users',
            type=int,
            default=10,
            help='Maximum number of users allowed for this tenant (default: 10)',
        )
        parser.add_argument(
            '--is-b2c',
            action='store_true',
            default=False,
            help='Mark this tenant as B2C instead of B2B (default: B2B)',
        )
        parser.add_argument(
            '--create-admin',
            action='store_true',
            help='Create an initial superuser admin for this tenant',
        )
        parser.add_argument(
            '--admin-email',
            type=str,
            help='Email for the admin user (required if --create-admin is used)',
        )
        parser.add_argument(
            '--admin-password',
            type=str,
            help='Password for the admin user (will prompt if not provided)',
        )

    def handle(self, *args, **options):
        """Main command handler."""
        name = options.get('name')
        domain = options.get('domain')
        max_users = options.get('max_users')
        is_b2c = options.get('is_b2c')
        create_admin = options.get('create_admin')
        admin_email = options.get('admin_email')
        admin_password = options.get('admin_password')

        try:
            with transaction.atomic():
                # Check if tenant already exists
                if ClientAccount.objects.filter(name=name).exists():
                    raise CommandError(f'Tenant with name "{name}" already exists.')

                # Create the tenant
                self.stdout.write(f'Creating tenant: {name}...')
                tenant = ClientAccount.objects.create(
                    name=name,
                    is_b2b=not is_b2c,  # Inverse of is_b2c flag
                    max_users=max_users,
                )
                
                self.stdout.write(
                    self.style.SUCCESS(f'✓ Created tenant: {tenant.name}')
                )
                
                # Display tenant info
                self.stdout.write(
                    f'  - ID: {tenant.id}\n'
                    f'  - Type: {"B2C" if is_b2c else "B2B"}\n'
                    f'  - Max users: {tenant.max_users}'
                )
                
                if domain:
                    self.stdout.write(f'  - Domain (info): {domain}')

                # Check if Admin role was created by signal
                admin_role = None
                try:
                    admin_role = tenant.get_or_create_admin_role()
                    self.stdout.write(
                        self.style.SUCCESS(f'✓ Admin role available: {admin_role.name}')
                    )
                except Exception as e:
                    self.stdout.write(
                        self.style.WARNING(f'⚠ Admin role not created: {str(e)}')
                    )
                    raise CommandError('Cannot create tenant without Admin role')

                # TOUJOURS créer un admin pour pouvoir se connecter (MVP)
                if not admin_role:
                    raise CommandError('Cannot create tenant without Admin role')
                
                # Générer un email par défaut basé sur le nom du tenant
                if not admin_email:
                    # Créer un email par défaut basé sur le nom du tenant
                    tenant_slug = name.lower().replace(' ', '-').replace('.', '')
                    default_email = f'admin@{tenant_slug}.com'
                    
                    self.stdout.write(
                        self.style.WARNING(
                            f'\n⚠️  Aucun email admin fourni.'
                        )
                    )
                    
                    # Demander confirmation ou saisie manuelle
                    use_default = input(f'Utiliser l\'email par défaut "{default_email}" ? (o/n) : ').strip().lower()
                    
                    if use_default in ['o', 'oui', 'y', 'yes', '']:
                        admin_email = default_email
                    else:
                        admin_email = self.get_email_interactive()
                
                # Check if user already exists
                if User.objects.filter(email=admin_email).exists():
                    raise CommandError(f'User with email "{admin_email}" already exists.')
                
                # Générer un mot de passe temporaire si non fourni
                if not admin_password:
                    self.stdout.write(
                        self.style.WARNING(
                            '\n⚠️  Aucun mot de passe fourni.'
                        )
                    )
                    
                    # Proposer un mot de passe temporaire ou saisie manuelle
                    use_temp = input('Utiliser un mot de passe temporaire "Admin123!" ? (o/n) : ').strip().lower()
                    
                    if use_temp in ['o', 'oui', 'y', 'yes', '']:
                        admin_password = 'Admin123!'
                        self.stdout.write(
                            self.style.WARNING(
                                '⚠️  IMPORTANT: Changez ce mot de passe dès la première connexion !'
                            )
                        )
                    else:
                        admin_password = self.get_password_interactive()
                
                # Create the admin user
                admin_user = self.create_admin_user(
                    email=admin_email,
                    password=admin_password,
                    tenant=tenant,
                    role=admin_role
                )
                
                # Final summary with credentials
                self.stdout.write(
                    self.style.SUCCESS(
                        f'\n{"="*50}\n'
                        f'✅ Tenant "{name}" créé avec succès !\n'
                        f'{"="*50}\n'
                    )
                )
                
                self.stdout.write(
                    self.style.SUCCESS(
                        f'📋 Informations du tenant:\n'
                        f'  - ID: {tenant.id}\n'
                        f'  - Nom: {tenant.name}\n'
                        f'  - Type: {"B2C" if is_b2c else "B2B"}\n'
                        f'  - Max users: {tenant.max_users}\n'
                    )
                )
                
                if domain:
                    self.stdout.write(f'  - Domaine: {domain}')
                
                self.stdout.write(
                    self.style.SUCCESS(
                        f'\n🔐 Compte administrateur:\n'
                        f'  - Email: {admin_user.email}\n'
                        f'  - Mot de passe: {"(celui que vous avez saisi)" if admin_password != "Admin123!" else "Admin123! (À CHANGER)"}\n'
                        f'  - Rôle: {admin_role.name}\n'
                        f'  - Superuser: {"✓" if admin_user.is_superuser else "✗"}\n'
                    )
                )
                
                self.stdout.write(
                    self.style.WARNING(
                        f'\n⚠️  Conservez ces informations en lieu sûr !\n'
                        f'{"="*50}'
                    )
                )

        except KeyboardInterrupt:
            self.stdout.write('\n\nOperation cancelled.')
            return
        except Exception as e:
            raise CommandError(f'Error creating tenant: {str(e)}')

    def get_email_interactive(self):
        """Prompt for email address interactively."""
        self.stdout.write('\nAdmin user creation:')
        while True:
            email = input('Email address: ').strip()
            if not email:
                self.stdout.write(self.style.ERROR('Email cannot be empty.'))
                continue
            
            # Basic email validation
            if '@' not in email or '.' not in email.split('@')[1]:
                self.stdout.write(self.style.ERROR('Please enter a valid email address.'))
                continue
            
            return email.lower()

    def get_password_interactive(self):
        """Prompt for password interactively with validation."""
        while True:
            password = getpass('Password: ')
            password_confirm = getpass('Password (again): ')
            
            if password != password_confirm:
                self.stdout.write(self.style.ERROR("Passwords don't match."))
                continue
            
            if not password:
                self.stdout.write(self.style.ERROR('Password cannot be empty.'))
                continue
            
            # Validate password using Django validators
            try:
                validate_password(password)
                return password
            except ValidationError as e:
                self.stdout.write(self.style.ERROR('Password validation failed:'))
                for error in e.messages:
                    self.stdout.write(self.style.ERROR(f'  - {error}'))
                self.stdout.write('Please try again with a stronger password.')

    def create_admin_user(self, email, password, tenant, role):
        """Create an admin user for the tenant."""
        user = User.objects.create_user(
            email=email,
            password=password,
            client_account=tenant,
            role=role,
            role_name=role.name,
            is_active=True,
            is_staff=True,  # Allow Django admin access
            is_superuser=True,  # Superuser for this tenant
            first_name='Admin',
            last_name=tenant.name  # Use tenant name as last name
        )
        
        return user