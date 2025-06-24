# apps/campaign/models/campaign.py - Save method update only
from django.db import models
from django.utils.translation import gettext_lazy as _
from core.client_scope import ClientScopeManager
from apps.core_apps.models import BaseModelApp
from core.exceptions import StandardizedValidationError
from core.error_messages import CoreErrorMessages, CampaignErrorMessages
from apps.sequence.sequences.sequence_dispatcher import SequenceDispatcher
from django.db.models import Q
from django.utils import timezone

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
        from .campaign_stakeholder import CampaignStakeholder
    
        User = get_user_model()
        
        # Get user IDs from CampaignStakeholder instead of doing reverse lookup
        stakeholder_user_ids = CampaignStakeholder.objects.filter(
            campaign=self,
            role=role
        ).values_list('user_id', flat=True)
    
        # Return users with those IDs
        return User.objects.filter(id__in=stakeholder_user_ids)
        
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
        from django.db.models import Q
        
        query = Q(campaign=self)
        
        if user:
            query &= Q(user=user)
            
        if role:
            query &= Q(role=role)
            
        return CampaignStakeholder.objects.filter(query).delete()[0]
    
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

    
    def get_objectives_progress_summary(self) -> dict:
        """
        Progression globale des objectifs (utilise CampaignAnalyticsService)
        
        Returns:
            dict: Résumé de progression des objectifs
        """
        try:
            from apps.campaign.services.campaign_analytics_service import CampaignAnalyticsService
            from apps.campaign.services.campaign_tracking_service import CampaignTrackingService
            
            # Obtenir les métriques via le service de tracking
            tracking_metrics = CampaignTrackingService.get_campaign_metrics(self)
            
            # Utiliser le service analytics pour le calcul
            objectives_data = CampaignAnalyticsService._calculate_objectives_vs_results(self, tracking_metrics)
            
            # Retourner le summary directement
            return objectives_data['summary']
            
        except Exception:
            return {
                'has_objectives': False,
                'total_objectives': 0,
                'achieved_objectives': 0,
                'overall_progress_percentage': 0.0,
                'primary_objectives_count': 0
            }

    def get_activities_progress_summary(self) -> dict:
        """
        Progression des activités (utilise CampaignAnalyticsService)
        
        Returns:
            dict: Résumé de progression des activités
        """
        try:
            from apps.campaign.services.campaign_analytics_service import CampaignAnalyticsService
            
            # Utiliser directement le service analytics
            return CampaignAnalyticsService._calculate_activities_progress(self)
            
        except Exception:
            return {
                'total_activities': 0,
                'completed_activities': 0,
                'planned_activities': 0,
                'cancelled_activities': 0,
                'completion_rate': 0.0
            }

    def get_timeline_progress_summary(self) -> dict:
        """
        Progression temporelle (utilise CampaignAnalyticsService)
        
        Returns:
            dict: Résumé de progression temporelle
        """
        try:
            from apps.campaign.services.campaign_analytics_service import CampaignAnalyticsService
            
            # Utiliser directement le service analytics
            return CampaignAnalyticsService._calculate_timeline_progress(self)
            
        except Exception:
            from datetime import date
            return {
                'start_date': self.start_date.isoformat() if self.start_date else None,
                'end_date': self.end_date.isoformat() if self.end_date else None,
                'current_date': date.today().isoformat(),
                'total_days': 1,
                'elapsed_days': 0,
                'remaining_days': 0,
                'time_elapsed_percentage': 0.0,
                'time_remaining_percentage': 0.0,
                'is_started': False,
                'is_ended': False
            }

    def get_conversion_rates(self) -> dict:
        """
        Taux de conversion (utilise CampaignAnalyticsService)
        
        Returns:
            dict: Taux de conversion factuels
        """
        try:
            from apps.campaign.services.campaign_analytics_service import CampaignAnalyticsService
            from apps.campaign.services.campaign_tracking_service import CampaignTrackingService
            
            # Obtenir les métriques via le service de tracking
            tracking_metrics = CampaignTrackingService.get_campaign_metrics(self)
            
            # Utiliser le service analytics pour les conversions
            conversion_data = CampaignAnalyticsService._calculate_conversion_rates(tracking_metrics)
            
            # Retourner le format simplifié pour compatibilité
            return conversion_data['conversion_rates']
            
        except Exception:
            return {
                'leads_to_meetings': {'rate_percentage': 0, 'numerator': 0, 'denominator': 0},
                'meetings_to_opportunities': {'rate_percentage': 0, 'numerator': 0, 'denominator': 0},
                'opportunities_to_deals': {'rate_percentage': 0, 'numerator': 0, 'denominator': 0},
                'overall_conversion': {'rate_percentage': 0, 'numerator': 0, 'denominator': 0}
            }

    def get_dashboard_summary(self) -> dict:
        """
        Résumé complet dashboard (utilise CampaignAnalyticsService)
        
        Returns:
            dict: Résumé factuel complet
        """
        try:
            from apps.campaign.services.campaign_analytics_service import CampaignAnalyticsService
            
            # Utiliser le service pour obtenir toutes les données d'un coup
            dashboard_response = CampaignAnalyticsService.get_campaign_dashboard_data(self)
            
            # Extraire les données de la Response standardisée
            if hasattr(dashboard_response, 'data') and 'data' in dashboard_response.data:
                dashboard_data = dashboard_response.data['data']
                
                # Retourner résumé simplifié
                return {
                    'objectives_summary': dashboard_data.get('objectives_progress', {}).get('summary', {}),
                    'activities_summary': {
                        'total_activities': dashboard_data.get('activities_progress', {}).get('total_activities', 0),
                        'completion_rate': dashboard_data.get('activities_progress', {}).get('completion_rate', 0)
                    },
                    'timeline_summary': {
                        'time_elapsed_percentage': dashboard_data.get('timeline_progress', {}).get('time_elapsed_percentage', 0),
                        'is_started': dashboard_data.get('timeline_progress', {}).get('is_started', False),
                        'is_ended': dashboard_data.get('timeline_progress', {}).get('is_ended', False)
                    },
                    'conversion_summary': dashboard_data.get('conversion_rates', {}).get('conversion_rates', {}),
                    'tracking_metrics': dashboard_data.get('tracking_metrics', {}),
                    'last_updated': dashboard_data.get('last_updated')
                }
            
            # Fallback si le format de Response change
            return self._get_fallback_dashboard_summary()
            
        except Exception:
            return self._get_fallback_dashboard_summary()

    def _get_fallback_dashboard_summary(self) -> dict:
        """Fallback pour get_dashboard_summary en cas d'erreur"""
        try:
            # Utiliser les autres méthodes helper individuellement
            return {
                'objectives_summary': self.get_objectives_progress_summary(),
                'activities_summary': {
                    'total_activities': self.get_activities_progress_summary().get('total_activities', 0),
                    'completion_rate': self.get_activities_progress_summary().get('completion_rate', 0)
                },
                'timeline_summary': {
                    'time_elapsed_percentage': self.get_timeline_progress_summary().get('time_elapsed_percentage', 0),
                    'is_started': self.get_timeline_progress_summary().get('is_started', False),
                    'is_ended': self.get_timeline_progress_summary().get('is_ended', False)
                },
                'conversion_summary': self.get_conversion_rates(),
                'tracking_metrics': self.get_metrics_summary(),
                'last_updated': timezone.now().isoformat()
            }
        except Exception:
            return {
                'objectives_summary': {'has_objectives': False},
                'activities_summary': {'total_activities': 0, 'completion_rate': 0},
                'timeline_summary': {'time_elapsed_percentage': 0, 'is_started': False, 'is_ended': False},
                'conversion_summary': {},
                'tracking_metrics': {},
                'last_updated': timezone.now().isoformat(),
                'error': 'Failed to generate dashboard summary'
            }