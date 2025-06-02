# apps/leads/models/lead.py

from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from core.client_scope import ClientScopeManager
from apps.core_apps.models import BaseModelApp, AccountLinkedModel
from core.exceptions import StandardizedValidationError
from core.error_messages import CoreErrorMessages


class Lead(BaseModelApp, AccountLinkedModel, ClientScopeManager.ModelMixin):
    """
    Represents a potential sales opportunity before qualification
    """
    
    class LeadSource(models.TextChoices):
        MANUAL = 'MANUAL', _('Manual Entry')
        CAMPAIGN = 'CAMPAIGN', _('Campaign')
        ACTIVITY = 'ACTIVITY', _('Activity')
        INBOUND = 'INBOUND', _('Inbound')
        REFERRAL = 'REFERRAL', _('Referral')
        WEBSITE = 'WEBSITE', _('Website')
        OTHER = 'OTHER', _('Other')
    
    class LeadStatus(models.TextChoices):
        NEW = 'NEW', _('New')
        CONTACTED = 'CONTACTED', _('Contacted')
        QUALIFIED = 'QUALIFIED', _('Qualified')
        UNQUALIFIED = 'UNQUALIFIED', _('Unqualified')
        CONVERTED = 'CONVERTED', _('Converted')
    
    # Basic Information
    title = models.CharField(
        max_length=200,
        verbose_name=_('Lead Title')
    )
    
    description = models.TextField(
        blank=True,
        null=True,
        verbose_name=_('Description')
    )
    
    # Source Information
    lead_source = models.CharField(
        max_length=20,
        choices=LeadSource.choices,
        default=LeadSource.MANUAL,
        verbose_name=_('Lead Source')
    )
    
    lead_source_detail = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name=_('Lead Source Detail'),
        help_text=_('Additional details about the source')
    )
    
    # Status
    lead_status = models.CharField(
        max_length=20,
        choices=LeadStatus.choices,
        default=LeadStatus.NEW,
        verbose_name=_('Lead Status')
    )
    
    # Relationships
    contact = models.ForeignKey(
        'accounts.Contact',
        on_delete=models.CASCADE,
        related_name='leads',
        verbose_name=_('Primary Contact')
    )
    
    campaign = models.ForeignKey(
        'campaign.Campaign',
        on_delete=models.SET_NULL,
        related_name='generated_leads',
        blank=True,
        null=True,
        verbose_name=_('Source Campaign')
    )
    
    source_activity = models.ForeignKey(
        'activities.Activity',
        on_delete=models.SET_NULL,
        related_name='generated_leads',
        blank=True,
        null=True,
        verbose_name=_('Source Activity'),
        help_text=_('The activity that initially generated this lead')
    )
    
    # Activities specifically for this lead
    activities = models.ManyToManyField(
        'activities.Activity',
        related_name='related_leads',
        blank=True,
        verbose_name=_('Lead Activities'),
        help_text=_('Activities specifically related to this lead')
    )
    
    # Assignment
    assigned_to = models.ForeignKey(
        'end_users.User',
        on_delete=models.SET_NULL,
        related_name='assigned_leads',
        null=True,
        verbose_name=_('Assigned To')
    )
    
    # Tracking & Analytics
    last_activity_date = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name=_('Last Activity Date')
    )
    
    last_contacted_date = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name=_('Last Contacted Date')
    )
    
    number_of_touches = models.IntegerField(
        default=0,
        verbose_name=_('Number of Touches'),
        help_text=_('Total number of interactions specifically for this lead')
    )
    
    # Conversion Tracking
    conversion_date = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name=_('Conversion Date')
    )
    
    converted_to_opportunity = models.OneToOneField(
        'opportunities.Opportunity',
        on_delete=models.SET_NULL,
        related_name='source_lead',
        blank=True,
        null=True,
        verbose_name=_('Converted to Opportunity')
    )
    
    # Qualification Data
    is_qualified = models.BooleanField(
        default=False,
        verbose_name=_('Is Qualified'),
        help_text=_('Whether this lead meets qualification criteria')
    )
    
    qualification_date = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name=_('Qualification Date')
    )
    
    # Additional Fields
    notes = models.TextField(
        blank=True,
        null=True,
        verbose_name=_('Internal Notes')
    )
    
    class Meta(ClientScopeManager.ModelMixin.get_meta_constraints(
        unique_fields=['contact', 'campaign'],
        index_fields=['lead_status', 'assigned_to']
    )):
        db_table = 'leads'
        verbose_name = _('Lead')
        verbose_name_plural = _('Leads')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['account', 'lead_status']),
            models.Index(fields=['lead_source']),
            models.Index(fields=['conversion_date']),
            models.Index(fields=['assigned_to', 'lead_status']),
            models.Index(fields=['last_activity_date']),
        ]
    
    def __str__(self):
        return f"{self.title} - {self.account.company_name} ({self.get_lead_status_display()})"
    
    def clean(self):
        """Validate the model"""
        super().clean()
        
        # Ensure contact belongs to the account
        if self.contact and self.account:
            if self.contact.account != self.account:
                raise StandardizedValidationError(
                    "Contact must belong to the specified account",
                    field_name="contact"
                )
        
        # Validate source relationships
        if self.lead_source == self.LeadSource.CAMPAIGN and not self.campaign:
            raise StandardizedValidationError(
                "Campaign is required when lead source is Campaign",
                field_name="campaign"
            )
        
        if self.lead_source == self.LeadSource.ACTIVITY and not self.source_activity:
            raise StandardizedValidationError(
                "Source activity is required when lead source is Activity",
                field_name="source_activity"
            )
    
    def save(self, *args, **kwargs):
        # Auto-assign if not assigned
        if not self.assigned_to and self.account.account_owner:
            self.assigned_to = self.account.account_owner
        
        # Update qualification status
        if self.lead_status == self.LeadStatus.QUALIFIED and not self.is_qualified:
            self.is_qualified = True
            self.qualification_date = timezone.now()
        
        super().save(*args, **kwargs)
    
    def update_activity_tracking(self):
        """Update last activity date and touch count based on lead-specific activities"""
        # Get all activities specifically related to this lead
        lead_activities = self.activities.filter(
            status='COMPLETED'  # Using string to avoid import
        ).order_by('-completed_at')
        
        if lead_activities.exists():
            self.last_activity_date = lead_activities.first().completed_at
            self.number_of_touches = lead_activities.count()
            
            # Update last contacted date for specific activity types
            contact_activities = lead_activities.filter(
                activity_type__in=['CALL', 'EMAIL', 'MEETING']
            )
            
            if contact_activities.exists():
                self.last_contacted_date = contact_activities.first().completed_at
            
            self.save(update_fields=['last_activity_date', 'last_contacted_date', 'number_of_touches'])
    
    def can_convert(self):
        """Check if lead can be converted to opportunity"""
        return (
            self.lead_status == self.LeadStatus.QUALIFIED and
            not self.converted_to_opportunity
        )
    
    def get_queued_activities(self):
        """Get lead-specific activities ordered by scheduled date"""
        return self.activities.filter(
            status='PLANNED'
        ).order_by('scheduled_start')
    
    def get_completed_activities(self):
        """Get completed lead-specific activities ordered by completion date"""
        return self.activities.filter(
            status='COMPLETED'
        ).order_by('-completed_at')
    
    def convert_to_opportunity(self, opportunity_data=None):
        """Convert lead to opportunity"""
        if not self.can_convert():
            raise StandardizedValidationError(
                "Lead must be qualified and not already converted"
            )
        
        # This will be implemented when we create the Opportunity model
        # For now, just update the status
        self.lead_status = self.LeadStatus.CONVERTED
        self.conversion_date = timezone.now()
        self.save()
        
        return None  # Will return opportunity once model is created