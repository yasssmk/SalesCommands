# apps/campaign/models/campaign.py - Save method update only
from django.db import models
from django.utils.translation import gettext_lazy as _
from core.client_scope import ClientScopeManager
from apps.core_apps.models import BaseModelApp
from core.exceptions import StandardizedValidationError
from core.error_messages import CoreErrorMessages, CampaignErrorMessages
from apps.sequence.sequences.sequence_dispatcher import SequenceDispatcher
from django.db.models import Q

class Campaign(BaseModelApp, ClientScopeManager.ModelMixin):
    """
    Represents a sales campaign with targeting criteria and objectives
    """
    class CampaignType(models.TextChoices):
        HUNTING = 'HUNTING', _('New Account Hunting')
        UPSELL = 'UPSELL', _('Existing Account Upsell')
        FOLLOW_UP = 'FOLLOW_UP', _('Opportunity Follow-up')
        RENEWAL = 'RENEWAL', _('Contract Renewal')
        CHASING = 'CHASING', _('Chasing')
        CALL_LIST = 'CALL_LIST', _('Call List')
        LEAD_NURTURE = 'LEAD_NURTURE', _('Lead Nurturing')
        CUSTOM = 'CUSTOM', _('Custom Campaign')
    
    name = models.CharField(
        max_length=100,
        verbose_name=_('Campaign Name')
    )
    
    description = models.TextField(
        blank=True,
        null=True,
        verbose_name=_('Description')
    )
    
    campaign_type = models.CharField(
        max_length=20,
        choices=CampaignType.choices,
        verbose_name=_('Campaign Type')
    )
    
    sequence_type = models.CharField(
        max_length=30,
        choices=SequenceDispatcher.SEQUENCE_CHOICES,
        default=None,
        blank=True,
        null=True,
        verbose_name=_('Sequence Type'),
        help_text=_('Leave empty for campaigns without automated sequences (e.g., call lists)')
    )
    
    owner = models.ForeignKey(
        'end_users.User',
        on_delete=models.SET_NULL,  
        related_name='owned_campaigns',
        null=True,  # Make it nullable
        blank=True,  # Allow blank in forms
        verbose_name=_('Campaign Owner (Legacy)')
    )
    
    # Add this field to establish the M2M relationship
    stakeholders = models.ManyToManyField(
    'end_users.User',
    through='campaign.CampaignStakeholder',
    through_fields=('campaign', 'user'),  # Specify which fields to use
    related_name='participated_campaigns',  # Change related_name to avoid clash
    verbose_name=_('Stakeholders')
)
    
    start_date = models.DateField(
        verbose_name=_('Start Date')
    )
    
    end_date = models.DateField(
        verbose_name=_('End Date')
    )
    
    status = models.CharField(
        max_length=20,
        choices=[
            ('DRAFT', 'Draft'),
            ('ACTIVE', 'Active'),
            ('PAUSED', 'Paused'),
            ('COMPLETED', 'Completed'),
            ('CANCELLED', 'Cancelled'),
        ],
        default='DRAFT'
    )
    
    class Meta:
        verbose_name = _('Campaign')
        verbose_name_plural = _('Campaigns')
        indexes = [
            models.Index(fields=['owner', 'start_date']),
            models.Index(fields=['campaign_type']),
            models.Index(fields=['sequence_type']),
        ]

    def __str__(self):
        return f"{self.name} ({self.get_campaign_type_display()})"
    
    def has_sequence(self):
        """Check if this campaign uses automated sequences"""
        return self.sequence_type is not None
    
    def is_call_list(self):
        """Check if this is a simple call list campaign (no sequences)"""
        return self.sequence_type is None
    
    def get_target_summary(self):
        """Get a summary of target types in this campaign"""
        summary = {
            'accounts': self.targets.filter(account__isnull=False, contact__isnull=True, lead__isnull=True, target_opportunity__isnull=True).count(),
            'contacts': self.targets.filter(contact__isnull=False).count(),
            'leads': self.targets.filter(lead__isnull=False).count(),
            'opportunities': self.targets.filter(target_opportunity__isnull=False).count(),
            'total': self.targets.count()
        }
        return summary

    def has_mixed_targets(self):
        """Check if campaign has multiple target types"""
        summary = self.get_target_summary()
        target_types = sum([
            1 if summary['accounts'] > 0 else 0,
            1 if summary['contacts'] > 0 else 0,
            1 if summary['leads'] > 0 else 0,
            1 if summary['opportunities'] > 0 else 0
        ])
        return target_types > 1
    
    def add_stakeholder(self, user, role, added_by=None):
        """
        Add a stakeholder to this campaign with a specific role
        
        Args:
            user: The user to add
            role: The role to assign (from CampaignStakeholder.StakeholderRole)
            added_by: The user who is adding this stakeholder
            
        Returns:
            The created CampaignStakeholder instance
        """
        from .campaign_stakeholder import CampaignStakeholder
        
        # Check if this user already has this role
        existing = CampaignStakeholder.objects.filter(
            campaign=self,
            user=user,
            role=role
        ).first()
        
        if existing:
            return existing
            
        # Create new stakeholder
        return CampaignStakeholder.objects.create(
            campaign=self,
            user=user,
            role=role,
            added_by=added_by,
            client_id=self.client_id
        )
    
    def remove_stakeholder(self, user, role=None):
        """
        Remove a stakeholder from this campaign
        
        Args:
            user: The user to remove (if None, removes all users with the given role)
            role: The role to remove (if None, removes all roles for the given user)
            
        Returns:
            int: Number of stakeholders removed
        """
        from .campaign_stakeholder import CampaignStakeholder
        
        query = Q(campaign=self)
        
        if user:
            query &= Q(user=user)
            
        if role:
            query &= Q(role=role)
            
        return CampaignStakeholder.objects.filter(query).delete()[0]
    
    def get_stakeholders_by_role(self, role):
        """
        Get all stakeholders with a specific role
        
        Args:
            role: The role to filter by (from CampaignStakeholder.StakeholderRole)
            
        Returns:
            QuerySet of User objects with the specified role
        """
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        return User.objects.filter(
            campaign_roles__campaign=self,
            campaign_roles__role=role
        )
    
    def get_owners(self):
        """Get campaign owners"""
        from .campaign_stakeholder import CampaignStakeholder
        return self.get_stakeholders_by_role(CampaignStakeholder.StakeholderRole.OWNER)
    
    def get_executors(self):
        """Get campaign executors"""
        from .campaign_stakeholder import CampaignStakeholder
        return self.get_stakeholders_by_role(CampaignStakeholder.StakeholderRole.EXECUTOR)
    
    def get_receivers(self):
        """Get campaign receivers"""
        from .campaign_stakeholder import CampaignStakeholder
        return self.get_stakeholders_by_role(CampaignStakeholder.StakeholderRole.RECEIVER)
    
    def clean(self):
        """Validate campaign data using standardized validation"""
        super().clean()
        
        try:
            # Ensure end date is after start date
            if self.end_date and self.start_date and self.end_date < self.start_date:
                raise StandardizedValidationError(
                    CoreErrorMessages.INVALID_FIELD.format(
                        field=f"Date range (end date {self.end_date} must be after start date {self.start_date})"
                    )
                )

            # Validate end date is not in the past
            from django.utils import timezone
            today = timezone.now().date()
            if self.end_date and self.end_date < today:
                raise StandardizedValidationError(
                    CoreErrorMessages.INVALID_FIELD.format(
                        field=f"End date (must be in the future, current date: {today})"
                    )
                )
                
        except StandardizedValidationError:
            # Re-raise standardized validation errors
            raise
        except Exception as e:
            # Convert any unexpected errors to standardized format
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(detail="Campaign validation failed")
            )
        
    def save(self, *args, **kwargs):
        """Save with standardized validation"""
        try:
            # Run clean validation first
            self.full_clean()

            if self.pk:  # Campaign existe déjà
                try:
                    old_instance = Campaign.objects.get(pk=self.pk)
                    old_sequence_type = old_instance.sequence_type
                    new_sequence_type = self.sequence_type
                    
                    # Si le sequence_type change
                    if old_sequence_type != new_sequence_type:
                        # Vérifier s'il y a des activités existantes
                        from apps.activities.models import Activity
                        existing_activities = Activity.objects.filter(
                            campaign_info__campaign=self
                        ).exists()
                        
                        if existing_activities:
                            raise StandardizedValidationError(
                                CampaignErrorMessages.CAMPAIGN_TRANSITION_INVALID.format(
                                    from_state=f"sequence_type '{old_sequence_type or 'None'}'",
                                    to_state=f"sequence_type '{new_sequence_type or 'None'}' (campaign has existing activities)"
                                )
                            )
                            
                except Campaign.DoesNotExist:
                    # Campaign en cours de création, pas de validation nécessaire
                    pass
            
            super().save(*args, **kwargs)

            # If this is a new campaign and owner is set, add owner as OWNER stakeholder
            if self.owner and not hasattr(self, '_owner_added_as_stakeholder'):
                from .campaign_stakeholder import CampaignStakeholder
                self.add_stakeholder(self.owner, CampaignStakeholder.StakeholderRole.OWNER)
                self._owner_added_as_stakeholder = True
                
        except StandardizedValidationError:
            # Re-raise standardized validation errors
            raise
        except Exception as e:
            # Convert any unexpected errors to standardized format
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(detail="Campaign save failed")
            )
    
    def get_or_create_result_tracking(self):
        """
        Obtenir ou créer le CampaignResultTracking pour cette campagne
        
        Returns:
            CampaignResultTracking: Instance de tracking
        """
        try:
            from apps.campaign.models.campaign_result_tracking import CampaignResultTracking
            result_tracking, created = CampaignResultTracking.objects.get_or_create(
                campaign=self,
                defaults={'client_id': self.client_id}
            )
            return result_tracking
        except Exception as e:

            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(
                    detail=f"Failed to get result tracking: {str(e)}"
                )
            )

    def get_metrics_summary(self) -> dict:
        """
        Obtenir un résumé rapide des métriques de campagne
        
        Returns:
            dict: Métriques essentielles
        """
        try:
            result_tracking = self.get_or_create_result_tracking()
            return {
                'leads_created': result_tracking.leads_created_count,
                'meetings_secured': result_tracking.meetings_secured_count,
                'opportunities_created': result_tracking.opportunities_created_count,
                'deals_closed': result_tracking.deals_closed_count,
                'pipeline_value': float(result_tracking.pipeline_value_created),
                'revenue_generated': float(result_tracking.revenue_generated)
            }
        except Exception:
            return {
                'leads_created': 0,
                'meetings_secured': 0,
                'opportunities_created': 0,
                'deals_closed': 0,
                'pipeline_value': 0.0,
                'revenue_generated': 0.0
            }

    def get_conversion_health(self) -> str:
        """
        Évaluer la santé des conversions de la campagne
        
        Returns:
            str: 'healthy', 'needs_improvement', 'poor', 'no_data'
        """
        try:
            metrics = self.get_metrics_summary()
            
            if metrics['leads_created'] == 0:
                return 'no_data'
            
            # Calculer taux de conversion leads -> meetings
            meeting_rate = (metrics['meetings_secured'] / metrics['leads_created']) * 100
            
            if meeting_rate >= 25:
                return 'healthy'
            elif meeting_rate >= 10:
                return 'needs_improvement'
            else:
                return 'poor'
                
        except Exception:
            return 'no_data'

    def needs_attention(self) -> bool:
        """
        Déterminer si la campagne nécessite attention
        
        Returns:
            bool: True si attention requise
        """
        try:
            # Campagne active sans résultats
            if self.status == 'ACTIVE':
                metrics = self.get_metrics_summary()
                total_results = sum([
                    metrics['leads_created'],
                    metrics['meetings_secured'], 
                    metrics['opportunities_created'],
                    metrics['deals_closed']
                ])
                
                if total_results == 0:
                    return True
            
            # Conversions faibles
            if self.get_conversion_health() == 'poor':
                return True
                
            return False
            
        except Exception:
            return True  # En cas d'erreur, mieux vaut signaler attention requise