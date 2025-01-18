from django.db import models
from django.contrib.auth.models import BaseUserManager
from django.utils.translation import gettext_lazy as _
from phonenumber_field.modelfields import PhoneNumberField
from core.constants import COUNTRIES
import uuid

class BaseModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class CentralizedUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("The Email field must be set.")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        if not extra_fields.get('is_staff'):
            raise ValueError("Superuser must have is_staff=True.")
        if not extra_fields.get('is_superuser'):
            raise ValueError("Superuser must have is_superuser=True.")

        return self.create_user(email, password, **extra_fields)
    
class BaseModelApp(models.Model):

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
    
class ContactDetailsMixin(models.Model):
    """
    Abstract model for storing contact details (used by Accounts and Contacts).
    """

    address = models.TextField(blank=True, null=True, verbose_name=_('Address'))
    city = models.CharField(max_length=50, blank=True, null=True, verbose_name=_('City'))
    post_code = models.CharField(max_length=20, blank=True, null=True, verbose_name=_('Post Code'))
    state = models.CharField(max_length=50, blank=True, null=True, verbose_name=_('State/Region'))
        
    country = models.CharField(
        max_length=2, choices=COUNTRIES, default='US', verbose_name=_('Country')
    )

    phone_number = PhoneNumberField(
        max_length=20, blank=True, null=True, verbose_name=_('Phone Number')
    )
    email = models.EmailField(blank=True, null=True, verbose_name=_('Email'))

    website = models.URLField(blank=True, null=True, verbose_name=_('Website'))
    linkedin = models.URLField(blank=True, null=True, verbose_name=_('LinkedIn Profile'))

    class Meta:
        abstract = True