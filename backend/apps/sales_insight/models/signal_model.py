from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from core.client_scope import ClientScopeManager
from apps.core_apps.models import BaseModelApp, AccountLinkedModel


class Signal(BaseModelApp, AccountLinkedModel, ClientScopeManager.ModelMixin):
    """
    Signal model that tracks valuable sales insights from AI analysis 
    and other sources to support sales prioritization and action planning.
    """

    class Category(models.TextChoices):
        PROFILE = 'PROFILE', _('Profile Data')
        GOALS = 'GOALS', _('Business/Unit Goals')
        PROCESS = 'PROCESS', _('Process')
        QUALIFICATION = 'QUALIFICATION', _('Qualification')
        PROJECT = 'PROJECT', _('Project')
    
    class Status(models.TextChoices):
        PENDING = 'PENDING', _('Pending')
        APPROVED = 'APPROVED', _('Approved')
        REJECTED = 'REJECTED', _('Rejected')
        APPLIED = 'APPLIED', _('Applied')
        MERGED = 'MERGED', _('Merged')
    
    class EntityType(models.TextChoices):
        ACCOUNT = 'ACCOUNT', _('Account')
        ORG_UNIT = 'ORG_UNIT', _('Organization Unit')
        CONTACT = 'CONTACT', _('Contact')
        ACCOUNT_PRODUCT = 'ACCOUNT_PRODUCT', _('Account Product Detail')
    
    # Signal classification
    category = models.CharField(
        max_length=20, 
        choices=Category.choices,
        verbose_name=_('Signal Category')
    )
    
    # Field & Value
    entity_type = models.CharField(
        max_length=20, 
        choices=EntityType.choices,
        verbose_name=_('Entity Type')
    )
    
    field_name = models.CharField(
        max_length=100,
        verbose_name=_('Field Name')
    )
    
    value = models.JSONField(
        verbose_name=_('Signal Value')
    )
    
    # Status and lifecycle
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        verbose_name=_('Signal Status')
    )
    
    # New fields for lifecycle management
    confirmation_count = models.PositiveIntegerField(default=1, verbose_name=_('Confirmation Count'))
    last_confirmed_at = models.DateTimeField(auto_now_add=True, verbose_name=_('Last Confirmed At'))
    merged_into = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        related_name='merged_from_signals',
        null=True,
        blank=True,
        verbose_name=_('Merged Into Signal')
    )
    
    # Dates and timestamps
    source = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        verbose_name=_('Data Source')
    )
    
    revisit_date = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name=_('Revisit Date')
    )
    
    applied_date = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name=_('Applied Date')
    )
    
    # Product alignment
    product_alignment = models.ForeignKey(
        'products.Product',
        related_name='aligned_signals',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name=_('Aligned Products')
    )
    
    # Entity references
    org_unit = models.ForeignKey(
        'org_units.AccountOrganizationUnit',
        on_delete=models.CASCADE,
        related_name='signals',
        null=True,
        blank=True,
        verbose_name=_('Organization Unit')
    )
    
    contact = models.ForeignKey(
        'contacts.Contact',
        on_delete=models.CASCADE,
        related_name='signals',
        null=True,
        blank=True,
        verbose_name=_('Contact')
    )
    
    account_product_detail = models.ForeignKey(
        'account_product_detail.AccountProductDetail',
        on_delete=models.CASCADE,
        related_name='signals',
        null=True,
        blank=True,
        verbose_name=_('Account Product Detail')
    )
    
    # Approval tracking
    approved_by = models.ForeignKey(
        'end_users.User',
        on_delete=models.SET_NULL,
        related_name='approved_signals',
        null=True,
        blank=True,
        verbose_name=_('Approved By')
    )
    
    approved_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Approved At')
    )
    
    # Parent signal for clustering related signals
    parent_signal = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        related_name='child_signals',
        null=True,
        blank=True,
        verbose_name=_('Parent Signal')
    )

    metadata = models.JSONField(
        verbose_name=_('Metadata'),
        help_text=_('Additional metadata for validations, history, and context'),
        null=True,
        blank=True
    )
    
    def get_effective_status(self):
        """Calculate the effective status based on age and signal type"""
        from ..services.signal_lifecycle_service import SignalLifecycleService
        return SignalLifecycleService.get_effective_status(self)
        
    def is_effectively_expired(self):
        """Check if the signal is effectively expired"""
        return self.get_effective_status() == "EXPIRED"

    def __str__(self):
        return f"{self.get_category_display()}: {self.field_name} [{self.get_status_display()}]"