from django.db import models
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from core.constants import COUNTRIES
from core.error_messages import CoreErrorMessages
from core.exceptions import StandardizedValidationError, StandardizedPermissionDenied
from end_users.models import User


class BaseModelApp(models.Model):
    """
    Base model for all application models that need client tracking
    """
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("Last Updated"))
    client_id = models.UUIDField(
        verbose_name=_('Client ID'),
        help_text=_('ID of the client company this record belongs to'),
        db_index=True,
        editable=False
    )
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, related_name="%(class)s_created", blank=True, null=True, verbose_name=_("Created By"))
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, related_name="%(class)s_updated", blank=True, null=True, verbose_name=_("Updated By"))


    class Meta:
        abstract = True
        
    def save(self, force_insert=False, force_update=False, *args, **kwargs):
        user=kwargs.pop('user', None)
        client_id = kwargs.pop('client_id', None)
        
        if not self.pk:  # New instance
            if not client_id and not self.client_id:
                 raise StandardizedValidationError(CoreErrorMessages.CLIENT_ID_REQUIRED)
            
            if client_id:
                self.client_id = client_id
            if user:
                self.created_by = user
                self.updated_by = user
        else:  # Existing instance
            # Prevent client_id from being changed
            if client_id and client_id != self.client_id:
                raise StandardizedValidationError(CoreErrorMessages.CLIENT_ID_IMMUTABLE)
            
            if user:
                self.updated_by = user
            
            # Double check against database
            try:
                db_instance = self.__class__.objects.get(pk=self.pk)
                if self.client_id != db_instance.client_id:
                    raise StandardizedValidationError(CoreErrorMessages.CLIENT_ID_IMMUTABLE)
            except self.__class__.DoesNotExist:
                raise StandardizedValidationError(CoreErrorMessages.OBJECT_NOT_FOUND)

        super().save(force_insert=force_insert, force_update=force_update, *args, **kwargs)

    def delete(self, *args, **kwargs):
        client_id = kwargs.pop('client_id', None)
        if client_id and client_id != self.client_id:
            raise StandardizedPermissionDenied(CoreErrorMessages.CLIENT_MISMATCH)
        super().delete(*args, **kwargs)

class AccountLinkedModel(models.Model):
    """Base model for entities that need account tracking"""
    account = models.ForeignKey(
        'accounts.Account',
        on_delete=models.CASCADE,
        verbose_name=_('Account'),
        related_name='%(class)s_set'
    )

    class Meta:
        abstract = True
        indexes = [
            models.Index(fields=['account'])
        ]

    def save(self, *args, **kwargs):
        if self.account and not self.client_id:
            self.client_id = self.account.client_id
        super().save(*args, **kwargs)

class StandardDepartment(models.Model):
    """
    A controlled list of standard department categories for mapping.
    """

    class DepartmentChoices(models.TextChoices):
        GENERAL_MANAGEMENT = "General Management", _("General Management")
        HR = "HR", _("Human Resources (HR)")
        FINANCE = "Finance", _("Finance & Accounting")
        IT = "IT", _("Information Technology (IT)")
        MARKETING = "Marketing", _("Marketing & Communications")
        SALES = "Sales", _("Sales & Business Development")
        CUSTOMER_SUPPORT = "Customer Support", _("Customer Support & Success")
        OPERATIONS = "Operations", _("Operations & Supply Chain")
        LEGAL = "Legal", _("Legal & Compliance")
        PROCUREMENT = "Procurement", _("Procurement & Vendor Management")
        ENGINEERING = "Engineering", _("Engineering & R&D")
        PRODUCT_MANAGEMENT = "Product Management", _("Product Management")
        DATA_ANALYTICS = "Data & Analytics", _("Data & Analytics")
        SECURITY_RISK = "Security & Risk Management", _("Security & Risk Management")
        HEALTHCARE_ADMIN = "Healthcare Administration", _("Healthcare Administration")
        CLINICAL_MEDICAL = "Clinical & Medical Staff", _("Clinical & Medical Staff")
        RETAIL_OPERATIONS = "Retail Operations", _("Retail & Store Operations")
        MANUFACTURING = "Manufacturing", _("Manufacturing & Production")
        LOGISTICS = "Logistics", _("Logistics & Transportation")
        CONSTRUCTION = "Construction", _("Construction & Engineering")
        EDUCATION_TRAINING = "Education & Training", _("Education & Training")
        GOVERNMENT = "Government", _("Government & Public Services")
        MEDIA = "Media", _("Media & Content Creation")

    name = models.CharField(
        max_length=50, 
        choices=DepartmentChoices.choices, 
        unique=True, 
        verbose_name=_("Standard Department Name")
    )

    class Meta:
        db_table = "standard_departments"
        verbose_name = _("Standard Department")
        verbose_name_plural = _("Standard Departments")
        ordering = ["name"]

    def __str__(self):
        return self.get_name_display()