"""
Management command to create a platform superuser.
This command creates a ClientAccount (if needed) and a superuser for initial platform setup.

UTILISATION: 

# Mode interactif complet
python manage.py create_platform_superuser

# Avec email pré-rempli
python manage.py create_platform_superuser --email admin@example.com

# Avec nom de client personnalisé
python manage.py create_platform_superuser --client-name "Ma Société"

"""

from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import transaction
from getpass import getpass
from end_users.models import ClientAccount, User, UserRole


class Command(BaseCommand):
    help = 'Creates a platform superuser with a default or specified client account'

    def add_arguments(self, parser):
        parser.add_argument(
            '--email',
            type=str,
            help='Email address for the superuser',
        )
        parser.add_argument(
            '--client-name',
            type=str,
            default='Platform Admin Client',
            help='Name for the client account (default: "Platform Admin Client")',
        )
        parser.add_argument(
            '--noinput',
            '--no-input',
            action='store_true',
            help='Do not prompt for user input. Email must be provided via --email',
        )

    def handle(self, *args, **options):
        """Main command handler."""
        email = options.get('email')
        client_name = options.get('client_name')
        noinput = options.get('noinput')

        try:
            # Get email interactively if not provided
            if not email:
                if noinput:
                    raise CommandError('Email is required when using --noinput')
                email = self.get_email_interactive()

            # Check if user already exists
            if User.objects.filter(email=email).exists():
                self.stdout.write(
                    self.style.ERROR(f'User with email "{email}" already exists.')
                )
                return

            # Get password interactively
            if noinput:
                raise CommandError('Password input is required. Cannot use --noinput for password.')
            password = self.get_password_interactive()

            # Create everything in a transaction
            with transaction.atomic():
                # Create or get client account
                client, created = self.get_or_create_client(client_name)
                if created:
                    self.stdout.write(
                        self.style.SUCCESS(f'Created client account: {client.name}')
                    )
                else:
                    self.stdout.write(
                        self.style.WARNING(f'Using existing client account: {client.name}')
                    )

                # Get the Admin role (should be created by signals)
                admin_role = client.get_or_create_admin_role()
                
                # Create the superuser
                user = self.create_superuser(
                    email=email,
                    password=password,
                    client=client,
                    role=admin_role
                )

                self.stdout.write(
                    self.style.SUCCESS(
                        f'\nSuccessfully created superuser:\n'
                        f'  Email: {user.email}\n'
                        f'  Client: {client.name}\n'
                        f'  Role: {admin_role.name}\n'
                        f'  Is Superuser: {user.is_superuser}\n'
                        f'  Is Active: {user.is_active}'
                    )
                )

                # Ensure admin invariants
                client.ensure_admin_invariants()

        except KeyboardInterrupt:
            self.stdout.write('\n\nOperation cancelled.')
            return
        except Exception as e:
            raise CommandError(f'Error creating superuser: {str(e)}')

    def get_email_interactive(self):
        """Prompt for email address interactively."""
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
                for error in e.messages:
                    self.stdout.write(self.style.ERROR(f'  - {error}'))
                self.stdout.write(self.style.WARNING('Please try again with a stronger password.'))

    def get_or_create_client(self, client_name):
        """Get or create a client account."""
        # First, check if any client exists
        if ClientAccount.objects.exists():
            # If there's only one client, use it
            if ClientAccount.objects.count() == 1:
                return ClientAccount.objects.first(), False
            
            # Otherwise, try to find one by name or create new
            client, created = ClientAccount.objects.get_or_create(
                name=client_name,
                defaults={
                    'is_b2b': True,
                    'max_users': 10  # Default limit for platform admin client
                }
            )
            return client, created
        else:
            # No clients exist, create the first one
            client = ClientAccount.objects.create(
                name=client_name,
                is_b2b=True,
                max_users= 10  # Default limit for platform admin client
            )
            return client, True

    def create_superuser(self, email, password, client, role):
        """Create the superuser with all necessary attributes."""
        user = User.objects.create_user(
            email=email,
            password=password,
            client_account=client,
            role=role,
            role_name=role.name,
            is_active=True,
            is_staff=True,  # Allow Django admin access
            is_superuser=True,  # Platform superuser
            first_name='Platform',
            last_name='Admin'
        )
        
        return user