# apps/campaign/models/campaign_target.py

from django.db import models
from django.utils import timezone
from typing import Dict, Optional
from django.utils.translation import gettext_lazy as _
from core.client_scope import ClientScopeManager
from apps.core_apps.models import BaseModelApp
from core.exceptions import StandardizedValidationError
from core.error_messages import CoreErrorMessages, CampaignErrorMessages


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
    
    def update_status(self, new_status, save=True, validate_consistency=False):
        """
        Update the status with validation and optional consistency check
        
        Args:
            new_status (str): New status value
            save (bool): Whether to save the instance
            validate_consistency (bool): If True, validates status matches activities
            
        Raises:
            StandardizedValidationError: If status is invalid or inconsistent
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
            
            # NOUVEAU: Validation optionnelle de cohérence avec les activités
            if validate_consistency:
                expected_status = self._calculate_expected_status()
                if expected_status and new_status != expected_status:
                    raise StandardizedValidationError(
                        CampaignErrorMessages.CAMPAIGN_INVALID_STATE.format(
                            current_state=f"Status '{new_status}' inconsistent with activities (expected: '{expected_status}')"
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
    
    def _calculate_expected_status(self) -> Optional[str]:
        """
        Calcule le statut attendu basé sur les activités associées
        
        Returns:
            Optional[str]: Statut attendu ou None si indéterminable
        """
        from apps.activities.models import Activity
        
        activities = Activity.objects.filter(campaign_info__campaign_target=self)
        if not activities.exists():
            return None
        
        # Récupérer les statuts et notes
        activity_data = activities.values_list('status', 'outcome_notes')
        statuses = [data[0] for data in activity_data]
        notes = [data[1] or '' for data in activity_data]
        
        # Vérifier si un meeting a été sécurisé
        has_meeting = any(
            'meeting' in note.lower() and 'scheduled' in note.lower()
            for note in notes
        )
        
        if has_meeting:
            return self.Status.MEETING_SECURED
        
        # Analyser les statuts
        completed_count = statuses.count(Activity.Status.COMPLETED)
        cancelled_count = statuses.count(Activity.Status.CANCELLED)
        total_count = len(statuses)
        
        if completed_count == total_count:
            return self.Status.COMPLETED
        elif cancelled_count == total_count:
            return self.Status.STOPPED
        elif completed_count > 0 or cancelled_count > 0:
            return self.Status.IN_PROGRESS
        else:
            return self.Status.QUEUED
    
    def sync_status_with_activities(self, save=True) -> bool:
        """
        Synchronise automatiquement le statut avec l'état des activités
        
        Args:
            save (bool): Si True, sauvegarde automatiquement
            
        Returns:
            bool: True si le statut a changé, False sinon
        """
        try:
            expected_status = self._calculate_expected_status()
            if not expected_status:
                return False  # Pas d'activités, pas de changement
            
            if self.status != expected_status:
                old_status = self.status
                self.status = expected_status
                
                if save:
                    self.save(update_fields=['status', 'updated_at'])
                
                return True
            
            return False
            
        except Exception as e:
            raise StandardizedValidationError(
                CampaignErrorMessages.CAMPAIGN_TARGET_ORPHANED.format(
                    target=f"Failed to sync status for target {self.id}: {str(e)}"
                )
            )
    
    def get_activities_summary(self) -> Dict:
        """
        Obtient un résumé des activités pour diagnostic et debugging
        
        Returns:
            Dict: Résumé complet des activités associées
        """
        from apps.activities.models import Activity
        
        activities = Activity.objects.filter(campaign_info__campaign_target=self)
        
        summary = {
            'target_id': self.id,
            'target_type': self.get_target_type(),
            'current_status': self.status,
            'total_activities': activities.count(),
            'by_status': {},
            'by_type': {},
            'has_meeting_scheduled': False,
            'last_completed_activity': None,
            'expected_status': self._calculate_expected_status()
        }
        
        # Compter par statut d'activité
        for status_choice in Activity.Status.choices:
            status_code = status_choice[0]
            count = activities.filter(status=status_code).count()
            summary['by_status'][status_code] = count
        
        # Compter par type d'activité
        for type_choice in Activity.ActivityType.choices:
            type_code = type_choice[0]
            count = activities.filter(activity_type=type_code).count()
            if count > 0:
                summary['by_type'][type_code] = count
        
        # Vérifier présence de meeting
        meeting_notes = activities.filter(
            models.Q(outcome_notes__icontains='meeting') & 
            models.Q(outcome_notes__icontains='scheduled')
        ).exists()
        summary['has_meeting_scheduled'] = meeting_notes
        
        # Dernière activité complétée
        last_activity = activities.filter(
            status=Activity.Status.COMPLETED
        ).order_by('-completed_at').first()
        
        if last_activity:
            summary['last_completed_activity'] = {
                'id': last_activity.id,
                'type': last_activity.activity_type,
                'completed_at': last_activity.completed_at.isoformat() if last_activity.completed_at else None,
                'notes': last_activity.outcome_notes or ''
            }
        
        return summary
    
    def validate_status_consistency(self) -> Dict:
        """
        Valide la cohérence du statut actuel avec les activités
        Utile pour diagnostics et maintenance
        
        Returns:
            Dict: Rapport de validation avec détails
        """
        expected_status = self._calculate_expected_status()
        current_status = self.status
        
        is_consistent = (
            expected_status is None or  # Pas d'activités = pas de contrainte
            current_status == expected_status
        )
        
        return {
            'target_id': self.id,
            'is_consistent': is_consistent,
            'current_status': current_status,
            'expected_status': expected_status,
            'needs_sync': not is_consistent,
            'activities_count': self.get_activities_summary()['total_activities'],
            'validation_timestamp': timezone.now().isoformat()
        }
    
    def auto_update_status_if_needed(self) -> Dict:
        """
        Met à jour automatiquement le statut si incohérent
        Méthode utilitaire pour la maintenance et les hooks automatiques
        
        Returns:
            Dict: Rapport de mise à jour
        """
        validation = self.validate_status_consistency()
        
        if validation['needs_sync']:
            old_status = self.status
            status_changed = self.sync_status_with_activities(save=True)
            
            return {
                'target_id': self.id,
                'action_taken': 'status_updated',
                'old_status': old_status,
                'new_status': self.status,
                'was_inconsistent': True,
                'timestamp': timezone.now().isoformat()
            }
        else:
            return {
                'target_id': self.id,
                'action_taken': 'no_change_needed',
                'status': self.status,
                'was_inconsistent': False,
                'timestamp': timezone.now().isoformat()
            }