# apps/signals/models/signal_model.py

from django.db import models
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
        PROCESS = 'PROCESS', _('Process')
        TECH_STACK = 'TECH_STACK', _('Technology Stack')
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
        ACCOUNT_PRODUCT = 'ACCOUNT_PRODUCT', _('Account Product Detail')
    
    class Field(models.TextChoices):
        # Account qualification fields (from call transcript analysis)
        COMPANY_SIZE = 'company_size', _('Company Size')
        ANNUAL_REVENUE = 'annual_revenue', _('Annual Revenue')
        OBJECTIVES = 'objectives', _('Objectives')
        MOTIVATIONS = 'motivations', _('Motivations')
        METRICS = 'metrics', _('Metrics')
        PAIN_POINTS = 'pain_points', _('Pain Points')
        IMPLICATIONS = 'implications', _('Implications')
        
        # Tech stack fields (from call transcript analysis)
        PURPOSE = 'purpose', _('Purpose')
        PROS = 'pros', _('Pros')
        CONS = 'cons', _('Cons')
        ANNUAL_COSTS = 'annual_costs', _('Annual Costs')
        RENEWAL_DATE = 'renewal_date', _('Renewal Date')
        START_YEAR_OF_USAGE = 'start_year_of_usage', _('Start year of Usage')
    
    # Define valid field categories (which fields belong to which categories)
    FIELD_CATEGORIES = {
        # Profile fields
        Field.COMPANY_SIZE: Category.PROFILE,
        Field.ANNUAL_REVENUE: Category.PROFILE,
        
        # Qualification fields
        Field.OBJECTIVES: Category.QUALIFICATION,
        Field.MOTIVATIONS: Category.QUALIFICATION,
        Field.METRICS: Category.QUALIFICATION,
        Field.PAIN_POINTS: Category.QUALIFICATION,
        Field.IMPLICATIONS: Category.QUALIFICATION,
        
        # Tech stack fields
        Field.PURPOSE: Category.TECH_STACK,
        Field.PROS: Category.TECH_STACK,
        Field.CONS: Category.TECH_STACK,
        Field.ANNUAL_COSTS: Category.TECH_STACK,
        Field.RENEWAL_DATE: Category.TECH_STACK,
        Field.START_YEAR_OF_USAGE: Category.TECH_STACK,
    }
    
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

    # Contact attribution (who provided this information)
    source_contact = models.ForeignKey(
        'accounts.Contact',
        on_delete=models.SET_NULL,
        related_name='provided_signals',
        null=True,
        blank=True,
        verbose_name=_('Source Contact')
    )
    
    source_department = models.ForeignKey(
        'core_apps.StandardDepartment',
        on_delete=models.SET_NULL,
        related_name='department_signals',
        null=True,
        blank=True,
        verbose_name=_('Source Department')
    )
    
    # lifecycle management
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
    
    #Later to connect with activity
    source = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        verbose_name=_('Data Source')
    )
    
    # Dates and timestamps
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
    
    contact = models.ForeignKey(
        'accounts.Contact',
        on_delete=models.CASCADE,
        related_name='signals',
        null=True,
        blank=True,
        verbose_name=_('Contact')
    )
    
    account_product_relationship = models.ForeignKey(
        'accounts.AccountProductRelationship',
        on_delete=models.CASCADE,
        related_name='signals',
        null=True,
        blank=True,
        verbose_name=_('Account Product relationship')
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

    def clean(self):
        """Minimal clean method with basic validations"""
        super().clean()
        
        # Set source department from contact if available and not set
        if self.source_contact and not self.source_department and hasattr(self.source_contact, 'standard_department'):
            self.source_department = self.source_contact.standard_department

    def save(self, force_insert=False, force_update=False, *args, **kwargs):
        from core.exceptions import StandardizedValidationError
        from core.error_messages import CoreErrorMessages
        
        user = kwargs.pop('user', None)
        client_id = kwargs.pop('client_id', None)
        
        if not self.pk:  # New instance
            if not client_id and not self.client_id:
                raise StandardizedValidationError(CoreErrorMessages.CLIENT_ID_REQUIRED)
        
        if self.source == 'manual_entry' and self.status == self.Status.PENDING:
            self.status = self.Status.APPROVED
        
        # Let the BaseModelApp handle timestamps and user tracking
        super().save(*args, **kwargs)
    
    @classmethod
    def get_signals_for_account(cls, account_id, **filters):
        """
        Get signals for a specific account with optional filters.
        
        Args:
            account_id: Account ID to filter by
            **filters: Additional filters like category, field_name, etc.
        """
        query = cls.objects.filter(account_id=account_id)
        
        # Apply additional filters if provided
        for field, value in filters.items():
            if value is not None:
                query = query.filter(**{field: value})
                
        return query
    

    def __str__(self):
        return f"{self.get_category_display()}: {self.field_name} [{self.get_status_display()}]"