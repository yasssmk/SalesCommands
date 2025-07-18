# backend/apps/opportunities/serializers/pipeline_template_serializer.py

from rest_framework import serializers
from core.client_scope import ClientScopeManager
from core.exceptions import StandardizedValidationError
from core.error_messages import CoreErrorMessages, OpportunityErrorMessages
from apps.opportunities.models import PipelineTemplate, Opportunity
from apps.opportunities.config.pipeline_stages import PipelineStagesConfig


class PipelineTemplateSerializer(ClientScopeManager.SerializerMixin, serializers.ModelSerializer):
    """
    Serializer pour les templates de pipeline avec validation d'unicité
    """

    opportunity = serializers.PrimaryKeyRelatedField(
        queryset=Opportunity.objects.all(),
        required=True,
        error_messages={
            'required': CoreErrorMessages.REQUIRED_FIELD.format(field='Opportunity'),
            'does_not_exist': CoreErrorMessages.OBJECT_NOT_FOUND,
            'invalid': CoreErrorMessages.INVALID_FIELD.format(field='Opportunity ID must be a valid integer')
        }
    )

    name = serializers.CharField(
        max_length=200,
        required=False,
        allow_blank=True,
        error_messages={
            'max_length': CoreErrorMessages.INVALID_FIELD.format(field='Template Name cannot exceed 200 characters')
        }
    )
    
    description = serializers.CharField(
        required=False,
        allow_blank=True,
        error_messages={
            'max_length': CoreErrorMessages.INVALID_FIELD.format(field='Description cannot exceed 1000 characters')
        }
    )
    
    template_type = serializers.ChoiceField(
        choices=PipelineStagesConfig.TemplateType.choices,
        default=PipelineStagesConfig.TemplateType.DEFAULT,
        error_messages={
            'required': CoreErrorMessages.REQUIRED_FIELD.format(field='Template Type'),
            'invalid_choice': 'Invalid template type. Choose from: DEFAULT, CUSTOM, RENEWAL'
        }
    )


    # Champs calculés pour accès rapide aux informations contextuelles
    account_id = serializers.SerializerMethodField(read_only=True)
    products= serializers.SerializerMethodField(read_only=True)
    stages_count = serializers.IntegerField(read_only=True)

    # Champs pour les relations (read-only)
    opportunity_title = serializers.CharField(source='opportunity.title', read_only=True)
    opportunity_status = serializers.CharField(source='opportunity.status', read_only=True)
    account_name = serializers.CharField(source='opportunity.account.company_name', read_only=True)

    
    class Meta:
        model = PipelineTemplate
        fields = [
                'id',
                'opportunity',
                'opportunity_title',
                'opportunity_status',
                'name',
                'description',
                'template_type',
                'stages_count',
                'is_default',
                'account_id',
                'products',
                'account_name',
                'created_at',
                'updated_at'
            ]
        read_only_fields = [
                'id',
                'opportunity_title',
                'opportunity_status',
                'account_id',
                'product_id',
                'account_name',
                'created_at',
                'updated_at'
            ]
    
    def get_account_id(self, obj):
        """
        Retourne l'ID du compte associé à l'opportunité
        Permet d'identifier rapidement le compte lié à ce processus
        """
        if obj.opportunity and obj.opportunity.account:
            return obj.opportunity.account.id
        return None
    
    def get_products(self, obj):
        """
        Retourne la liste des produits de l'opportunité
        Format: [{"id": 1, "name": "Product Name"}, ...]
        """
        if not obj.opportunity:
            return []
        
        # Récupérer les line_items de l'opportunité
        line_items = obj.opportunity.line_items.select_related('product').all()
        
        if not line_items.exists():
            return []
        
        # Construire la liste des produits uniques
        products = []
        seen_product_ids = set()
        
        for line_item in line_items:
            if line_item.product and line_item.product.id not in seen_product_ids:
                products.append({
                    "id": line_item.product.id,
                    "name": line_item.product.product_name
                })
                seen_product_ids.add(line_item.product.id)
        
        return products
    
    def get_stages_count(self, obj):
        """
        Retourne le nombre d'étapes dans ce template
        """
        return obj.stages.count() if obj.stages else 0
    
    def generate_default_name(cls, opportunity):
        """
        Génère un nom par défaut pour le template basé sur l'opportunité
        Format: "Buying Process for {account.name}" ou "Renewal Process for {account.name}"
        """
        
        # Détermine le type de processus
        if opportunity.opportunity_type == opportunity.OpportunityType.RENEWAL:
            process_type = "Renewal Process"
        else:
            process_type = "Buying Process"
        
        return f"{process_type} for {opportunity.account.company_name}"
    
    def validate_template_type(self, value):
        """Validation du type de template"""
        if value not in [choice[0] for choice in PipelineStagesConfig.TemplateType.choices]:
            raise StandardizedValidationError({
                "template_type": CoreErrorMessages.INVALID_FIELD.format(
                    field=f"Template type"
                )
            })
        return value
    
    def validate_name(self, value):
        """Validation du nom du template avec génération automatique"""
        # Si pas de nom fourni, on générera automatiquement dans validate()
        if value and value.strip():
            return value.strip()
        return value
    
    def validate_opportunity(self, value):
        """Validation de l'opportunité selon le pattern du projet"""
        if value:
            client_id = self._get_client_id_from_context()
            if str(value.client_id) != str(client_id):
                raise StandardizedValidationError(
                    CoreErrorMessages.PERMISSION_DENIED,
                    field_name="opportunity"
                )
        return value
    
    def _unique_constraint(self, data):
        """
        Contrainte d'unicité : un seul template par opportunité
        """
        opportunity = data.get('opportunity', getattr(self.instance, 'opportunity', None))
        
        if opportunity:
            self.validate_client_scoped_uniqueness(
                data={'opportunity': opportunity.id},
                unique_fields=['opportunity'],
                model_class=PipelineTemplate,
            )

    def validate(self, data):
        """Validation générale des données"""
        data = super().validate(data)
        
        # Validation d'unicité avec la méthode standard
        self._unique_constraint(data)
        
        # Génération automatique du nom si pas fourni
        opportunity = data.get('opportunity', getattr(self.instance, 'opportunity', None))
        name = data.get('name')
        
        if not name or not name.strip():
            if opportunity:
                data['name'] = self.generate_default_name(opportunity)
            else:
                raise StandardizedValidationError(
                    CoreErrorMessages.REQUIRED_FIELD.format(field='Template Name'),
                    field_name="name"
                )
        
        return data
    
    def create(self, validated_data):
        """Création avec client_id automatique"""
        # Hériter du client_id de l'opportunité
        if 'opportunity' in validated_data and validated_data['opportunity']:
            validated_data['client_id'] = validated_data['opportunity'].client_id
        else:
            validated_data['client_id'] = self._get_client_id_from_context()
        
        return super().create(validated_data)
    
    def update(self, instance, validated_data):
        """Mise à jour avec validation de cohérence"""
        # Vérifier les permissions
        client_id = self._get_client_id_from_context()
        if str(instance.client_id) != str(client_id):
            raise StandardizedValidationError(
                CoreErrorMessages.PERMISSION_DENIED
            )
        
        return super().update(instance, validated_data)
    
  