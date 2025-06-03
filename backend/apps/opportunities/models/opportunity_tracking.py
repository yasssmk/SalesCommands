# apps/opportunities/models/opportunity_tracking.py

from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from core.client_scope import ClientScopeManager
from apps.core_apps.models import BaseModelApp
from core.exceptions import StandardizedValidationError


class OpportunitySource(BaseModelApp, ClientScopeManager.ModelMixin):
    """
    Tracks the origin of an opportunity and conversion workflow
    """
    
    class SourceType(models.TextChoices):
        LEAD = 'LEAD', _('Lead Conversion')
        CAMPAIGN = 'CAMPAIGN', _('Campaign')
        MANUAL = 'MANUAL', _('Manual Creation')
        INBOUND = 'INBOUND', _('Inbound Request')
        EXISTING_CUSTOMER = 'EXISTING_CUSTOMER', _('Existing Customer')
        PARTNER = 'PARTNER', _('Partner Referral')
    
    class ConversionStatus(models.TextChoices):
        PENDING = 'PENDING', _('Pending Approval')
        ACCEPTED = 'ACCEPTED', _('Accepted')
        REJECTED = 'REJECTED', _('Rejected')
        NOT_APPLICABLE = 'NOT_APPLICABLE', _('Not Applicable')
    
    opportunity = models.OneToOneField(
        'opportunities.Opportunity',
        on_delete=models.CASCADE,
        related_name='source',
        verbose_name=_('Opportunity')
    )
    
    source_type = models.CharField(
        max_length=20,
        choices=SourceType.choices,
        default=SourceType.MANUAL,
        verbose_name=_('Source Type')
    )
    
    # Related entities based on source
    source_lead = models.ForeignKey(
        'leads.Lead',
        on_delete=models.SET_NULL,
        related_name='generated_opportunities',
        null=True,
        blank=True,
        verbose_name=_('Source Lead')
    )
    
    source_campaign = models.ForeignKey(
        'campaign.Campaign',
        on_delete=models.SET_NULL,
        related_name='generated_opportunities',
        null=True,
        blank=True,
        verbose_name=_('Source Campaign')
    )
    
    source_campaign_target = models.ForeignKey(
        'campaign.CampaignTarget',
        on_delete=models.SET_NULL,
        related_name='generated_opportunities',
        null=True,
        blank=True,
        verbose_name=_('Campaign Target')
    )
    
    partner = models.ForeignKey(
        'accounts.Account',
        on_delete=models.SET_NULL,
        related_name='partner_opportunities',
        null=True,
        blank=True,
        verbose_name=_('Partner')
    )
    
    # Conversion workflow
    created_by = models.ForeignKey(
        'end_users.User',
        on_delete=models.SET_NULL,
        related_name='created_opportunities',
        null=True,
        verbose_name=_('Created By')
    )
    
    conversion_status = models.CharField(
        max_length=20,
        choices=ConversionStatus.choices,
        default=ConversionStatus.NOT_APPLICABLE,
        verbose_name=_('Conversion Status')
    )
    
    conversion_date = models.DateTimeField(
        default=timezone.now,
        verbose_name=_('Conversion Date')
    )
    
    conversion_notes = models.TextField(
        blank=True,
        null=True,
        verbose_name=_('Conversion Notes')
    )
    
    # For approval workflow
    assigned_to = models.ForeignKey(
        'end_users.User',
        on_delete=models.SET_NULL,
        related_name='assigned_opportunity_conversions',
        null=True,
        blank=True,
        verbose_name=_('Assigned To')
    )
    
    approval_date = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Approval Date')
    )
    
    rejection_reason = models.TextField(
        blank=True,
        null=True,
        verbose_name=_('Rejection Reason')
    )
    
    # Metrics
    days_as_lead = models.IntegerField(
        default=0,
        verbose_name=_('Days as Lead'),
        help_text=_('Days from lead creation to opportunity conversion')
    )
    
    class Meta(ClientScopeManager.ModelMixin.get_meta_constraints(
        unique_fields=['opportunity'],
        index_fields=['source_type', 'conversion_status']
    )):
        db_table = 'opportunity_sources'
        verbose_name = _('Opportunity Source')
        verbose_name_plural = _('Opportunity Sources')
        indexes = [
            models.Index(fields=['source_lead']),
            models.Index(fields=['source_campaign']),
            models.Index(fields=['created_by']),
            models.Index(fields=['assigned_to']),
            models.Index(fields=['conversion_date']),
        ]
    
    def __str__(self):
        return f"Source for {self.opportunity.title}: {self.get_source_type_display()}"
    
    def accept_conversion(self, user, notes=None):
        """Accept the opportunity conversion"""
        if self.conversion_status != self.ConversionStatus.PENDING:
            raise StandardizedValidationError("This opportunity is not pending approval")
        
        self.conversion_status = self.ConversionStatus.ACCEPTED
        self.approval_date = timezone.now()
        
        if notes:
            self.conversion_notes = notes if not self.conversion_notes else f"{self.conversion_notes}\n\n{notes}"
        
        # Update opportunity owner to the accepting user
        self.opportunity.deal_owner = user
        self.opportunity.save(update_fields=['deal_owner'])
        
        self.save()
        
        # Create history entry
        self.opportunity.create_history_entry(
            'CONVERSION_ACCEPTED',
            f"Conversion accepted by {user}",
            notes
        )
        
        return self
    
    def reject_conversion(self, reason=None):
        """Reject the opportunity conversion"""
        if self.conversion_status != self.ConversionStatus.PENDING:
            raise StandardizedValidationError("This opportunity is not pending approval")
        
        self.conversion_status = self.ConversionStatus.REJECTED
        self.approval_date = timezone.now()
        
        if reason:
            self.rejection_reason = reason
        
        self.save()
        
        # Create history entry
        self.opportunity.create_history_entry(
            'CONVERSION_REJECTED',
            "Conversion rejected",
            reason
        )
        
        return self
    
    @classmethod
    def from_lead(cls, opportunity, lead, assignee=None, notes=None):
        """Create opportunity source from a lead"""
        # Calculate days as lead
        days_as_lead = 0
        if lead.created_at:
            delta = timezone.now() - lead.created_at
            days_as_lead = delta.days
        
        # Determine if approval is needed
        conversion_status = cls.ConversionStatus.NOT_APPLICABLE
        if assignee and assignee != lead.assigned_to:
            conversion_status = cls.ConversionStatus.PENDING
        
        # Create source tracking
        source = cls.objects.create(
            opportunity=opportunity,
            source_type=cls.SourceType.LEAD,
            source_lead=lead,
            conversion_date=timezone.now(),
            conversion_notes=notes,
            created_by=lead.assigned_to,
            assigned_to=assignee,
            conversion_status=conversion_status,
            days_as_lead=days_as_lead
        )
        
        # Create history entry
        opportunity.create_history_entry(
            'CONVERSION_CREATED',
            f"Converted from Lead: {lead.title}",
            notes
        )
        
        return source


