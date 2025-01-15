# end_users/models.py
from django.db import models
from django.utils.translation import gettext_lazy as _
from core.models import BaseModel, CentralizedUserManager
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin


class ClientAccount(BaseModel):
    name = models.CharField(max_length=255, unique=True, help_text=_("Name of the company"))
    is_b2b = models.BooleanField(default=True, help_text=_("True if the client is B2B; False for B2C."))
    max_users = models.PositiveIntegerField(default=10, help_text=_("Maximum number of users allowed for this client."))

    class Meta:
        db_table = 'client_accounts'
        verbose_name = _('client_account')
        verbose_name_plural = _('client_accounts')
        ordering = ['name']

    def __str__(self):
        return self.name


class UserRole(BaseModel):
    name = models.CharField(max_length=50, help_text=_("Role name"))
    read = models.BooleanField(default=True)
    write = models.BooleanField(default=False)
    modify = models.BooleanField(default=False)
    delete = models.BooleanField(default=False)
    client_account = models.ForeignKey(
        ClientAccount,
        on_delete=models.CASCADE,
        related_name='roles',
        help_text=_("Client this role belongs to."),
    )

    class Meta:
        db_table = 'users_roles'
        verbose_name = _('user_role')
        verbose_name_plural = _('users_roles')
        unique_together = ('name', 'client_account')
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.client_account.name})"


class Organization(BaseModel):
    name = models.CharField(max_length=100, help_text=_("Name of the organization (e.g., Sales, Management)."))
    client_account = models.ForeignKey(
        ClientAccount,
        on_delete=models.CASCADE,
        related_name='organizations',
        help_text=_("Client this organization belongs to."),
    )
    manager = models.ForeignKey(
        'end_users.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='managed_organizations',
        help_text=_("Director or main manager of the organization."),
    )

    class Meta:
        db_table = 'organizations'
        verbose_name = _('organization')
        verbose_name_plural = _('organizations')
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.client_account.name})"


class Team(BaseModel):
    name = models.CharField(max_length=100, help_text=_("Name of the team"))
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='teams',
        help_text=_("Organization this team belongs to."),
    )
    manager = models.ForeignKey(
        'end_users.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='managed_teams',
        help_text=_("Manager of the team."),
    )

    class Meta:
        db_table = 'teams'
        verbose_name = _('team')
        verbose_name_plural = _('teams')
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.organization.name} - {self.organization.client_account.name})"


class User(BaseModel, AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True)
    password = models.CharField(max_length=255)
    first_name = models.CharField(max_length=50, null=True, blank=True)
    last_name = models.CharField(max_length=50, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    client_account = models.ForeignKey(
        ClientAccount,
        on_delete=models.CASCADE,
        related_name='users',
        help_text=_("The client this user belongs to."),
    )
    role = models.ForeignKey(
        UserRole,
        on_delete=models.SET_NULL,
        null=True,
        related_name='users',
        help_text=_("Role assigned to the user."),
    )
    role_name = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        help_text=_("The name of the role assigned to the user."),
    )
    organization = models.ForeignKey(
        Organization,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='members',
        help_text=_("Organization the user belongs to."),
    )
    team = models.ForeignKey(
        Team,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='members',
        help_text=_("Team the user belongs to."),
    )

    # Explicit related_name for reverse accessors
    groups = models.ManyToManyField(
        'auth.Group',
        related_name='end_users_user_set',
        blank=True,
        help_text=_('The groups this user belongs to.'),
        verbose_name=_('groups'),
    )
    user_permissions = models.ManyToManyField(
        'auth.Permission',
        related_name='end_users_user_set',
        blank=True,
        help_text=_('Specific permissions for this user.'),
        verbose_name=_('user permissions'),
    )

    objects = CentralizedUserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    class Meta:
        db_table = 'users'
        verbose_name = _('user')
        verbose_name_plural = _('users')
        ordering = ['-created_at']

    def __str__(self):
        return self.email

    def save(self, *args, **kwargs):
        # Automatically set organization based on the team
        if self.team:
            self.organization = self.team.organization
        # Update role_name whenever role is set
        if self.role:
            self.role_name = self.role.name
        super().save(*args, **kwargs)
