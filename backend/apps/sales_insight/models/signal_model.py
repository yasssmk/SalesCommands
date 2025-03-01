# apps/sales_insight/models/signal_model.py
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
        DORMANT = 'DORMANT', _('Dormant')
    
    class Confidence(models.TextChoices):
        HIGH = 'HIGH', _('High')
        MEDIUM = 'MEDIUM', _('Medium')
        LOW = 'LOW', _('Low')
    
    class Urgency(models.TextChoices):
        CRITICAL = 'CRITICAL', _('Critical')
        HIGH = 'HIGH', _('High')
        MEDIUM = 'MEDIUM', _('Medium')
        LOW = 'LOW', _('Low')
    
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
    
    # Prioritization fields
    confidence = models.CharField(
        max_length=10,
        choices=Confidence.choices,
        default=Confidence.MEDIUM,
        verbose_name=_('Confidence Level')
    )
    
    potential_value = models.IntegerField(
        default=0,
        verbose_name=_('Revenue Potential'),
        help_text=_('Estimated revenue impact (0-100)')
    )
    
    urgency = models.CharField(
        max_length=10,
        choices=Urgency.choices,
        default=Urgency.MEDIUM,
        verbose_name=_('Urgency Level')
    )
    
    # Product alignment - using string reference instead of direct import
    product_alignment = models.ForeignKey(
        'products.Product',
        related_name='aligned_signals',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name=_('Aligned Products')
    )
    
    # Status and lifecycle
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        verbose_name=_('Signal Status')
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
    
    # Entity references - corrected module paths
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

    class Meta(ClientScopeManager.ModelMixin.get_meta_constraints(
        index_fields=['category', 'entity_type', 'status', 'urgency']
    )):
        db_table = 'signals'
        verbose_name = _('Signal')
        verbose_name_plural = _('Signals')
        ordering = ['-urgency', '-potential_value', '-created_at']
        indexes = [
            models.Index(fields=['account']),
            models.Index(fields=['org_unit']),
            models.Index(fields=['contact']),
            models.Index(fields=['account_product_detail']),
            models.Index(fields=['revisit_date']),
            models.Index(fields=['applied_date']),
        ]
    
    def __str__(self):
        return f"{self.get_category_display()}: {self.field_name} [{self.get_status_display()}]"