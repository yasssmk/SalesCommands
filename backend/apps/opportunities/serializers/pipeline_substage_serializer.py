# backend/apps/opportunities/serializers/pipeline_substage_serializer.py

from rest_framework import serializers
from django.utils import timezone
from core.client_scope import ClientScopeManager
from core.exceptions import StandardizedValidationError
from core.error_messages import CoreErrorMessages, OpportunityErrorMessages
from apps.opportunities.models import PipelineSubStage, PipelineStage
from apps.opportunities.config.pipeline_stages import PipelineStagesConfig


class PipelineSubStageSerializer(ClientScopeManager.SerializerMixin, serializers.ModelSerializer):
    """
    Serializer pour les sous-étapes de pipeline avec validation d'unicité et de logique métier
    """
    
    # Champs calculés (read-only)
    is_overdue = serializers.SerializerMethodField(read_only=True)
    days_overdue = serializers.SerializerMethodField(read_only=True)
    progress_percentage = serializers.SerializerMethodField(read_only=True)
    can_be_deleted = serializers.SerializerMethodField(read_only=True)
    activities_count = serializers.SerializerMethodField(read_only=True)
    chasing_active = serializers.SerializerMethodField(read_only=True)

    stakeholders_count = serializers.SerializerMethodField(read_only=True)
    stakeholders_names = serializers.SerializerMethodField(read_only=True)
    stakeholders_ids = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=False,
        allow_empty=True,
        help_text='List of contact IDs to assign as stakeholders'
    )
    
    # Champs pour les relations
    stage_name = serializers.CharField(source='stage.name', read_only=True)
    substage_type_display = serializers.CharField(source='get_substage_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    # Champs pour les durées calculées
    actual_duration = serializers.SerializerMethodField(read_only=True)
    remaining_duration = serializers.SerializerMethodField(read_only=True)

    # Follow-up Campaign Status Fields
    in_followup_campaign = serializers.SerializerMethodField(read_only=True)
    followup_campaign_info = serializers.SerializerMethodField(read_only=True)
    can_add_to_followup = serializers.SerializerMethodField(read_only=True)
    stakeholder_count = serializers.SerializerMethodField(read_only=True)
    
    # Expected completion date calculé
    expected_completion_date = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = PipelineSubStage
        fields = [
        # Champs de base du modèle (noms corrigés)
        'id', 'name', 'description', 'order',
        'substage_type', 'substage_type_display',
        'status', 'status_display',
        'is_active',
        'estimated_duration_days',  
        'start_date', 'end_date',
        'actual_start_date', 'actual_end_date',
        'notes',
        
        # Relations
        'stage', 'stage_name',
        'previous_substage', 'next_substage',
        
        # NOUVEAUX CHAMPS STAKEHOLDERS ✅
        'stakeholders', 'stakeholders_count', 'stakeholders_names', 'stakeholders_ids',
        
        # Champs calculés
        'expected_completion_date',
        'actual_duration', 'remaining_duration',
        'is_overdue', 'days_overdue',
        'progress_percentage',
        'can_be_deleted', 'activities_count',
        'chasing_active',
        
        # Follow-up campaign fields
        'in_followup_campaign', 'followup_campaign_info',
        'can_add_to_followup', 'stakeholder_count',  # ⚠️ GARDER stakeholder_count pour rétrocompatibilité
        
        # Timestamps
        'created_at', 'updated_at'
    ]
    read_only_fields = [
        'id', 'stage_name', 'substage_type_display', 'status_display',
        'actual_duration', 'remaining_duration', 'expected_completion_date',
        'is_overdue', 'days_overdue', 'progress_percentage',
        'can_be_deleted', 'activities_count',
        'in_followup_campaign', 'followup_campaign_info',
        'can_add_to_followup', 'stakeholder_count',
        'chasing_active', 'created_at', 'updated_at',
        'previous_substage', 'next_substage',
        # NOUVEAUX CHAMPS READ-ONLY ✅
        'stakeholders_count', 'stakeholders_names'
    ]

    def get_expected_completion_date(self, obj):
        """Calcule la date de fin prévue basée sur start_date + estimated_duration_days"""
        try:
            if obj.start_date and obj.estimated_duration_days:
                from datetime import timedelta
                return obj.start_date + timedelta(days=obj.estimated_duration_days)
            elif obj.actual_start_date and obj.estimated_duration_days:
                from datetime import timedelta
                return obj.actual_start_date.date() + timedelta(days=obj.estimated_duration_days)
            return obj.end_date
        except Exception:
            return obj.end_date
    
    def get_is_overdue(self, obj):
        """Vérifie si la sous-étape est en retard"""
        expected_date = self.get_expected_completion_date(obj)
        if expected_date and obj.status != PipelineStagesConfig.SubStageStatus.COMPLETED:
            return timezone.now().date() > expected_date
        return False
    
    def get_days_overdue(self, obj):
        """Calcule le nombre de jours de retard"""
        if self.get_is_overdue(obj):
            expected_date = self.get_expected_completion_date(obj)
            if expected_date:
                return (timezone.now().date() - expected_date).days
        return 0
    
    def get_progress_percentage(self, obj):
        """Calcule le pourcentage de progression"""
        if obj.status == PipelineStagesConfig.SubStageStatus.COMPLETED:
            return 100.0
        elif obj.status == PipelineStagesConfig.SubStageStatus.IN_PROGRESS:
            if obj.actual_start_date and obj.estimated_duration_days:
                days_elapsed = (timezone.now().date() - obj.actual_start_date.date()).days
                return min(round((days_elapsed / obj.estimated_duration_days) * 100, 2), 90.0)
            return 25.0
        elif obj.status == PipelineStagesConfig.SubStageStatus.BLOCKED:
            return 0.0
        return 0.0
    
    def get_can_be_deleted(self, obj):
        """Vérifie si la sous-étape peut être supprimée"""
        # Ne peut pas être supprimée si elle a des activités liées
        if hasattr(obj, 'direct_activities') and obj.direct_activities.exists():
            return False
        
        # Ne peut pas être supprimée si elle est en cours ou terminée
        if obj.status in [PipelineStagesConfig.SubStageStatus.IN_PROGRESS, 
                         PipelineStagesConfig.SubStageStatus.COMPLETED]:
            return False
        
        return True
    
    def get_activities_count(self, obj):
        """Nombre d'activités liées à cette sous-étape"""
        if hasattr(obj, 'direct_activities'):
            return obj.direct_activities.count()
        return 0
    
    def get_actual_duration(self, obj):
        """Durée réelle en jours"""
        if obj.actual_start_date and obj.actual_end_date:
            return (obj.actual_end_date.date() - obj.actual_start_date.date()).days
        elif obj.actual_start_date:
            return (timezone.now().date() - obj.actual_start_date.date()).days
        return 0
    
    def get_remaining_duration(self, obj):
        """Durée restante estimée"""
        if obj.status == PipelineStagesConfig.SubStageStatus.COMPLETED:
            return 0
        
        if obj.estimated_duration_days and obj.actual_start_date:
            days_elapsed = (timezone.now().date() - obj.actual_start_date.date()).days
            return max(0, obj.estimated_duration_days - days_elapsed)
        
        return obj.estimated_duration_days or 0
    
    def get_in_followup_campaign(self, obj):
        """Check if this substage is already in a follow-up campaign"""
        try:
            # Check if there are any campaign targets linked to this substage
            from apps.campaign.models import CampaignTarget, Campaign
            return CampaignTarget.objects.filter(
                substage=obj,
                campaign__campaign_type=Campaign.CampaignType.FOLLOW_UP,
                campaign__client_id=obj.client_id
            ).exists()
        except Exception:
            return False
    
    def get_followup_campaign_info(self, obj):
        """Get information about the follow-up campaign if this substage is in one"""
        try:
            from apps.campaign.models import CampaignTarget, Campaign
            
            campaign_target = CampaignTarget.objects.filter(
                substage=obj,
                campaign__campaign_type=Campaign.CampaignType.FOLLOW_UP,
                campaign__client_id=obj.client_id
            ).select_related('campaign').first()
            
            if campaign_target:
                return {
                    'campaign_id': campaign_target.campaign.id,
                    'campaign_name': campaign_target.campaign.name,
                    'target_id': campaign_target.id,
                    'target_status': campaign_target.status,
                    'added_at': campaign_target.created_at,
                    'contact_name': f"{campaign_target.contact.first_name} {campaign_target.contact.last_name}" if campaign_target.contact else None
                }
            return None
        except Exception:
            return None
    
    def get_can_add_to_followup(self, obj):
        """Check if this substage can be added to follow-up campaign"""
        # Can add if:
        # 1. Not already in follow-up campaign
        # 2. Has stakeholders (metadata exists)
        # 3. Is not completed
        # 4. Has an opportunity pipeline
        
        try:
            # Check if already in follow-up
            if self.get_in_followup_campaign(obj):
                return False
            
            # Check if completed
            if obj.status == PipelineStagesConfig.SubStageStatus.COMPLETED:
                return False
            
            # Check if has stakeholders
            if hasattr(obj, 'metadata') and obj.metadata.stakeholders.exists():
                return True
            
            # Check if has opportunity pipeline
            if obj.stage and hasattr(obj.stage, 'opportunity_pipeline'):
                return True
            
            return False
        except Exception:
            return False
    
    
    def get_chasing_active(self, obj):
        """Check if chasing is active for this substage"""
        return self.get_in_followup_campaign(obj)
    
    def validate_name(self, value):
        """Validation du nom de la sous-étape"""
        if not value or not value.strip():
            raise StandardizedValidationError(
                CoreErrorMessages.REQUIRED_FIELD,
                field_name="name"
            )
        
        # Nettoyer le nom
        value = value.strip()
        
        # Validation de la longueur
        if len(value) < 2:
            raise StandardizedValidationError(
                "SubStage name must be at least 2 characters long",
                field_name="name"
            )
        
        if len(value) > 200:
            raise StandardizedValidationError(
                "SubStage name cannot exceed 200 characters",
                field_name="name"
            )
        
        return value
    
    def validate_order(self, value):
        """Validation de l'ordre"""
        if value is not None and value < 0:
            raise StandardizedValidationError(
                "Order must be a positive number",
                field_name="order"
            )
        return value
    
    def validate_estimated_duration_days(self, value):
        """Validation de la durée estimée"""
        if value is not None and value <= 0:
            raise StandardizedValidationError(
                OpportunityErrorMessages.SUBSTAGE_DURATION_INVALID,
                field_name="estimated_duration_days"
            )
        
        # Validation des limites raisonnables
        if value is not None and value > 365:
            raise StandardizedValidationError(
                "Estimated duration cannot exceed 365 days",
                field_name="estimated_duration_days"
            )
        
        return value
    
    def validate_substage_type(self, value):
        """Validation du type de sous-étape"""
        if value not in [choice[0] for choice in PipelineStagesConfig.SubStageType.choices]:
            raise StandardizedValidationError(
                OpportunityErrorMessages.SUBSTAGE_TYPE_INVALID.format(substage_type=value),
                field_name="substage_type"
            )
        return value
    
    def validate_stage(self, value):
        """Validation de l'étape parent"""
        if value:
            client_id = self._get_client_id_from_context()
            if str(value.client_id) != str(client_id):
                raise StandardizedValidationError(
                    CoreErrorMessages.PERMISSION_DENIED,
                    field_name="stage"
                )
        return value
    
    def validate_actual_start_date(self, value):
        """Validation de la date de début"""
        if value and value > timezone.now():
            raise StandardizedValidationError(
                "Start date cannot be in the future",
                field_name="actual_start_date"
            )
        return value
    
    def validate_actual_end_date(self, value):
        """Validation de la date de fin"""
        if value and value > timezone.now():
            raise StandardizedValidationError(
                "Completion date cannot be in the future",
                field_name="actual_end_date"
            )
        return value
    
    def validate_start_date(self, value):
        """Validation de la date de début prévue"""
        return value
    
    def validate_end_date(self, value):
        """Validation de la date de fin prévue"""
        return value
    
    def validate(self, data):
        """Validation générale des données"""
        data = super().validate(data)
        
        # Récupérer les valeurs actuelles et nouvelles
        stage = data.get('stage', getattr(self.instance, 'stage', None))
        name = data.get('name')
        order = data.get('order')
        substage_type = data.get('substage_type', getattr(self.instance, 'substage_type', None))
        estimated_duration_days = data.get('estimated_duration_days', getattr(self.instance, 'estimated_duration_days', None))
        actual_start_date = data.get('actual_start_date', getattr(self.instance, 'actual_start_date', None))
        actual_end_date = data.get('actual_end_date', getattr(self.instance, 'actual_end_date', None))
        status = data.get('status', getattr(self.instance, 'status', None))
        
        # Validation de l'unicité du nom dans l'étape
        if name and stage:
            self.validate_client_scoped_uniqueness(
                data={'stage': stage.id, 'name': name},
                unique_fields=['stage', 'name'],
                model_class=PipelineSubStage,
                error_message=f"A substage with name '{name}' already exists in this stage"
            )
        
        # Validation de l'unicité de l'ordre dans l'étape
        if order is not None and stage:
            self.validate_client_scoped_uniqueness(
                data={'stage': stage.id, 'order': order},
                unique_fields=['stage', 'order'],
                model_class=PipelineSubStage,
                error_message=f"A substage with order {order} already exists in this stage"
            )
        
        # Validation des règles métier selon le type
        if substage_type == PipelineStagesConfig.SubStageType.PROCESS_INTERNE_CLIENT:
            # Les processus internes clients doivent avoir une durée estimée
            if not estimated_duration_days:
                raise StandardizedValidationError(
                    "Internal client processes must have an estimated duration",
                    field_name="estimated_duration_days"
                )
        
        # Validation des dates
        if actual_start_date and actual_end_date:
            if actual_start_date >= actual_end_date:
                raise StandardizedValidationError(
                    OpportunityErrorMessages.SUBSTAGE_DATE_INVALID,
                    field_name="actual_end_date"
                )
        
        # Validation des transitions d'état
        if self.instance and status:
            current_status = self.instance.status
            if current_status != status:
                self._validate_status_transition(current_status, status)
        
        # Validation de la cohérence statut/dates
        if status == PipelineStagesConfig.SubStageStatus.COMPLETED and not actual_end_date:
            raise StandardizedValidationError(
                "Completed substages must have a completion date",
                field_name="actual_end_date"
            )
        
        if status == PipelineStagesConfig.SubStageStatus.IN_PROGRESS and not actual_start_date:
            raise StandardizedValidationError(
                "In-progress substages must have a start date",
                field_name="actual_start_date"
            )
        
        return data
    
    def _validate_status_transition(self, current_status, new_status):
        """Valide les transitions d'état autorisées"""
        allowed_transitions = {
            PipelineStagesConfig.SubStageStatus.NOT_STARTED: [
                PipelineStagesConfig.SubStageStatus.IN_PROGRESS,
                PipelineStagesConfig.SubStageStatus.BLOCKED
            ],
            PipelineStagesConfig.SubStageStatus.IN_PROGRESS: [
                PipelineStagesConfig.SubStageStatus.COMPLETED,
                PipelineStagesConfig.SubStageStatus.BLOCKED,
                PipelineStagesConfig.SubStageStatus.NOT_STARTED
            ],
            PipelineStagesConfig.SubStageStatus.COMPLETED: [
                PipelineStagesConfig.SubStageStatus.IN_PROGRESS  # Permettre la réouverture
            ],
            PipelineStagesConfig.SubStageStatus.BLOCKED: [
                PipelineStagesConfig.SubStageStatus.IN_PROGRESS,
                PipelineStagesConfig.SubStageStatus.NOT_STARTED
            ]
        }
        
        if new_status not in allowed_transitions.get(current_status, []):
            raise StandardizedValidationError(
                f"Cannot transition from {current_status} to {new_status}",
                field_name="status"
            )
    
    def create(self, validated_data):
        """Création d'une nouvelle sous-étape"""
        try:
            # Ajouter le client_id automatiquement
            validated_data['client_id'] = self._get_client_id_from_context()
            stakeholders_ids = validated_data.pop('stakeholders_ids', [])
            
            # Créer la sous-étape
            substage = PipelineSubStage.objects.create(**validated_data)

            if stakeholders_ids:
                self._update_substage_stakeholders(substage, stakeholders_ids)
            
            return substage
            
        except Exception as e:
            raise StandardizedValidationError(
                f"SubStage creation failed: {str(e)}"
            )
    
    def update(self, instance, validated_data):
        """Mise à jour d'une sous-étape existante"""
        try:
            # Vérifier les permissions
            client_id = self._get_client_id_from_context()
            if str(instance.client_id) != str(client_id):
                raise StandardizedValidationError(
                    CoreErrorMessages.PERMISSION_DENIED
                )
            
            stakeholders_ids = validated_data.pop('stakeholders_ids', None)
            substage = super().update(instance, validated_data)
            
            # Vérifier si la sous-étape peut être modifiée
            if instance.status == PipelineStagesConfig.SubStageStatus.COMPLETED:
                # Certaines modifications sont interdites pour les sous-étapes terminées
                restricted_fields = ['stage', 'substage_type', 'estimated_duration_days']
                for field in restricted_fields:
                    if field in validated_data:
                        raise StandardizedValidationError(
                            OpportunityErrorMessages.SUBSTAGE_ALREADY_COMPLETED.format(substage_name=instance.name),
                            field_name=field
                        )
                    
            if stakeholders_ids is not None:
                self._update_substage_stakeholders(substage, stakeholders_ids)
            
            # Mettre à jour l'instance
            for attr, value in validated_data.items():
                setattr(instance, attr, value)
            
            instance.save()
            return instance
            
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                f"SubStage update failed: {str(e)}"
            )
    def _update_substage_stakeholders(self, substage, stakeholders_ids):
        """
        Met à jour les stakeholders d'un substage et déclenche la propagation vers le stage
        """
        try:
            client_id = self._get_client_id_from_context()
            
            # Récupérer les contacts
            from apps.accounts.models import Contact
            contacts = Contact.objects.filter(
                id__in=stakeholders_ids,
                client_id=client_id
            )
            
            # Mettre à jour les stakeholders
            substage.stakeholders.set(contacts)
            
            # Déclencher la mise à jour du stage parent
            substage.update_stakeholders()
            
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(detail="Failed to update substage stakeholders")
            )
        
    def get_stakeholder_count(self, obj):
        """Get number of stakeholders for this substage (REMPLACE LA MÉTHODE EXISTANTE)"""
        return obj.get_stakeholders_count()
        
    def get_stakeholders_count(self, obj):
        """Nombre total de stakeholders dans ce substage"""
        return obj.get_stakeholders_count()

    def get_stakeholders_names(self, obj):
        """Liste des noms des stakeholders pour affichage"""
        return [contact.full_name for contact in obj.get_all_stakeholders()]

    def validate_stakeholders_ids(self, value):
        """
        Valide que tous les contacts stakeholders existent et appartiennent au bon client
        """
        if not value:
            return []

        try:
            client_id = self._get_client_id_from_context()
            
            # Vérifier que tous les contacts existent et appartiennent au bon client
            from apps.accounts.models import Contact
            contacts = Contact.objects.filter(
                id__in=value,
                client_id=client_id
            )
            
            if contacts.count() != len(value):
                missing_ids = set(value) - set(contacts.values_list('id', flat=True))
                raise StandardizedValidationError(
                    CoreErrorMessages.OBJECT_NOT_FOUND.format(
                        detail=f"Contacts not found: {missing_ids}"
                    )
                )
            
            return value
            
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(detail="Stakeholder validation failed")
            )
        
    def to_representation(self, instance):
        """Enrichir la représentation avec des données calculées"""
        representation = super().to_representation(instance)
        
        # Ajouter les champs calculés
        representation['is_overdue'] = self.get_is_overdue(instance)
        representation['days_overdue'] = self.get_days_overdue(instance)
        representation['progress_percentage'] = self.get_progress_percentage(instance)
        representation['can_be_deleted'] = self.get_can_be_deleted(instance)
        representation['activities_count'] = self.get_activities_count(instance)
        representation['chasing_active'] = self.get_chasing_active(instance)
        representation['actual_duration'] = self.get_actual_duration(instance)
        representation['remaining_duration'] = self.get_remaining_duration(instance)
        
        return representation