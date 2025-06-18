# apps/campaign/serializers/campaign_serializer.py

from rest_framework import serializers
from apps.campaign.models.campaign import Campaign
from apps.campaign.models.campaign_stakeholder import CampaignStakeholder
from apps.campaign.serializers.campaign_stakeholders_serializer import CampaignStakeholderSerializer
from apps.campaign.models.campaign_result_tracking import CampaignResultTracking
from core.client_scope import ClientScopeManager
from core.exceptions import StandardizedValidationError
from core.error_messages import CoreErrorMessages
from end_users.models import User

# ✅ Import des constantes
from apps.campaign.config.variables import (
    SERIALIZER_CONFIGS,
    VALIDATION_LIMITS,
    DATE_FORMATS,
    FIELD_NAMES,
    CAMPAIGN_FORBIDDEN_STATES
)

class CampaignSerializer(ClientScopeManager.SerializerMixin, serializers.ModelSerializer):
    """Serializer for Campaign model with standardized validation"""
    
    # Read-only fields
    owner_name = serializers.SerializerMethodField(read_only=True)
    campaign_type_display = serializers.CharField(source='get_campaign_type_display', read_only=True)
    sequence_type_display = serializers.SerializerMethodField(read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    stakeholders = CampaignStakeholderSerializer(source='stakeholders.through.objects', many=True, read_only=True)
    
    # Computed fields
    has_sequence = serializers.SerializerMethodField(read_only=True)
    is_call_list = serializers.SerializerMethodField(read_only=True)
    target_summary = serializers.SerializerMethodField(read_only=True)
    has_mixed_targets = serializers.SerializerMethodField(read_only=True)

    # Stakeholder write fields
    owner_ids = serializers.PrimaryKeyRelatedField(
        many=True, 
        write_only=True, 
        queryset=User.objects.all(),
        required=False,
        error_messages={
            'does_not_exist': CoreErrorMessages.OBJECT_NOT_FOUND,
            'invalid': CoreErrorMessages.INVALID_FIELD.format(field='Owner IDs')
        }
    )
    
    executor_ids = serializers.PrimaryKeyRelatedField(
        many=True, 
        write_only=True, 
        queryset=User.objects.all(),
        required=False,
        error_messages={
            'does_not_exist': CoreErrorMessages.OBJECT_NOT_FOUND,
            'invalid': CoreErrorMessages.INVALID_FIELD.format(field='Executor IDs')
        }
    )
    
    receiver_ids = serializers.PrimaryKeyRelatedField(
        many=True, 
        write_only=True, 
        queryset=User.objects.all(),
        required=False,
        error_messages={
            'does_not_exist': CoreErrorMessages.OBJECT_NOT_FOUND,
            'invalid': CoreErrorMessages.INVALID_FIELD.format(field='Receiver IDs')
        }
    )
    
    # Campaign name with custom validation
    name = serializers.CharField(
        max_length=VALIDATION_LIMITS['MAX_CAMPAIGN_NAME_LENGTH'],
        error_messages={
            'required': CoreErrorMessages.REQUIRED_FIELD.format(field='Campaign Name'),
            'blank': CoreErrorMessages.REQUIRED_FIELD.format(field='Campaign Name'),
            'max_length': CoreErrorMessages.INVALID_FIELD.format(
                field=f'Campaign Name (maximum {VALIDATION_LIMITS["MAX_CAMPAIGN_NAME_LENGTH"]} characters)'
            )
        }
    )
    
    # Description with validation
    description = serializers.CharField(
        max_length=VALIDATION_LIMITS['MAX_DESCRIPTION_LENGTH'],
        required=False,
        allow_blank=True,
        error_messages={
            'max_length': CoreErrorMessages.INVALID_FIELD.format(
                field=f'Description (maximum {VALIDATION_LIMITS["MAX_DESCRIPTION_LENGTH"]} characters)'
            )
        }
    )
    
    # Date fields with custom validation
    start_date = serializers.DateField(
        error_messages={
            'required': CoreErrorMessages.REQUIRED_FIELD.format(field='Start Date'),
            'invalid': CoreErrorMessages.INVALID_FIELD.format(field='Start Date (format: YYYY-MM-DD)')
        }
    )
    
    end_date = serializers.DateField(
        error_messages={
            'required': CoreErrorMessages.REQUIRED_FIELD.format(field='End Date'),
            'invalid': CoreErrorMessages.INVALID_FIELD.format(field='End Date (format: YYYY-MM-DD)')
        }
    )
    
    # Computed stakeholder summaries
    owner_count = serializers.SerializerMethodField(read_only=True)
    executor_count = serializers.SerializerMethodField(read_only=True)
    receiver_count = serializers.SerializerMethodField(read_only=True)

    # === NOUVEAU : RESULT TRACKING INTÉGRÉ ===
    result_tracking = serializers.SerializerMethodField(
        help_text="Campaign results and metrics tracking"
    )
    
    # === MÉTRIQUES RAPIDES (computed fields) ===
    quick_metrics = serializers.SerializerMethodField(
        help_text="Quick overview of campaign metrics"
    )
    
    # === RÉSUMÉ DES TARGETS ===
    target_summary = serializers.SerializerMethodField(
        help_text="Summary of campaign targets by type"
    )
    
    class Meta:
        model = Campaign

        fields = SERIALIZER_CONFIGS['CAMPAIGN_FIELDS']
        read_only_fields = SERIALIZER_CONFIGS['CAMPAIGN_READ_ONLY_FIELDS']
    
    def get_owner_name(self, obj):
        """Get the full name of the campaign owner"""
        try:
            if obj.owner:
                return f"{obj.owner.first_name} {obj.owner.last_name}".strip() or obj.owner.username
            return None
        except Exception:
            return None
    
    def get_sequence_type_display(self, obj):
        """Get display name for sequence type"""
        try:
            if obj.sequence_type:
                # Get the display value from choices
                from apps.sequence.sequences.sequence_dispatcher import SequenceDispatcher
                for choice in SequenceDispatcher.SEQUENCE_CHOICES:
                    if choice[0] == obj.sequence_type:
                        return choice[1]
                return obj.sequence_type
            return "No Sequence (Call List)"
        except Exception:
            return obj.sequence_type if obj.sequence_type else "No Sequence"
    
    def get_has_sequence(self, obj):
        """Check if campaign has automated sequences"""
        try:
            return obj.has_sequence()
        except Exception:
            return False
    
    def get_is_call_list(self, obj):
        """Check if campaign is a simple call list"""
        try:
            return obj.is_call_list()
        except Exception:
            return True
    
    def get_target_summary(self, obj):
        """Get summary of targets in the campaign"""
        try:
            return obj.get_target_summary()
        except Exception:
            return {'total': 0, 'accounts': 0, 'contacts': 0, 'leads': 0, 'opportunities': 0}
    
    def get_has_mixed_targets(self, obj):
        """Check if campaign has multiple target types"""
        try:
            return obj.has_mixed_targets()
        except Exception:
            return False
    
    def get_owner_count(self, obj):
        """Get count of owners"""
        try:
            return obj.get_owners().count()
        except Exception:
            return 0
    
    def get_executor_count(self, obj):
        """Get count of executors"""
        try:
            return obj.get_executors().count()
        except Exception:
            return 0
    
    def get_receiver_count(self, obj):
        """Get count of receivers"""
        try:
            return obj.get_receivers().count()
        except Exception:
            return 0
    
    def validate_start_date(self, value):
        """Validate start date"""
        try:
            from datetime import date
            if value < date.today():
                # Allow past start dates for existing campaigns, but warn for new ones
                pass  # Could add warnings in the future
            return value
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_FIELD.format(field="Start Date")
            )
    
    def validate_end_date(self, value):
        """Validate end date"""
        try:
            from datetime import date
            if value < date.today():
                raise StandardizedValidationError(
                    CoreErrorMessages.INVALID_FIELD.format(field="End Date (cannot be in the past)")
                )
            return value
        except StandardizedValidationError:
            # Re-raise standardized validation errors
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_FIELD.format(field="End Date")
            )
    
    def validate(self, data):
        """Validate campaign data with standardized error handling"""
        try:
            # Validate dates
            start_date = data.get('start_date', self.instance.start_date if self.instance else None)
            end_date = data.get('end_date', self.instance.end_date if self.instance else None)
            
            if start_date and end_date and end_date < start_date:
                raise StandardizedValidationError(
                    CoreErrorMessages.INVALID_FIELD.format(
                        field=f"Date range (end date {end_date} must be after start date {start_date})"
                    )
                )
            
            # Validate sequence_type with campaign_type
            campaign_type = data.get('campaign_type', self.instance.campaign_type if self.instance else None)
            sequence_type = data.get('sequence_type', self.instance.sequence_type if self.instance else None)
            
            # Call list campaigns should not have a sequence
            if campaign_type == Campaign.CampaignType.CALL_LIST and sequence_type is not None:
                raise StandardizedValidationError(
                    CoreErrorMessages.INVALID_FIELD.format(
                        field="Sequence Type (Call List campaigns cannot have automated sequences)"
                    )
                )
            
            # Validate stakeholder lists don't contain duplicates
            stakeholder_fields = ['owner_ids', 'executor_ids', 'receiver_ids']
            for field_name in stakeholder_fields:
                stakeholder_list = data.get(field_name, [])
                if stakeholder_list and len(stakeholder_list) != len(set(user.id for user in stakeholder_list)):
                    raise StandardizedValidationError(
                        CoreErrorMessages.INVALID_FIELD.format(
                            field=f"{field_name.replace('_', ' ').title()} (cannot contain duplicate users)"
                        )
                    )
            
            # ✅ Validation avec constantes
            # Validate description length
            description = data.get('description', '')
            if description and len(description) > VALIDATION_LIMITS['MAX_DESCRIPTION_LENGTH']:
                raise StandardizedValidationError(
                    CoreErrorMessages.INVALID_FIELD.format(
                        field=f"Description (maximum {VALIDATION_LIMITS['MAX_DESCRIPTION_LENGTH']} characters)"
                    )
                )
            
            return data
            
        except StandardizedValidationError:
            # Re-raise standardized validation errors
            raise
        except serializers.ValidationError as e:
            # Convert DRF validation errors to standardized format
            if isinstance(e.detail, dict):
                # Multiple field errors
                error_messages = []
                for field, errors in e.detail.items():
                    if isinstance(errors, list):
                        error_messages.extend([str(error) for error in errors])
                    else:
                        error_messages.append(str(errors))
                raise StandardizedValidationError('; '.join(error_messages))
            else:
                raise StandardizedValidationError(str(e.detail))
        except Exception as e:
            # Convert any unexpected errors to standardized format
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(detail="Campaign validation failed")
            )
    
    def create(self, validated_data):
        """Create a new campaign with stakeholders and standardized error handling"""
        try:
            # Extract stakeholder data
            owner_ids = validated_data.pop('owner_ids', [])
            executor_ids = validated_data.pop('executor_ids', [])
            receiver_ids = validated_data.pop('receiver_ids', [])
            
            # Get the current user
            request = self.context.get('request')
            user = request.user if request and hasattr(request, 'user') else None
            
            # Set created_by and updated_by
            if user:
                validated_data['created_by'] = user
                validated_data['updated_by'] = user
                if 'owner' not in validated_data:
                    validated_data['owner'] = user
            
            # Create the campaign
            campaign = Campaign.objects.create(**validated_data)
            
            # Add stakeholders with error handling
            self._add_stakeholders_safely(campaign, owner_ids, executor_ids, receiver_ids, user)
            
            return campaign
            
        except StandardizedValidationError:
            # Re-raise standardized validation errors
            raise
        except Exception as e:
            # Convert any unexpected errors to standardized format
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(detail="Campaign creation failed")
            )
    
    def update(self, instance, validated_data):
        """Update a campaign with stakeholders and standardized error handling"""
        try:
            # ✅ Validation avec constantes - empêcher modification des campagnes terminées
            if instance.status in CAMPAIGN_FORBIDDEN_STATES:
                raise StandardizedValidationError(
                    CoreErrorMessages.INVALID_FIELD.format(
                        field=f"Campaign status (cannot modify {instance.get_status_display()} campaigns)"
                    )
                )
            
            # Extract stakeholder data
            owner_ids = validated_data.pop('owner_ids', None)
            executor_ids = validated_data.pop('executor_ids', None)
            receiver_ids = validated_data.pop('receiver_ids', None)
            
            # Get the current user
            request = self.context.get('request')
            user = request.user if request and hasattr(request, 'user') else None
            
            # Set updated_by
            if user:
                validated_data['updated_by'] = user
            
            # Update the instance
            for attr, value in validated_data.items():
                setattr(instance, attr, value)
            
            instance.save()
            
            # Update stakeholders if provided
            self._update_stakeholders_safely(instance, owner_ids, executor_ids, receiver_ids, user)
            
            return instance
            
        except StandardizedValidationError:
            # Re-raise standardized validation errors
            raise
        except Exception as e:
            # Convert any unexpected errors to standardized format
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(detail="Campaign update failed")
            )
    
    def _add_stakeholders_safely(self, campaign, owner_ids, executor_ids, receiver_ids, user):
        """Add stakeholders with error handling"""
        try:
            # The owner will already be added as a stakeholder via the save method
            
            # Add additional owners
            for owner in owner_ids:
                if owner != campaign.owner:  # Avoid duplicate if owner is already set
                    campaign.add_stakeholder(owner, CampaignStakeholder.StakeholderRole.OWNER, added_by=user)
            
            # Add executors
            for executor in executor_ids:
                campaign.add_stakeholder(executor, CampaignStakeholder.StakeholderRole.EXECUTOR, added_by=user)
            
            # Add receivers
            for receiver in receiver_ids:
                campaign.add_stakeholder(receiver, CampaignStakeholder.StakeholderRole.RECEIVER, added_by=user)
                
        except Exception as e:
            # If stakeholder addition fails, we should still have the campaign created
            # Log the error but don't fail the entire creation
            pass  # In production, this should be logged
    
    def _update_stakeholders_safely(self, instance, owner_ids, executor_ids, receiver_ids, user):
        """Update stakeholders with error handling"""
        try:
            # Update stakeholders if provided
            if owner_ids is not None:
                # Remove existing owners (except for the campaign.owner which is added automatically)
                instance.stakeholder_links.filter(
                    role=CampaignStakeholder.StakeholderRole.OWNER
                ).exclude(user=instance.owner).delete()
                
                # Add new owners
                for owner in owner_ids:
                    if owner != instance.owner:  # Avoid duplicate with campaign.owner
                        instance.add_stakeholder(owner, CampaignStakeholder.StakeholderRole.OWNER, added_by=user)
            
            if executor_ids is not None:
                # Remove existing executors
                instance.stakeholder_links.filter(
                    role=CampaignStakeholder.StakeholderRole.EXECUTOR
                ).delete()
                
                # Add new executors
                for executor in executor_ids:
                    instance.add_stakeholder(executor, CampaignStakeholder.StakeholderRole.EXECUTOR, added_by=user)
            
            if receiver_ids is not None:
                # Remove existing receivers
                instance.stakeholder_links.filter(
                    role=CampaignStakeholder.StakeholderRole.RECEIVER
                ).delete()
                
                # Add new receivers
                for receiver in receiver_ids:
                    instance.add_stakeholder(receiver, CampaignStakeholder.StakeholderRole.RECEIVER, added_by=user)
                    
        except Exception as e:
            # If stakeholder update fails, log but don't fail the entire update
            pass  # In production, this should be logged
    
    def get_quick_metrics(self, obj: Campaign) -> dict:
        """
        Métriques rapides pour affichage dans les listes
        """
        try:
            # Obtenir le result tracking existant (sans créer)
            try:
                result_tracking = obj.result_tracking
            except CampaignResultTracking.DoesNotExist:
                # Pas encore de tracking, retourner zéros
                return {
                    'total_results': 0,
                    'conversion_health': 'no_data',
                    'last_activity': None,
                    'needs_attention': False
                }
            
            # Calculer métriques rapides
            total_results = (
                result_tracking.leads_created_count +
                result_tracking.meetings_secured_count +
                result_tracking.opportunities_created_count +
                result_tracking.deals_closed_count
            )
            
            # Évaluer la "santé" de conversion
            conversion_health = 'healthy'
            if result_tracking.leads_created_count > 0:
                meeting_rate = (result_tracking.meetings_secured_count / result_tracking.leads_created_count) * 100
                if meeting_rate < 10:
                    conversion_health = 'poor'
                elif meeting_rate < 25:
                    conversion_health = 'needs_improvement'
            
            # Déterminer si la campagne nécessite attention
            needs_attention = (
                conversion_health == 'poor' or
                (total_results == 0 and obj.status == 'ACTIVE')
            )
            
            return {
                'total_results': total_results,
                'conversion_health': conversion_health,
                'last_activity': result_tracking.last_updated.isoformat() if result_tracking.last_updated else None,
                'needs_attention': needs_attention
            }
            
        except Exception:
            return {
                'total_results': 0,
                'conversion_health': 'error',
                'last_activity': None,
                'needs_attention': True
            }
    
    def get_target_summary(self, obj: Campaign) -> dict:
        """
        Résumé des targets de campagne (existant, optimisé)
        """
        try:
            # Utiliser la méthode existante du modèle
            return obj.get_target_summary()
        except Exception:
            return {
                'accounts': 0,
                'contacts': 0,
                'leads': 0,
                'opportunities': 0,
                'total': 0
            }
    
    def to_representation(self, instance: Campaign) -> dict:
        """
        Personnaliser la représentation selon le contexte
        """
        try:
            representation = super().to_representation(instance)
            
            context = self.context or {}
            
            # Pour les vues liste, simplifier les données
            if context.get('list_view', False):
                # Garder seulement les champs essentiels pour la liste
                simplified = {
                    'id': representation['id'],
                    'name': representation['name'],
                    'campaign_type': representation['campaign_type'],
                    'campaign_type_display': representation['campaign_type_display'],
                    'status': representation['status'],
                    'status_display': representation['status_display'],
                    'start_date': representation['start_date'],
                    'end_date': representation['end_date'],
                    'owner_name': representation['owner_name'],
                    'quick_metrics': representation['quick_metrics'],
                    'target_summary': representation['target_summary']
                }
                return simplified
            
            # Pour les vues détail, inclure tout
            return representation
            
        except Exception as e:
            # Fallback en cas d'erreur de représentation
            return {
                'id': getattr(instance, 'id', None),
                'name': getattr(instance, 'name', 'Unknown Campaign'),
                'error': f'Serialization error: {str(e)}'
            }


