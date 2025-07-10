# backend/apps/opportunities/serializers/substage_metadata_serializer.py

from rest_framework import serializers
from core.client_scope import ClientScopeManager
from core.exceptions import StandardizedValidationError
from core.error_messages import CoreErrorMessages, OpportunityErrorMessages
from apps.opportunities.models import SubStageMetadata, PipelineSubStage
from apps.accounts.models import Contact
from apps.core_apps.models import StandardDepartment


class SubStageMetadataSerializer(ClientScopeManager.SerializerMixin, serializers.ModelSerializer):
    """
    Serializer pour les métadonnées des sous-étapes avec validation des stakeholders et critères
    """
    
    # Champs calculés (read-only)
    stakeholders_count = serializers.IntegerField(read_only=True)
    validation_criteria_count = serializers.IntegerField(read_only=True)
    decision_criteria_count = serializers.IntegerField(read_only=True)
    is_complete = serializers.BooleanField(read_only=True)
    risk_level = serializers.CharField(read_only=True)
    
    # Champs pour les relations
    substage_name = serializers.CharField(source='substage.name', read_only=True)
    department_name = serializers.CharField(source='department.name', read_only=True)
    priority_display = serializers.CharField(source='get_priority_display', read_only=True)
    
    # Champs pour les stakeholders (liste des IDs et noms)
    stakeholder_ids = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=False,
        allow_empty=True
    )
    stakeholder_names = serializers.ListField(
        child=serializers.CharField(),
        read_only=True
    )
    
    class Meta:
        model = SubStageMetadata
        fields = [
            'id',
            'substage',
            'substage_name',
            'objective',
            'validation_criteria',
            'decision_criteria',
            'process_notes',
            'department',
            'department_name',
            'priority',
            'priority_display',
            'estimated_budget',
            'actual_cost',
            'risk_level_assessment',
            'stakeholders_count',
            'validation_criteria_count',
            'decision_criteria_count',
            'is_complete',
            'risk_level',
            'stakeholder_ids',
            'stakeholder_names',
            'last_reviewed_at',
            'last_reviewed_by',
            'created_at',
            'updated_at'
        ]
        read_only_fields = [
            'id',
            'substage_name',
            'department_name',
            'priority_display',
            'stakeholders_count',
            'validation_criteria_count',
            'decision_criteria_count',
            'is_complete',
            'risk_level',
            'stakeholder_names',
            'created_at',
            'updated_at'
        ]
    
    def get_stakeholders_count(self, obj):
        """Nombre de stakeholders assignés"""
        return obj.stakeholders.count()
    
    def get_validation_criteria_count(self, obj):
        """Nombre de critères de validation"""
        return len(obj.validation_criteria) if obj.validation_criteria else 0
    
    def get_decision_criteria_count(self, obj):
        """Nombre de critères de décision"""
        return len(obj.decision_criteria) if obj.decision_criteria else 0
    
    def get_is_complete(self, obj):
        """Vérifie si les métadonnées sont complètes"""
        required_fields = [obj.objective, obj.validation_criteria, obj.decision_criteria]
        return all(field for field in required_fields) and obj.stakeholders.exists()
    
    def get_risk_level(self, obj):
        """Calcule le niveau de risque basé sur les critères"""
        if obj.risk_level_assessment:
            return obj.risk_level_assessment
        
        # Calcul automatique basé sur les critères
        if obj.estimated_budget and obj.actual_cost:
            if obj.actual_cost > obj.estimated_budget * 1.5:
                return "HIGH"
            elif obj.actual_cost > obj.estimated_budget * 1.2:
                return "MEDIUM"
        
        return "LOW"
    
    def get_stakeholder_names(self, obj):
        """Liste des noms des stakeholders"""
        return [f"{contact.first_name} {contact.last_name}" for contact in obj.stakeholders.all()]
    
    def validate_substage(self, value):
        """Validation de la sous-étape"""
        if value:
            client_id = self._get_client_id_from_context()
            if str(value.client_id) != str(client_id):
                raise StandardizedValidationError(
                    CoreErrorMessages.PERMISSION_DENIED,
                    field_name="substage"
                )
            
            # Vérifier qu'il n'y a pas déjà des métadonnées pour cette sous-étape
            if not self.instance and hasattr(value, 'metadata'):
                raise StandardizedValidationError(
                    "This substage already has metadata",
                    field_name="substage"
                )
        
        return value
    
    def validate_department(self, value):
        """Validation du département"""
        if value:
            client_id = self._get_client_id_from_context()
            if str(value.client_id) != str(client_id):
                raise StandardizedValidationError(
                    OpportunityErrorMessages.METADATA_DEPARTMENT_INVALID,
                    field_name="department"
                )
        return value
    
    def validate_validation_criteria(self, value):
        """Validation des critères de validation"""
        if value is not None:
            if not isinstance(value, list):
                raise StandardizedValidationError(
                    "Validation criteria must be a list",
                    field_name="validation_criteria"
                )
            
            # Validation de chaque critère
            for i, criterion in enumerate(value):
                if not isinstance(criterion, (str, dict)):
                    raise StandardizedValidationError(
                        f"Validation criterion {i+1} must be a string or object",
                        field_name="validation_criteria"
                    )
                
                if isinstance(criterion, str) and len(criterion.strip()) == 0:
                    raise StandardizedValidationError(
                        f"Validation criterion {i+1} cannot be empty",
                        field_name="validation_criteria"
                    )
                
                if isinstance(criterion, dict):
                    required_keys = ['description']
                    for key in required_keys:
                        if key not in criterion:
                            raise StandardizedValidationError(
                                f"Validation criterion {i+1} must have '{key}' field",
                                field_name="validation_criteria"
                            )
        
        return value
    
    def validate_decision_criteria(self, value):
        """Validation des critères de décision"""
        if value is not None:
            if not isinstance(value, list):
                raise StandardizedValidationError(
                    "Decision criteria must be a list",
                    field_name="decision_criteria"
                )
            
            # Validation de chaque critère
            for i, criterion in enumerate(value):
                if not isinstance(criterion, (str, dict)):
                    raise StandardizedValidationError(
                        f"Decision criterion {i+1} must be a string or object",
                        field_name="decision_criteria"
                    )
                
                if isinstance(criterion, str) and len(criterion.strip()) == 0:
                    raise StandardizedValidationError(
                        f"Decision criterion {i+1} cannot be empty",
                        field_name="decision_criteria"
                    )
                
                if isinstance(criterion, dict):
                    required_keys = ['description', 'weight']
                    for key in required_keys:
                        if key not in criterion:
                            raise StandardizedValidationError(
                                f"Decision criterion {i+1} must have '{key}' field",
                                field_name="decision_criteria"
                            )
        
        return value
    
    def validate_estimated_budget(self, value):
        """Validation du budget estimé"""
        if value is not None and value < 0:
            raise StandardizedValidationError(
                "Estimated budget cannot be negative",
                field_name="estimated_budget"
            )
        return value
    
    def validate_actual_cost(self, value):
        """Validation du coût réel"""
        if value is not None and value < 0:
            raise StandardizedValidationError(
                "Actual cost cannot be negative",
                field_name="actual_cost"
            )
        return value
    
    def validate_stakeholder_ids(self, value):
        """Validation des IDs des stakeholders"""
        if value:
            client_id = self._get_client_id_from_context()
            
            # Vérifier que tous les contacts existent et appartiennent au client
            contacts = Contact.objects.filter(
                id__in=value,
                account__client_id=client_id
            )
            
            if len(contacts) != len(value):
                missing_ids = set(value) - set(contacts.values_list('id', flat=True))
                raise StandardizedValidationError(
                    f"Invalid contact IDs: {list(missing_ids)}",
                    field_name="stakeholder_ids"
                )
            
            # Vérifier que les contacts appartiennent au compte de l'opportunité
            if self.instance and self.instance.substage.stage.opportunity_pipeline:
                opportunity_account = self.instance.substage.stage.opportunity_pipeline.opportunity.contact.account
                invalid_contacts = contacts.exclude(account=opportunity_account)
                if invalid_contacts.exists():
                    raise StandardizedValidationError(
                        OpportunityErrorMessages.METADATA_STAKEHOLDER_INVALID,
                        field_name="stakeholder_ids"
                    )
        
        return value
    
    def validate(self, data):
        """Validation générale des données"""
        data = super().validate(data)
        
        # Validation de la cohérence budget/coût
        estimated_budget = data.get('estimated_budget', getattr(self.instance, 'estimated_budget', None))
        actual_cost = data.get('actual_cost', getattr(self.instance, 'actual_cost', None))
        
        if estimated_budget and actual_cost:
            if actual_cost > estimated_budget * 2:
                raise StandardizedValidationError(
                    OpportunityErrorMessages.METADATA_BUDGET_EXCEEDED.format(
                        actual=actual_cost,
                        estimated=estimated_budget,
                        substage_name=getattr(self.instance, 'substage', {}).get('name', 'Unknown')
                    ),
                    field_name="actual_cost"
                )
        
        # Validation de la cohérence des critères
        validation_criteria = data.get('validation_criteria', getattr(self.instance, 'validation_criteria', []))
        decision_criteria = data.get('decision_criteria', getattr(self.instance, 'decision_criteria', []))
        
        if validation_criteria and decision_criteria:
            # Vérifier qu'il n'y a pas de doublons entre les critères
            validation_descriptions = [
                c.get('description', c) if isinstance(c, dict) else c
                for c in validation_criteria
            ]
            decision_descriptions = [
                c.get('description', c) if isinstance(c, dict) else c
                for c in decision_criteria
            ]
            
            duplicates = set(validation_descriptions) & set(decision_descriptions)
            if duplicates:
                raise StandardizedValidationError(
                    f"Duplicate criteria found: {list(duplicates)}",
                    field_name="decision_criteria"
                )
        
        return data
    
    def create(self, validated_data):
        """Création de nouvelles métadonnées"""
        try:
            # Extraire les stakeholder_ids
            stakeholder_ids = validated_data.pop('stakeholder_ids', [])
            
            # Ajouter le client_id automatiquement
            validated_data['client_id'] = self._get_client_id_from_context()
            
            # Créer les métadonnées
            metadata = SubStageMetadata.objects.create(**validated_data)
            
            # Ajouter les stakeholders
            if stakeholder_ids:
                contacts = Contact.objects.filter(id__in=stakeholder_ids)
                metadata.stakeholders.set(contacts)
            
            return metadata
            
        except Exception as e:
            raise StandardizedValidationError(
                f"SubStage metadata creation failed: {str(e)}"
            )
    
    def update(self, instance, validated_data):
        """Mise à jour des métadonnées existantes"""
        try:
            # Vérifier les permissions
            client_id = self._get_client_id_from_context()
            if str(instance.client_id) != str(client_id):
                raise StandardizedValidationError(
                    CoreErrorMessages.PERMISSION_DENIED
                )
            
            # Extraire les stakeholder_ids
            stakeholder_ids = validated_data.pop('stakeholder_ids', None)
            
            # Mettre à jour l'instance
            for attr, value in validated_data.items():
                setattr(instance, attr, value)
            
            instance.save()
            
            # Mettre à jour les stakeholders si fournis
            if stakeholder_ids is not None:
                contacts = Contact.objects.filter(id__in=stakeholder_ids)
                instance.stakeholders.set(contacts)
            
            return instance
            
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                f"SubStage metadata update failed: {str(e)}"
            )
    
    def to_representation(self, instance):
        """Enrichir la représentation avec des données calculées"""
        representation = super().to_representation(instance)
        
        # Ajouter les champs calculés
        representation['stakeholders_count'] = self.get_stakeholders_count(instance)
        representation['validation_criteria_count'] = self.get_validation_criteria_count(instance)
        representation['decision_criteria_count'] = self.get_decision_criteria_count(instance)
        representation['is_complete'] = self.get_is_complete(instance)
        representation['risk_level'] = self.get_risk_level(instance)
        representation['stakeholder_names'] = self.get_stakeholder_names(instance)
        
        return representation