class OpportunityActivity(BaseModelApp, ClientScopeManager.ModelMixin):
    """
    Links activities to opportunities with additional context
    """
    
    opportunity = models.ForeignKey(
        'opportunities.Opportunity',
        on_delete=models.CASCADE,
        related_name='activity_links',
        verbose_name=_('Opportunity')
    )
    
    activity = models.ForeignKey(
        'activities.Activity',
        on_delete=models.CASCADE,
        related_name='opportunity_links',
        verbose_name=_('Activity')
    )
    
    is_key_activity = models.BooleanField(
        default=False,
        verbose_name=_('Is Key Activity'),
        help_text=_('Whether this is a key milestone activity')
    )
    
    created_by = models.ForeignKey(
        'end_users.User',
        on_delete=models.SET_NULL,
        related_name='+',  # No reverse relation
        null=True,
        verbose_name=_('Created By')
    )
    
    notes = models.TextField(
        blank=True,
        null=True,
        verbose_name=_('Context Notes'),
        help_text=_('Notes about how this activity relates to the opportunity')
    )
    
    class Meta(ClientScopeManager.ModelMixin.get_meta_constraints(
        unique_fields=['opportunity', 'activity'],
        index_fields=['is_key_activity']
    )):
        db_table = 'opportunity_activities'
        verbose_name = _('Opportunity Activity')
        verbose_name_plural = _('Opportunity Activities')
    
    def __str__(self):
        return f"{self.activity} - {self.opportunity.title}"


class OpportunityHistory(BaseModelApp, ClientScopeManager.ModelMixin):
    """
    Records history of important changes to an opportunity
    """
    
    class ChangeType(models.TextChoices):
        CREATED = 'CREATED', _('Created')
        STATUS_CHANGE = 'STATUS_CHANGE', _('Status Change')
        STAGE_CHANGE = 'STAGE_CHANGE', _('Stage Change')
        OWNER_CHANGE = 'OWNER_CHANGE', _('Owner Change')
        AMOUNT_CHANGE = 'AMOUNT_CHANGE', _('Amount Change')
        DATE_CHANGE = 'DATE_CHANGE', _('Date Change')
        CONVERSION_CREATED = 'CONVERSION_CREATED', _('Conversion Created')
        CONVERSION_ACCEPTED = 'CONVERSION_ACCEPTED', _('Conversion Accepted')
        CONVERSION_REJECTED = 'CONVERSION_REJECTED', _('Conversion Rejected')
        CUSTOM = 'CUSTOM', _('Custom')
    
    opportunity = models.ForeignKey(
        'opportunities.Opportunity',
        on_delete=models.CASCADE,
        related_name='history',
        verbose_name=_('Opportunity')
    )
    
    change_type = models.CharField(
        max_length=30,
        choices=ChangeType.choices,
        verbose_name=_('Change Type')
    )
    
    description = models.CharField(
        max_length=255,
        verbose_name=_('Description')
    )
    
    details = models.TextField(
        blank=True,
        null=True,
        verbose_name=_('Details')
    )
    
    change_date = models.DateTimeField(
        default=timezone.now,
        verbose_name=_('Change Date')
    )
    
    changed_by = models.ForeignKey(
        'end_users.User',
        on_delete=models.SET_NULL,
        related_name='+',  # No reverse relation
        null=True,
        verbose_name=_('Changed By')
    )
    
    class Meta:
        db_table = 'opportunity_history'
        verbose_name = _('Opportunity History')
        verbose_name_plural = _('Opportunity History')
        ordering = ['-change_date']
        indexes = [
            models.Index(fields=['opportunity', 'change_type']),
            models.Index(fields=['change_date']),
        ]
    
    def __str__(self):
        return f"{self.get_change_type_display()}: {self.description}"