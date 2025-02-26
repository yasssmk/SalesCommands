from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils.translation import gettext_lazy as _
from core.models import BaseModel, CentralizedUserManager

class ProductAdmin(BaseModel, AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True)
    password= models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    class Meta:
        db_table = 'product_admin_users'
        verbose_name = _('product_admin')
        verbose_name_plural = _('products_admins')
        ordering = ['-created_at']

    # Explicit related_name for reverse accessors
    groups = models.ManyToManyField(
        'auth.Group',
        related_name='product_admin_set',
        blank=True,
        help_text=_('The groups this admin belongs to.'),
        verbose_name=_('groups'),
    )
    user_permissions = models.ManyToManyField(
        'auth.Permission',
        related_name='product_admin_set',
        blank=True,
        help_text=_('Specific permissions for this admin.'),
        verbose_name=_('user permissions'),
    )


    objects = CentralizedUserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    def __str__(self):
        return self.email