class CampaignListSerializer(serializers.ModelSerializer):
    """Simplified serializer for listing campaigns"""
    
    owner_name = serializers.SerializerMethodField(read_only=True)
    campaign_type_display = serializers.CharField(source='get_campaign_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    has_sequence = serializers.SerializerMethodField(read_only=True)
    target_counts = serializers.SerializerMethodField(read_only=True)
    owner_count = serializers.SerializerMethodField(read_only=True)
    executor_count = serializers.SerializerMethodField(read_only=True)
    receiver_count = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = Campaign
        # ✅ Configuration simplifiée pour la liste
        fields = [
            'id', 'name', 'campaign_type', 'campaign_type_display', 'has_sequence',
            'owner', 'owner_name', 'owner_count', 'executor_count', 'receiver_count',
            'start_date', 'end_date', 'status', 'status_display', 'quick_metrics', 'target_counts', 'created_at'
        ]
    
    def get_owner_name(self, obj):
        """Get the full name of the campaign owner"""
        if obj.owner:
            return f"{obj.owner.first_name} {obj.owner.last_name}"
        return None
    
    def get_has_sequence(self, obj):
        """Check if campaign has automated sequences"""
        return obj.has_sequence()
    
    def get_target_counts(self, obj):
        """Get simplified target counts"""
        summary = obj.get_target_summary()
        return {
            'total': summary['total'],
            'accounts': summary['accounts'],
            'contacts': summary['contacts'],
            'leads': summary['leads']
        }
    
    def get_owner_count(self, obj):
        """Get count of owners"""
        return obj.get_owners().count()
    
    def get_executor_count(self, obj):
        """Get count of executors"""
        return obj.get_executors().count()
    
    def get_receiver_count(self, obj):
        """Get count of receivers"""
        return obj.get_receivers().count()

class CampaignDetailSerializer(CampaignSerializer):
    """
    Serializer détaillé pour les vues single campaign
    """
    
    # Inclure des champs additionnels pour la vue détail
    objectives = serializers.SerializerMethodField()
    stakeholders_summary = serializers.SerializerMethodField()
    
    class Meta(CampaignSerializer.Meta):
        fields = CampaignSerializer.Meta.fields + [
            'objectives',
            'stakeholders_summary'
        ]
    
    def get_objectives(self, obj: Campaign) -> list:
        """Obtenir les objectifs de la campagne"""
        try:
            from apps.campaign.serializers.campaign_objective_serializer import CampaignObjectiveSerializer
            objectives = obj.objectives.all()
            return CampaignObjectiveSerializer(objectives, many=True, context=self.context).data
        except Exception:
            return []
    
    def get_stakeholders_summary(self, obj: Campaign) -> dict:
        """Résumé des stakeholders"""
        try:
            stakeholders = obj.stakeholder_links.select_related('user').all()
            summary = {
                'total': stakeholders.count(),
                'by_role': {},
                'owners': [],
                'executors': []
            }
            
            for link in stakeholders:
                role = link.role
                if role not in summary['by_role']:
                    summary['by_role'][role] = 0
                summary['by_role'][role] += 1
                
                user_info = {
                    'id': link.user.id,
                    'name': link.user.get_full_name() or link.user.username
                }
                
                if role == 'OWNER':
                    summary['owners'].append(user_info)
                elif role == 'EXECUTOR':
                    summary['executors'].append(user_info)
            
            return summary
            
        except Exception:
            return {
                'total': 0,
                'by_role': {},
                'owners': [],
                'executors': []
            }
    
    def to_representation(self, instance: Campaign) -> dict:
        """Force le contexte detailed pour cette classe"""
        if not self.context:
            self.context = {}
        self.context['detailed_result_tracking'] = True
        
        return super().to_representation(instance)


# Export serializers
__all__ = [
    'CampaignSerializer',
    'CampaignListSerializer',
    'CampaignDetailSerializer'
]