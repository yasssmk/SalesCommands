# apps/campaign/serializers/campaign_serializer.py

from rest_framework import serializers
from apps.campaign.models.campaign import Campaign
from apps.campaign.models.campaign_stakeholder import CampaignStakeholder
from apps.campaign.serializers.campaign_stakeholders_serializer import CampaignStakeholderSerializer
from apps.campaign.serializers.campaign_objective_serializer import CampaignObjectiveSerializer
from apps.campaign.models.campaign_result_tracking import CampaignResultTracking
from core.client_scope import ClientScopeManager
from core.exceptions import StandardizedValidationError
from core.error_messages import CoreErrorMessages
from end_users.models import User
from django.db import transaction

# ✅ Import des constantes
from apps.campaign.config.settings import CONFIG

class CampaignSerializer(ClientScopeManager.SerializerMixin, serializers.ModelSerializer):
    """Serializer for Campaign model with standardized validation"""
    
    # Read-only fields
    owner_name = serializers.SerializerMethodField(read_only=True)
    campaign_type_display = serializers.CharField(source='get_campaign_type_display', read_only=True)
    sequence_type_display = serializers.SerializerMethodField(read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    stakeholders = CampaignStakeholderSerializer(source='stakeholder_links', many=True, read_only=True)
    
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
        max_length=CONFIG.limits.max_campaign_name_length,
        error_messages={
            'required': CoreErrorMessages.REQUIRED_FIELD.format(field='Campaign Name'),
            'blank': CoreErrorMessages.REQUIRED_FIELD.format(field='Campaign Name'),
            'max_length': CoreErrorMessages.INVALID_FIELD.format(
                field=f'Campaign Name (maximum {CONFIG.limits.max_campaign_name_length} characters)'
            )
        }
    )
    
    # Description with validation
    description = serializers.CharField(
        max_length=CONFIG.limits.max_description_length,
        required=False,
        allow_blank=True,
        error_messages={
            'max_length': CoreErrorMessages.INVALID_FIELD.format(
                field=f'Description (maximum {CONFIG.limits.max_description_length,} characters)'
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

    objective = serializers.DictField(
        write_only=True, 
        required=False,
        help_text="Objective data for campaign creation"
    )
    objectives = CampaignObjectiveSerializer(many=True, read_only=True)
    
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
    
    
    class Meta:
        model = Campaign
        fields = CONFIG.serializers.campaign_fields
        read_only_fields = CONFIG.serializers.campaign_read_only_fields
    
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
    
    def get_result_tracking(self, obj: Campaign) -> dict:
        """
        Obtenir le result tracking pour cette campagne - MÉTHODE MANQUANTE
        """
        try:
            # Utiliser la méthode du modèle Campaign
            result_tracking = obj.get_or_create_result_tracking()
            
            # Sérialiser avec le CampaignResultTrackingSerializer
            from apps.campaign.serializers.campaign_result_tracking_serializer import CampaignResultTrackingSerializer
            
            # Créer le contexte pour le serializer
            context = self.context or {}
            tracking_context = {
                'request': context.get('request'),
                'detailed_result_tracking': context.get('detailed_result_tracking', False),
                'include_tracked_ids': context.get('include_tracked_ids', False),
                'include_full_integrity_check': context.get('include_full_integrity_check', False)
            }
            
            # Sérialiser et retourner les données
            serializer = CampaignResultTrackingSerializer(result_tracking, context=tracking_context)
            return serializer.data
            
        except Exception as e:
            # En cas d'erreur, retourner un objet minimal plutôt que de faire planter
            print(f"DEBUG get_result_tracking: Error getting result tracking for campaign {getattr(obj, 'id', 'unknown')}: {e}")
            return {
                'id': None,
                'campaign': getattr(obj, 'id', None),
                'leads_created_count': 0,
                'meetings_secured_count': 0,
                'opportunities_created_count': 0,
                'deals_closed_count': 0,
                'pipeline_value_created': '0.00',
                'revenue_generated': '0.00',
                'error': f'Failed to load result tracking: {str(e)}'
            }
    
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
    
    def validate_objective(self, value):
        """
        ✅ FIXED: Manual validation for objective data to avoid campaign_id requirement
        """
        if not value:
            return value
            
        try:
            # Validate required fields manually
            required_fields = ['name', 'objective_type', 'target_value']
            for field in required_fields:
                if not value.get(field):
                    raise StandardizedValidationError(
                        CoreErrorMessages.REQUIRED_FIELD.format(field=f"Objective {field}")
                    )
            
            # Validate target_value
            target_value = value.get('target_value')
            try:
                target_value = float(target_value)
                if target_value <= 0:
                    raise StandardizedValidationError(
                        CoreErrorMessages.INVALID_FIELD.format(
                            field="Objective target value (must be greater than 0)"
                        )
                    )
            except (ValueError, TypeError):
                raise StandardizedValidationError(
                    CoreErrorMessages.INVALID_FIELD.format(
                        field="Objective target value (must be a number)"
                    )
                )
            
            # Validate objective_type exists
            objective_type = value.get('objective_type')
            from apps.campaign.models.campaign_objective import CampaignObjective
            valid_types = [choice[0] for choice in CampaignObjective.ObjectiveType.choices]
            if objective_type not in valid_types:
                raise StandardizedValidationError(
                    CoreErrorMessages.INVALID_FIELD.format(
                        field=f"Objective type (must be one of: {', '.join(valid_types)})"
                    )
                )
            
            # Validate objective name
            name = value.get('name', '').strip()
            if len(name) > CONFIG.limits.max_campaign_name_length:
                raise StandardizedValidationError(
                    CoreErrorMessages.INVALID_FIELD.format(
                        field=f"Objective name (maximum {CONFIG.limits.max_campaign_name_length} characters)"
                    )
                )
            
            # Clean the data
            value['target_value'] = target_value
            value['name'] = name
            
            return value
            
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_FIELD.format(field="Objective data")
            )

    def validate_campaign_type(self, value):
        """Validate campaign type"""
        try:
            # Ensure campaign type is valid
            valid_types = [choice[0] for choice in Campaign.CampaignType.choices]
            if value not in valid_types:
                raise StandardizedValidationError(
                    CoreErrorMessages.INVALID_FIELD.format(
                        field=f"Campaign type (must be one of: {', '.join(valid_types)})"
                    )
                )
            
            return value
            
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_FIELD.format(field="Campaign type")
            )

    def validate_sequence_type(self, value):
        """Validate sequence type"""
        if value is None:
            return value
            
        try:
            # Import sequence types
            from apps.sequence.sequences.sequence_dispatcher import SequenceDispatcher
            
            valid_sequences = [choice[0] for choice in SequenceDispatcher.SEQUENCE_CHOICES]
            if value not in valid_sequences:
                raise StandardizedValidationError(
                    CoreErrorMessages.INVALID_FIELD.format(
                        field=f"Sequence type (must be one of: {', '.join(valid_sequences)})"
                    )
                )
            
            return value
            
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_FIELD.format(field="Sequence type")
            )

    def validate_owner_ids(self, value):
        """Validate owner IDs list"""
        return self._validate_stakeholder_list(value, "Owner IDs")

    def validate_executor_ids(self, value):
        """Validate executor IDs list"""
        return self._validate_stakeholder_list(value, "Executor IDs")

    def validate_receiver_ids(self, value):
        """Validate receiver IDs list"""
        return self._validate_stakeholder_list(value, "Receiver IDs")

    def _validate_stakeholder_list(self, value, field_name):
        """Helper to validate stakeholder lists"""
        if not value:
            return value
            
        try:
            # Check for duplicates
            user_ids = [user.id if hasattr(user, 'id') else user for user in value]
            if len(user_ids) != len(set(user_ids)):
                raise StandardizedValidationError(
                    CoreErrorMessages.INVALID_FIELD.format(
                        field=f"{field_name} (cannot contain duplicate users)"
                    )
                )
            
            # Validate maximum stakeholders per role
            max_stakeholders = 10  # Business rule
            if len(value) > max_stakeholders:
                raise StandardizedValidationError(
                    CoreErrorMessages.INVALID_FIELD.format(
                        field=f"{field_name} (maximum {max_stakeholders} users per role)"
                    )
                )
            
            return value
            
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_FIELD.format(field=field_name)
            )
    
    def validate(self, data):
        """Validate campaign data with standardized error handling - ENHANCED VERSION"""
        try:

            if 'client_id' not in data:
                client_id = self._get_client_id_from_context()
                data['client_id'] = client_id

            self.validate_client_scoped_uniqueness(
                data=data,
                unique_fields=['name', 'client_id'],
                model_class=Campaign,
                error_message=CoreErrorMessages.UNIQUE_CONSTRAINT.format(
                    fields='Name and Client ID'
                )
            )

            # === VALIDATION DES DATES (existante + améliorée) ===
            start_date = data.get('start_date', self.instance.start_date if self.instance else None)
            end_date = data.get('end_date', self.instance.end_date if self.instance else None)
            
            if start_date and end_date:
                if end_date < start_date:
                    raise StandardizedValidationError(
                        CoreErrorMessages.INVALID_FIELD.format(
                            field=f"Date range (end date {end_date} must be after start date {start_date})"
                        )
                    )
                
                # NOUVEAU : Validation durée maximale
                duration_days = (end_date - start_date).days
                max_duration = 365  # Business rule: max 1 year
                if duration_days > max_duration:
                    raise StandardizedValidationError(
                        CoreErrorMessages.INVALID_FIELD.format(
                            field=f"Campaign duration (maximum {max_duration} days, got {duration_days} days)"
                        )
                    )
            
            # === VALIDATION CAMPAIGN TYPE vs SEQUENCE TYPE (existante) ===
            campaign_type = data.get('campaign_type', self.instance.campaign_type if self.instance else None)
            sequence_type = data.get('sequence_type', self.instance.sequence_type if self.instance else None)
            
            if campaign_type == Campaign.CampaignType.CALL_LIST and sequence_type is not None:
                raise StandardizedValidationError(
                    CoreErrorMessages.INVALID_FIELD.format(
                        field="Sequence Type (Call List campaigns cannot have automated sequences)"
                    )
                )
            
            # === NOUVELLE : VALIDATION OBJECTIVE vs CAMPAIGN TYPE ===
            objective_data = data.get('objective')
            if objective_data and campaign_type:
                self._validate_objective_consistency(objective_data, campaign_type)
            
            # === NOUVELLE : VALIDATION STAKEHOLDERS CROISÉE ===
            self._validate_stakeholder_consistency(data)
            
            # === VALIDATION EXISTANTE : Stakeholder duplicates ===
            stakeholder_fields = ['owner_ids', 'executor_ids', 'receiver_ids']
            for field_name in stakeholder_fields:
                stakeholder_list = data.get(field_name, [])
                if stakeholder_list and len(stakeholder_list) != len(set(user.id for user in stakeholder_list)):
                    raise StandardizedValidationError(
                        CoreErrorMessages.INVALID_FIELD.format(
                            field=f"{field_name.replace('_', ' ').title()} (cannot contain duplicate users)"
                        )
                    )
            
            # === NOUVELLE : VALIDATION STATE TRANSITIONS ===
            if self.instance:  # Update case
                self._validate_state_transitions(data)
            
            # === VALIDATION EXISTANTE : Description length ===
            description = data.get('description', '')
            if description and len(description) > CONFIG.limits.max_description_length:
                raise StandardizedValidationError(
                    CoreErrorMessages.INVALID_FIELD.format(
                        field=f"Description (maximum {CONFIG.limits.max_description_length} characters)"
                    )
                )
            
            return data
            
        except StandardizedValidationError:
            raise
        except serializers.ValidationError as e:
            # Convert DRF validation errors to standardized format
            if isinstance(e.detail, dict):
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
            raise StandardizedValidationError(
                CoreErrorMessages.UNEXPECTED_ERROR.format(detail="Campaign validation failed")
            )

    def _validate_objective_consistency(self, objective_data, campaign_type):
        """Validate objective is consistent with campaign type"""
        try:
            objective_type = objective_data.get('objective_type')
            
            # Business rules for objective vs campaign type
            if campaign_type == Campaign.CampaignType.CALL_LIST:
                # Call lists typically focus on meetings
                if objective_type in ['OPPORTUNITIES', 'CLOSED_DEALS', 'REVENUE']:
                    raise StandardizedValidationError(
                        CoreErrorMessages.INVALID_FIELD.format(
                            field=f"Objective type '{objective_type}' not recommended for Call List campaigns"
                        )
                    )
            
            # Validate target value makes sense for objective type
            target_value = objective_data.get('target_value', 0)
            if objective_type in ['REVENUE', 'PIPELINE_VALUE'] and target_value < 1000:
                raise StandardizedValidationError(
                    CoreErrorMessages.INVALID_FIELD.format(
                        field="Revenue/Pipeline objectives should have target value ≥ 1000"
                    )
                )
            
        except StandardizedValidationError:
            raise
        except Exception:
            # Don't fail validation for consistency checks
            pass

    def _validate_stakeholder_consistency(self, data):
        """Validate stakeholder assignments are consistent"""
        try:
            owner_ids = data.get('owner_ids', [])
            executor_ids = data.get('executor_ids', [])
            receiver_ids = data.get('receiver_ids', [])
            
            # Convert to user IDs for comparison
            owner_user_ids = {user.id if hasattr(user, 'id') else user for user in owner_ids}
            executor_user_ids = {user.id if hasattr(user, 'id') else user for user in executor_ids}
            receiver_user_ids = {user.id if hasattr(user, 'id') else user for user in receiver_ids}
            
            # Business rule: Users can have multiple roles
            # But warn if someone is both executor and receiver (might be confusing)
            overlap_exec_recv = executor_user_ids & receiver_user_ids
            if overlap_exec_recv:
                # This is a warning, not an error - just log it
                pass
            
            # Validate total unique stakeholders doesn't exceed limit
            all_stakeholder_ids = owner_user_ids | executor_user_ids | receiver_user_ids
            max_total_stakeholders = 20  # Business rule
            if len(all_stakeholder_ids) > max_total_stakeholders:
                raise StandardizedValidationError(
                    CoreErrorMessages.INVALID_FIELD.format(
                        field=f"Total stakeholders (maximum {max_total_stakeholders} unique users)"
                    )
                )
            
        except StandardizedValidationError:
            raise
        except Exception:
            # Don't fail validation for consistency checks
            pass

    def _validate_state_transitions(self, data):
        """Validate state transitions are allowed"""
        try:
            if not self.instance:
                return
                
            current_status = self.instance.status
            new_status = data.get('status', current_status)
            
            # Don't allow modifications to completed/cancelled campaigns
            if current_status in CONFIG.validation.forbidden_states:
                forbidden_fields = {'name', 'description', 'start_date', 'end_date', 'campaign_type', 'sequence_type'}
                modified_fields = forbidden_fields & set(data.keys())
                
                if modified_fields:
                    raise StandardizedValidationError(
                        CoreErrorMessages.INVALID_FIELD.format(
                            field=f"Campaign modification (cannot modify {', '.join(modified_fields)} when status is {current_status})"
                        )
                    )
            
            # Validate status transitions
            valid_transitions = {
                'DRAFT': ['ACTIVE', 'CANCELLED'],
                'ACTIVE': ['PAUSED', 'COMPLETED', 'CANCELLED'],
                'PAUSED': ['ACTIVE', 'CANCELLED'],
                'COMPLETED': [],  # Final state
                'CANCELLED': []   # Final state
            }
            
            if new_status != current_status:
                allowed_states = valid_transitions.get(current_status, [])
                if new_status not in allowed_states:
                    raise StandardizedValidationError(
                        CoreErrorMessages.INVALID_FIELD.format(
                            field=f"Status transition (cannot change from {current_status} to {new_status})"
                        )
                    )
            
        except StandardizedValidationError:
            raise
        except Exception:
            # If unexpected error occurs, we should still allow the campaign to be created/updated
            pass  # In production, this should be logged but not fail validation

    
    def create(self, validated_data):
        """
        Create campaign with optional objective
        Delegue to service for business logic - serializer only handles validation
        """
        try:
            # Extract objective data if provided
            objective_data = validated_data.pop('objective', None)
            
            # Delegate to service for business logic
            from apps.campaign.services.campaign_creation_service import CampaignCreationService

            campaign = CampaignCreationService.create_campaign_with_objective(
                campaign_data=validated_data,
                objective_data=objective_data
            )
            
            return campaign
            
        except StandardizedValidationError:
            # Re-raise service validation errors
            raise
        except Exception as e:
            # Convert unexpected errors to validation errors
            raise serializers.ValidationError(
                f"Campaign creation failed: {str(e)}"
            )
    
    def update(self, instance, validated_data):
        """
        Update campaign - keep objective handling separate for simplicity
        """
        try:
            # Extract objective data if provided
            objective_data = validated_data.pop('objective', None)
            
            # Update campaign fields
            for attr, value in validated_data.items():
                setattr(instance, attr, value)
            instance.save()
            
            # Handle objective update if provided
            if objective_data:
                self._update_or_create_objective(instance, objective_data)
            
            return instance
            
        except Exception as e:
            raise serializers.ValidationError(
                f"Campaign update failed: {str(e)}"
            )
    
    def _update_or_create_objective(self, campaign, objective_data):
        """Helper to update or create objective"""
        try:
            from apps.campaign.models.campaign_objective import CampaignObjective
            
            # Try to get existing primary objective
            existing_objective = campaign.objectives.filter(is_primary=True).first()
            
            if existing_objective:
                # Update existing
                for attr, value in objective_data.items():
                    setattr(existing_objective, attr, value)
                existing_objective.save()
            else:
                # Create new primary objective
                objective_data['campaign'] = campaign
                objective_data['is_primary'] = True
                objective_data['client_id'] = campaign.client_id
                CampaignObjective.objects.create(**objective_data)
                
        except Exception as e:
            raise serializers.ValidationError(
                f"Objective update failed: {str(e)}"
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


class CampaignListSerializer(CampaignSerializer):
    """
    ✅ VERSION SIMPLIFIÉE: Pas de logique to_representation complexe
    """
    
    class Meta(CampaignSerializer.Meta):
        # Champs essentiels pour la liste SANS target_summary
        fields = [
            'id', 'name', 'campaign_type', 'campaign_type_display', 'has_sequence',
            'owner', 'owner_name', 'owner_count', 'executor_count', 'receiver_count',
            'start_date', 'end_date', 'status', 'status_display', 'quick_metrics', 'created_at'
        ]
        read_only_fields = [
            'owner_name', 'campaign_type_display', 'status_display', 'has_sequence', 
            'quick_metrics', 'owner_count', 'executor_count', 'receiver_count', 'created_at'
        ]



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