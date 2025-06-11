# apps/campaign/models/campaign_target.py

from django.db import models
from django.utils.translation import gettext_lazy as _
from core.client_scope import ClientScopeManager
from apps.core_apps.models import BaseModelApp
from core.exceptions import StandardizedValidationError
from core.error_messages import CoreErrorMessages


class CampaignTarget(BaseModelApp, ClientScopeManager.ModelMixin):
    """
    Links ONE target (account OR contact OR lead OR opportunity) to a campaign
    A campaign can have many targets of different types
    """
    class Status(models.TextChoices):
        PENDING = 'PENDING', _('Pending')
        IN_PROGRESS = 'IN_PROGRESS', _('In Progress')
        CALLBACK_PENDING = 'CALLBACK_PENDING', _('Callback Pending') 
        MEETING_SECURED = 'MEETING_SECURED', _('Meeting Secured')
        OPPORTUNITY_CREATED = 'OPPORTUNITY_CREATED', _('Opportunity Created')
        COMPLETED = 'COMPLETED', _('Completed')
        STOPPED = 'STOPPED', _('Stopped')
    
    campaign = models.ForeignKey(
        'campaign.Campaign',
        on_delete=models.CASCADE,
        related_name='targets',
        verbose_name=_('Campaign')
    )
    
    account = models.ForeignKey(
        'accounts.Account',
        on_delete=models.CASCADE,
        related_name='campaign_targets',
        verbose_name=_('Target Account'),
        blank=True,
        null=True
    )
    
    contact = models.ForeignKey(
        'accounts.Contact',
        on_delete=models.CASCADE,
        related_name='campaign_targets',
        verbose_name=_('Target Contact'),
        blank=True,
        null=True
    )
    
    lead = models.ForeignKey(
        'leads.Lead',
        on_delete=models.CASCADE,
        related_name='campaign_targets',
        verbose_name=_('Target Lead'),
        blank=True,
        null=True
    )
    
    # New field for opportunity as a target
    target_opportunity = models.ForeignKey(
        'opportunities.Opportunity',
        on_delete=models.CASCADE,
        related_name='targeted_by_campaigns',
        verbose_name=_('Target Opportunity'),
        blank=True,
        null=True
    )
    
    # Status tracking
    status = models.CharField(
        max_length=30,
        choices=Status.choices,
        default=Status.PENDING,
        verbose_name=_('Status')
    )
    
    activities_generated = models.BooleanField(
        default=False,
        verbose_name=_('Activities Generated')
    )

    callback_date = models.DateField(
        null=True,
        blank=True,
        verbose_name=_('Callback Date'),
        help_text=_('Date when contact requested to be called back')
    )

    no_answer_count = models.IntegerField(
        default=0,
        verbose_name=_('No Answer Count'),
        help_text=_('Number of times contact did not answer')
    )
        
    notes = models.TextField(
        blank=True,
        null=True,
        verbose_name=_('Notes')
    )
    
    # 'linked_opportunity' is used to track if this target is linked to an opportunity
    linked_opportunity = models.ForeignKey(
        'opportunities.Opportunity',
        on_delete=models.SET_NULL,
        related_name='linked_campaign_targets',
        null=True,
        blank=True,
        verbose_name=_('Linked Opportunity')
    )
    
    class Meta:
        verbose_name = _('Campaign Target')
        verbose_name_plural = _('Campaign Targets')
        indexes = [
            models.Index(fields=['campaign', 'status']),
            models.Index(fields=['account', 'status']),
            models.Index(fields=['contact', 'status']),
            models.Index(fields=['lead', 'status']),
            models.Index(fields=['target_opportunity', 'status']),
            models.Index(fields=['activities_generated']),
        ]
        constraints = [
            # Ensure unique account per campaign
            models.UniqueConstraint(
                fields=['campaign', 'account'],
                condition=models.Q(contact__isnull=True, lead__isnull=True, target_opportunity__isnull=True),
                name='unique_campaign_account_only'
            ),
            # Ensure unique contact per campaign
            models.UniqueConstraint(
                fields=['campaign', 'contact'],
                condition=models.Q(contact__isnull=False),
                name='unique_campaign_contact'
            ),
            # Ensure unique lead per campaign
            models.UniqueConstraint(
                fields=['campaign', 'lead'],
                condition=models.Q(lead__isnull=False),
                name='unique_campaign_lead'
            ),
            # Ensure unique opportunity per campaign
            models.UniqueConstraint(
                fields=['campaign', 'target_opportunity'],
                condition=models.Q(target_opportunity__isnull=False),
                name='unique_campaign_opportunity'
            )
        ]

    def __str__(self):
        if self.contact:
            return f"{self.campaign.name} - Contact: {self.contact.first_name} {self.contact.last_name} ({self.get_status_display()})"
        elif self.lead:
            return f"{self.campaign.name} - Lead: {self.lead.title} ({self.get_status_display()})"
        elif self.target_opportunity:
            return f"{self.campaign.name} - Opportunity: {self.target_opportunity.name} ({self.get_status_display()})"
        elif self.account:
            return f"{self.campaign.name} - Account: {self.account.company_name} ({self.get_status_display()})"
        return f"{self.campaign.name} - No Target ({self.get_status_display()})"
    
    def clean(self):
        """Validate that exactly one target type is set using standardized validation"""
        super().clean()
        
        try:
            target_count = sum([
                bool(self.account),
                bool(self.contact),
                bool(self.lead),
                bool(self.target_opportunity)
            ])
            
            if target_count == 0:
                raise StandardizedValidationError(
                    CoreErrorMessages.REQUIRED_FIELD.format(
                        field="Target (one of: account, contact, lead, or opportunity)"
                    )
                )
            
            if target_count > 1:
                raise StandardizedValidationError(
                    CoreErrorMessages.INVALID_FIELD.format(
                        field="Target selection (only one target type can be specified per campaign target)"
                    )
                )
                
        except StandardizedValidationError:
            # Re-raise standardized validation errors
            raise
        except Exception as e:
            # Convert any unexpected errors to standardized format
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(detail="Target validation failed")
            )
    
    def save(self, *args, **kwargs):
        """Save with standardized validation"""
        try:
            # Run clean validation first
            self.full_clean()
            super().save(*args, **kwargs)
            
        except StandardizedValidationError:
            # Re-raise standardized validation errors
            raise
        except Exception as e:
            # Convert any unexpected errors to standardized format
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(detail="Target save failed")
            )
    
    def get_target_type(self):
        """Return the type of target"""
        try:
            if self.contact:
                return 'contact'
            elif self.lead:
                return 'lead'
            elif self.target_opportunity:
                return 'opportunity'
            elif self.account:
                return 'account'
            return None
        except Exception:
            return None
    
    def get_target(self):
        """Return the actual target object"""
        try:
            if self.contact:
                return self.contact
            elif self.lead:
                return self.lead
            elif self.target_opportunity:
                return self.target_opportunity
            elif self.account:
                return self.account
            return None
        except Exception:
            return None
    
    def get_target_account(self):
        """Get the account associated with this target"""
        try:
            if self.account:
                return self.account
            elif self.contact:
                return self.contact.account
            elif self.lead:
                return self.lead.account
            elif self.target_opportunity:
                return self.target_opportunity.account
            return None
        except Exception:
            return None
    
    def mark_activities_generated(self, save=True):
        """Mark that activities have been generated for this target"""
        try:
            self.activities_generated = True
            
            if save:
                self.save()
                
        except StandardizedValidationError:
            # Re-raise standardized validation errors
            raise
        except Exception as e:
            # Convert any unexpected errors to standardized format
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(detail="Failed to mark activities as generated")
            )
    
    def update_status(self, new_status, save=True):
        """
        Update the status with validation
        
        Args:
            new_status (str): New status value
            save (bool): Whether to save the instance
            
        Raises:
            StandardizedValidationError: If status is invalid
        """
        try:
            # Validate status
            valid_statuses = [choice[0] for choice in self.Status.choices]
            if new_status not in valid_statuses:
                raise StandardizedValidationError(
                    CoreErrorMessages.INVALID_FIELD.format(
                        field=f"Status (must be one of: {', '.join(valid_statuses)})"
                    )
                )
            
            self.status = new_status
            
            if save:
                self.save()
                
        except StandardizedValidationError:
            # Re-raise standardized validation errors
            raise
        except Exception as e:
            # Convert any unexpected errors to standardized format
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(detail="Status update failed")
            )
    
    def link_opportunity(self, opportunity, save=True):
        """Link an opportunity to this target with validation"""
        try:
            if not opportunity:
                raise StandardizedValidationError(
                    CoreErrorMessages.REQUIRED_FIELD.format(field="Opportunity")
                )
                
            self.linked_opportunity = opportunity
            self.update_status(self.Status.OPPORTUNITY_CREATED, save=False)
            
            if save:
                self.save()
                
        except StandardizedValidationError:
            # Re-raise standardized validation errors
            raise
        except Exception as e:
            # Convert any unexpected errors to standardized format
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(detail="Opportunity linking failed")
            )