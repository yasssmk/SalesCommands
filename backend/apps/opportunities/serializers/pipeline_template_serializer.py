# backend/apps/opportunities/serializers/pipeline_template_serializer.py

from rest_framework import serializers
from core.client_scope import ClientScopeManager
from core.exceptions import StandardizedValidationError
from core.error_messages import CoreErrorMessages, OpportunityErrorMessages
from apps.opportunities.models import PipelineTemplate


class PipelineTemplateSerializer(ClientScopeManager.SerializerMixin, serializers.ModelSerializer):
    """
    Serializer pour les templates de pipeline avec validation d'unicité
    """
    
    # Champs calculés (read-only)
    stages_count = serializers.IntegerField(read_only=True)
    is_in_use = serializers.BooleanField(read_only=True)
    can_be_deleted = serializers.BooleanField(read_only=True)
    opportunities_count = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = PipelineTemplate
        fields = [
            'id',
            'name',
            'description',
            'order',
            'is_active',
            'is_default',
            'stages_count',
            'is_in_use',
            'can_be_deleted',
            'opportunities_count',
            'created_at',
            'updated_at'
        ]
        read_only_fields = [
            'id',
            'stages_count',
            'is_in_use',
            'can_be_deleted',
            'opportunities_count',
            'created_at',
            'updated_at'
        ]
    
    def get_stages_count(self, obj):
        """Nombre d'étapes actives dans ce template"""
        return obj.stages.filter(is_active=True).count()
    
    def get_is_in_use(self, obj):
        """Vérifie si le template est utilisé par des opportunités"""
        return obj.opportunity_pipelines.exists()
    
    def get_can_be_deleted(self, obj):
        """Vérifie si le template peut être supprimé"""
        # Ne peut pas être supprimé s'il est utilisé par des opportunités
        return not obj.opportunity_pipelines.exists()
    
    def get_opportunities_count(self, obj):
        """Nombre d'opportunités utilisant ce template"""
        return obj.opportunity_pipelines.count()
    
    def validate_name(self, value):
        """Validation de l'unicité du nom dans le client"""
        if not value or not value.strip():
            raise StandardizedValidationError(
                CoreErrorMessages.REQUIRED_FIELD,
                field_name="name"
            )
        
        # Nettoyer le nom
        value = value.strip()
        
        # Validation de la longueur
        if len(value) < 3:
            raise StandardizedValidationError(
                "Template name must be at least 3 characters long",
                field_name="name"
            )
        
        if len(value) > 200:
            raise StandardizedValidationError(
                "Template name cannot exceed 200 characters",
                field_name="name"
            )
        
        # Utiliser la méthode ClientScopeManager pour l'unicité
        self.validate_client_scoped_uniqueness(
            data={'name': value},
            unique_fields=['name'],
            model_class=PipelineTemplate,
            error_message=OpportunityErrorMessages.TEMPLATE_ALREADY_EXISTS
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
    
    def validate_is_default(self, value):
        """Validation du statut par défaut"""
        if value is True:
            client_id = self._get_client_id_from_context()
            
            # Vérifier qu'il n'y a pas déjà un template par défaut
            existing_default = PipelineTemplate.objects.filter(
                client_id=client_id,
                is_default=True,
                is_active=True
            ).exclude(id=self.instance.id if self.instance else None).first()
            
            if existing_default:
                raise StandardizedValidationError(
                    f"Template '{existing_default.name}' is already set as default. Only one default template is allowed per client.",
                    field_name="is_default"
                )
        
        return value
    
    def validate(self, data):
        """Validation générale des données"""
        data = super().validate(data)
        
        # Vérifier la cohérence des statuts
        is_active = data.get('is_active', getattr(self.instance, 'is_active', True))
        is_default = data.get('is_default', getattr(self.instance, 'is_default', False))
        
        # Un template par défaut doit être actif
        if is_default and not is_active:
            raise StandardizedValidationError(
                "A default template must be active",
                field_name="is_active"
            )
        
        # Validation des permissions pour les templates en cours d'utilisation
        if self.instance and self.instance.opportunity_pipelines.exists():
            # Vérifier si on essaie de désactiver un template en cours d'utilisation
            if not is_active:
                raise StandardizedValidationError(
                    OpportunityErrorMessages.TEMPLATE_IN_USE.format(
                        template_name=self.instance.name,
                        pipelines_count=self.instance.opportunity_pipelines.count()
                    ),
                    field_name="is_active"
                )
        
        return data
    
    def create(self, validated_data):
        """Création d'un nouveau template"""
        try:
            # Ajouter le client_id automatiquement
            validated_data['client_id'] = self._get_client_id_from_context()
            
            # Créer le template
            template = PipelineTemplate.objects.create(**validated_data)
            
            return template
            
        except Exception as e:
            raise StandardizedValidationError(
                OpportunityErrorMessages.TEMPLATE_CREATION_FAILED.format(reason=str(e))
            )
    
    def update(self, instance, validated_data):
        """Mise à jour d'un template existant"""
        try:
            # Vérifier les permissions
            client_id = self._get_client_id_from_context()
            if str(instance.client_id) != str(client_id):
                raise StandardizedValidationError(
                    CoreErrorMessages.PERMISSION_DENIED
                )
            
            # Mettre à jour l'instance
            for attr, value in validated_data.items():
                setattr(instance, attr, value)
            
            instance.save()
            return instance
            
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                OpportunityErrorMessages.TEMPLATE_UPDATE_FAILED.format(reason=str(e))
            )
    
    def to_representation(self, instance):
        """Enrichir la représentation avec des données calculées"""
        representation = super().to_representation(instance)
        
        # Ajouter les champs calculés
        representation['stages_count'] = self.get_stages_count(instance)
        representation['is_in_use'] = self.get_is_in_use(instance)
        representation['can_be_deleted'] = self.get_can_be_deleted(instance)
        representation['opportunities_count'] = self.get_opportunities_count(instance)
        
        return representation