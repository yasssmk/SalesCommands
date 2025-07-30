# backend/apps/opportunities/serializers/opportunity_pipeline_serializer.py

from rest_framework import serializers
from decimal import Decimal
from core.client_scope import ClientScopeManager
from core.exceptions import StandardizedValidationError
from core.error_messages import CoreErrorMessages, OpportunityErrorMessages
from apps.opportunities.models import OpportunityPipeline, Opportunity, PipelineStage, PipelineSubStage
from apps.opportunities.config.pipeline_stages import PipelineStagesConfig


class OpportunityPipelineSerializer(ClientScopeManager.SerializerMixin, serializers.ModelSerializer):
    """
    Serializer pour les pipelines d'opportunité avec validation et calculs dynamiques
    """
    
    # ===== RELATIONS AVEC VALIDATION =====
    
    opportunity = serializers.PrimaryKeyRelatedField(
        queryset=Opportunity.objects.all(),
        required=True,
        error_messages={
            'required': CoreErrorMessages.REQUIRED_FIELD.format(field='Opportunity'),
            'does_not_exist': CoreErrorMessages.OBJECT_NOT_FOUND,
            'invalid': CoreErrorMessages.INVALID_FIELD.format(field='Opportunity ID must be a valid integer')
        }
    )
    
    current_stage = serializers.PrimaryKeyRelatedField(
        queryset=PipelineStage.objects.all(),
        required=False,
        allow_null=True,
        error_messages={
            'does_not_exist': OpportunityErrorMessages.STAGE_NOT_FOUND,
            'invalid': CoreErrorMessages.INVALID_FIELD.format(field='Stage ID must be a valid integer')
        }
    )
    
    current_substage = serializers.PrimaryKeyRelatedField(
        queryset=PipelineSubStage.objects.all(),
        required=False,
        allow_null=True,
        error_messages={
            'does_not_exist': OpportunityErrorMessages.SUBSTAGE_NOT_FOUND,
            'invalid': CoreErrorMessages.INVALID_FIELD.format(field='SubStage ID must be a valid integer')
        }
    )
    
    # ===== CHAMPS AVEC VALIDATION =====
    
    status = serializers.ChoiceField(
        choices=PipelineStagesConfig.PipelineStatus.choices,
        default=PipelineStagesConfig.PipelineStatus.ACTIVE,
        error_messages={
            'invalid_choice': OpportunityErrorMessages.PIPELINE_INVALID_STATE.format(
                current_state='{invalid_choice}'
            )
        }
    )
    
    expected_close_date = serializers.DateField(
        required=False,
        allow_null=True,
        error_messages={
            'invalid': CoreErrorMessages.INVALID_FIELD.format(field='Expected close date must be a valid date')
        }
    )
    
    customization_notes = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=1000,
        error_messages={
            'max_length': CoreErrorMessages.INVALID_FIELD.format(
                field='Customization notes cannot exceed 1000 characters'
            )
        }
    )
    
    # ===== CHAMPS CALCULÉS (READ-ONLY) =====

    # POSITION DÉTECTÉE AUTOMATIQUEMENT 
    
    detected_position = serializers.SerializerMethodField(read_only=True)
    position_last_updated = serializers.DateTimeField(read_only=True)
    
    # Champs individuels pour compatibilité
    detected_activity_id = serializers.IntegerField(source='detected_activity.id', read_only=True)
    detected_substage_id = serializers.IntegerField(source='detected_substage.id', read_only=True)
    detected_stage_id = serializers.IntegerField(source='detected_stage.id', read_only=True)
    
    detected_activity_title = serializers.CharField(source='detected_activity.title', read_only=True)
    detected_substage_name = serializers.CharField(source='detected_substage.name', read_only=True)
    detected_stage_name = serializers.CharField(source='detected_stage.name', read_only=True)
    
    # Métriques de progression
    progress_percentage = serializers.SerializerMethodField()
    days_since_started = serializers.SerializerMethodField()
    days_until_expected_close = serializers.SerializerMethodField()
    
    # Comptages
    total_stages_count = serializers.SerializerMethodField()
    completed_stages_count = serializers.SerializerMethodField()
    total_substages_count = serializers.SerializerMethodField()
    completed_substages_count = serializers.SerializerMethodField()
    
    # Statut et santé
    is_pipeline_overdue = serializers.SerializerMethodField()
    overdue_summary = serializers.SerializerMethodField()
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    # Position courante avec détection
    current_position = serializers.SerializerMethodField()
    
    # ===== CHAMPS POUR LES RELATIONS =====
    
    opportunity_title = serializers.CharField(source='opportunity.title', read_only=True)
    opportunity_status = serializers.CharField(source='opportunity.status', read_only=True)
    current_stage_name = serializers.CharField(source='current_stage.name', read_only=True)
    current_substage_name = serializers.CharField(source='current_substage.name', read_only=True)
    
    # Informations du deal owner
    deal_owner_name = serializers.CharField(source='opportunity.deal_owner.get_full_name', read_only=True)
    primary_contact_name = serializers.CharField(source='opportunity.contact.get_full_name', read_only=True)
    
    class Meta:
        model = OpportunityPipeline
        fields = [
            # Relations principales
            'id',
            'opportunity',
            'opportunity_title',
            'opportunity_status',
            'current_stage',
            'current_stage_name',
            'current_substage',
            'current_substage_name',
            
            # Statut et tracking
            'status',
            'status_display',
            'is_customized',
            'customization_notes',
            
            # Dates importantes
            'started_at',
            'last_updated',
            'completed_at',
            'expected_close_date',
            'actual_duration_days',

            # Position détectée automatiquement
            'detected_position',
            'position_last_updated',
            'detected_activity_id',
            'detected_substage_id', 
            'detected_stage_id',
            'detected_activity_title',
            'detected_substage_name',
            'detected_stage_name',
            
            # Métriques calculées
            'progress_percentage',
            'days_since_started',
            'days_until_expected_close',
            'total_stages_count',
            'completed_stages_count',
            'total_substages_count',
            'completed_substages_count',
            
            # Santé et statut
            'is_pipeline_overdue',
            'overdue_summary',
            'current_position',
            
            # Informations relationnelles
            'deal_owner_name',
            'primary_contact_name',
            
            # Timestamps
            'created_at',
            'updated_at'
        ]
        
        read_only_fields = [
            # Champs auto-générés
            'id',
            'created_at',
            'updated_at',
            'last_updated',
            'actual_duration_days',
            
            # Champs calculés (SerializerMethodField)
            'progress_percentage',
            'days_since_started',
            'days_until_expected_close',
            'total_stages_count',
            'completed_stages_count',
            'total_substages_count',
            'completed_substages_count',
            'is_pipeline_overdue',
            'overdue_summary',
            'current_position',
            
            # Informations relationnelles
            'opportunity_title',
            'opportunity_status',
            'current_stage_name',
            'current_substage_name',
            'status_display',
            'deal_owner_name',
            'primary_contact_name'
        ]

    # ===== MÉTHODES DE CALCUL (SerializerMethodField) =====

    def get_progress_percentage(self, obj):
        """Calcule le pourcentage de progression du pipeline"""
        try:
            return float(obj.progress_percentage)
        except (AttributeError, TypeError):
            return 0.0

    def get_days_since_started(self, obj):
        """Nombre de jours depuis le début du pipeline"""
        try:
            return obj.days_since_started
        except (AttributeError, TypeError):
            return 0

    def get_days_until_expected_close(self, obj):
        """Nombre de jours jusqu'à la date de clôture prévue"""
        try:
            return obj.days_until_expected_close
        except (AttributeError, TypeError):
            return None

    def get_total_stages_count(self, obj):
        """Nombre total d'étapes dans le pipeline"""
        try:
            return obj.get_total_stages_count()
        except (AttributeError, TypeError):
            return 0

    def get_completed_stages_count(self, obj):
        """Nombre d'étapes complétées"""
        try:
            return obj.get_completed_stages_count()
        except (AttributeError, TypeError):
            return 0

    def get_total_substages_count(self, obj):
        """Nombre total de sous-étapes dans le pipeline"""
        try:
            return obj.get_total_substages_count()
        except (AttributeError, TypeError):
            return 0

    def get_completed_substages_count(self, obj):
        """Nombre de sous-étapes complétées"""
        try:
            return obj.get_completed_substages_count()
        except (AttributeError, TypeError):
            return 0

    def get_is_pipeline_overdue(self, obj):
        """Détermine si le pipeline global est en retard"""
        try:
            return obj.is_pipeline_overdue()
        except (AttributeError, TypeError):
            return False

    def get_overdue_summary(self, obj):
        """Résumé des retards sans détails individuels"""
        try:
            return obj.get_overdue_summary()
        except (AttributeError, TypeError):
            return {'has_overdue': False, 'count': 0}

    def get_current_position(self, obj):
        """Position courante avec détection basée sur les activités"""
        try:
            return obj.get_current_position()
        except (AttributeError, TypeError):
            return {
                'current_stage': None,
                'current_substage': None,
                'detected_from_activities': False
            }

    # ===== VALIDATION PERSONNALISÉE =====

    def validate(self, data):
        """
        Validation de cohérence métier du pipeline
        L'unicité est gérée par validate_client_scoped_uniqueness
        """
        try:
            # Validation de base avec client scope
            self.validate_client_id(data.get('opportunity'))
            
            # Validation de l'unicité opportunity + client_id (un seul pipeline par opportunité)
            if 'opportunity' in data:
                self.validate_client_scoped_uniqueness(
                    data=data,
                    unique_fields=['opportunity'],
                    model_class=OpportunityPipeline,
                    error_message=OpportunityErrorMessages.PIPELINE_ALREADY_EXISTS
                )
            
            # Validation de cohérence stage/substage
            current_stage = data.get('current_stage')
            current_substage = data.get('current_substage')
            
            if current_substage and current_stage:
                if current_substage.stage != current_stage:
                    raise StandardizedValidationError(
                        OpportunityErrorMessages.INCONSISTENT_STAGE_SUBSTAGE
                    )
            
            # Validation du substage appartient bien au template de l'opportunité
            if current_substage:
                opportunity = data.get('opportunity')
                if opportunity:
                    template = opportunity.pipeline_templates.first()
                    if template and current_substage.stage.template != template:
                        raise StandardizedValidationError(
                            OpportunityErrorMessages.SUBSTAGE_NOT_FOUND
                        )
            
            # Validation du stage appartient bien au template de l'opportunité
            if current_stage:
                opportunity = data.get('opportunity')
                if opportunity:
                    template = opportunity.pipeline_templates.first()
                    if template and current_stage.template != template:
                        raise StandardizedValidationError(
                            OpportunityErrorMessages.STAGE_NOT_FOUND
                        )
            
            # Validation de la date de clôture prévue
            expected_close_date = data.get('expected_close_date')
            if expected_close_date:
                from datetime import date
                if expected_close_date < date.today():
                    raise StandardizedValidationError(
                        CoreErrorMessages.INVALID_FIELD.format(
                            field='Expected close date cannot be in the past'
                        )
                    )
            
            return data
            
        except serializers.ValidationError as e:
            raise StandardizedValidationError(e.detail)

    def create(self, validated_data):
        """
        Création d'un pipeline avec initialisation automatique
        L'unicité est validée par validate_client_scoped_uniqueness
        """
        try:
            user = self.context.get('request').user if self.context.get('request') else None
            
            # Créer le pipeline (l'unicité a été validée dans validate)
            pipeline = super().create(validated_data)
            
            # Si aucune position courante n'est définie, définir la première étape
            if not pipeline.current_stage:
                opportunity = validated_data['opportunity']
                template = opportunity.pipeline_templates.first()
                if template:
                    first_stage = template.stages.filter(is_active=True).order_by('order').first()
                    if first_stage:
                        pipeline.current_stage = first_stage
                        # Définir la première substage si disponible
                        first_substage = first_stage.substages.filter(is_active=True).order_by('order').first()
                        if first_substage:
                            pipeline.current_substage = first_substage
                        pipeline.save(user=user)
            
            return pipeline
            
        except Exception as e:
            if isinstance(e, StandardizedValidationError):
                raise
            raise StandardizedValidationError(
                OpportunityErrorMessages.PIPELINE_CREATION_FAILED.format(reason=str(e))
            )

    def update(self, instance, validated_data):
        """
        Mise à jour d'un pipeline avec validation des transitions
        """
        try:
            user = self.context.get('request').user if self.context.get('request') else None
            
            # Marquer comme personnalisé si des changements sont apportés
            if any(field in validated_data for field in ['current_stage', 'current_substage']):
                validated_data['is_customized'] = True
            
            # Mise à jour standard
            pipeline = super().update(instance, validated_data)
            
            # Recalculer la date de fin prévue si nécessaire
            if 'current_stage' in validated_data or 'current_substage' in validated_data:
                pipeline._update_expected_completion()
            
            return pipeline
            
        except Exception as e:
            if isinstance(e, StandardizedValidationError):
                raise
            raise StandardizedValidationError(
                OpportunityErrorMessages.PIPELINE_UPDATE_FAILED.format(reason=str(e))
            )

    # ===== MÉTHODES UTILITAIRES =====

    def get_serializer_context(self):
        """Contexte pour les opérations de sérialisation"""
        context = super().get_serializer_context() if hasattr(super(), 'get_serializer_context') else {}
        context.update({
            'include_calculations': True,
            'optimize_queries': True
        })
        return context
    
    def get_detected_position(self, obj):
        """Position détectée automatiquement avec métadonnées"""
        try:
            return {
                'activity': {
                    'id': obj.detected_activity.id if obj.detected_activity else None,
                    'title': obj.detected_activity.title if obj.detected_activity else None,
                    'status': obj.detected_activity.status if obj.detected_activity else None
                },
                'substage': {
                    'id': obj.detected_substage.id if obj.detected_substage else None,
                    'name': obj.detected_substage.name if obj.detected_substage else None,
                    'order': obj.detected_substage.order if obj.detected_substage else None
                },
                'stage': {
                    'id': obj.detected_stage.id if obj.detected_stage else None,
                    'name': obj.detected_stage.name if obj.detected_stage else None,
                    'order': obj.detected_stage.order if obj.detected_stage else None
                },
                'last_updated': obj.position_last_updated
            }
        except Exception:
            return {
                'activity': {'id': None, 'title': None, 'status': None},
                'substage': {'id': None, 'name': None, 'order': None},
                'stage': {'id': None, 'name': None, 'order': None},
                'last_updated': obj.position_last_updated
            }