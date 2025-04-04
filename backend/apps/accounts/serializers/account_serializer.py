# apps/account/serializers/account_serializer.py

from rest_framework import serializers
from django.utils.translation import gettext_lazy as _
from core.serializers import ContactDetailsSerializer
from core.client_scope import ClientScopeManager
from core.error_messages import CoreErrorMessages, AccountErrorMessages
from core.exceptions import StandardizedValidationError, StandardizedPermissionDenied
from apps.core_apps.serializers import SignalAwareSerializerMixin, HistoricalTrackingSerializerMixin
from end_users.models import User, Team
from ..models import Account, AccountType, AccountClassification

class AssignedTeamSerializer(serializers.ModelSerializer):
    """Serializer for the assigned team summary"""
    class Meta:
        model = Team
        fields = ['id', 'name', 'organization']
        read_only_fields = fields

class AccountManagerSerializer(serializers.ModelSerializer):
    """Serializer for the account manager summary"""
    class Meta:
        model = User
        fields = ['id', 'email', 'first_name', 'last_name', 'role_name', 'team']
        read_only_fields = fields

class AccountSerializer(ContactDetailsSerializer,
                        HistoricalTrackingSerializerMixin, ClientScopeManager.SerializerMixin, 
                        SignalAwareSerializerMixin, serializers.ModelSerializer):
    # Field for write operations
    company_name = serializers.CharField(
        error_messages={
            'required': CoreErrorMessages.REQUIRED_FIELD.format(field='Company Name'),
            'invalid': CoreErrorMessages.INVALID_FIELD.format(field='Company Name')
        }
    )
    
    parent_id = serializers.IntegerField(
        source='parent_company_id',
        required=False,
        allow_null=True,
        write_only=True
    )

    account_owner_id = serializers.UUIDField(
        required=False,
        allow_null=True,
        write_only=True
    )

    team_owner_id = serializers.UUIDField(
        required=False,
        allow_null=True,
        write_only=True
    )

    company_size = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True
    )

    annual_revenue = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True
    )

    type = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True
    )

    classification = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True
    )

    partner_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        write_only=True
    )
    
    partners = serializers.SerializerMethodField(read_only=True)

    # JSON fields that support item operations
    objectives = serializers.JSONField(required=False, allow_null=True)
    motivations = serializers.JSONField(required=False, allow_null=True)
    metrics = serializers.JSONField(required=False, allow_null=True)
    pain_points = serializers.JSONField(required=False, allow_null=True)
    implications = serializers.JSONField(required=False, allow_null=True)
    has_buying_decision = serializers.BooleanField(
        required=False,
        default=False
    )

    # Fields for read operations
    parent_company = serializers.SerializerMethodField(read_only=True)
    direct_child_companies = serializers.SerializerMethodField(read_only=True)
    account_owner = AccountManagerSerializer(read_only=True)
    team_owner = AssignedTeamSerializer(read_only=True)
    
    class Meta:
        model = Account
        fields = [
            'id', 'company_name', 'industry', 'address', 
            'city', 'post_code', 'state', 'country', 'website', 
            'type', 'phone_number',
            'company_size', 'annual_revenue', 'classification',
            'parent_company', 'parent_id', 'direct_child_companies',
            'email', 'linkedin', 'account_owner', 'account_owner_id', 
            'team_owner', 'team_owner_id', 'client_id', 'historical_data',
            'objectives', 'motivations', 'metrics',
            'pain_points', 'implications', 'has_buying_decision',
            'partners', 'partner_ids',
            'signal_metadata', 'qualification_with_signals', 'profile_with_signals'
        ]
        read_only_fields = [
            'created_at', 'updated_at', 'client_id', 'historical_data', 
            'signal_metadata', 'qualification_with_signals', 'profile_with_signals'
        ]
    
    def get_parent_company(self, obj):
        if obj.parent_company:
            return {
                'id': obj.parent_company.id,
                'company_name': obj.parent_company.company_name,
                'type': obj.parent_company.type,
                'classification': obj.parent_company.classification
            }
        return None
    
    def get_direct_child_companies(self, obj):
        return [{
            'id': child.id,
            'company_name': child.company_name,
            'type': child.type,
            'classification': child.classification
        } for child in obj.direct_child_companies.all()]
    
    def get_partners(self, obj):
        """Get partner accounts for this account."""
        return [{
            'id': partner.id,
            'company_name': partner.company_name,
            'type': partner.type
        } for partner in obj.partners.all()]
    
    def validate_type(self, value):
        """Validate type field"""
        if value is None or value == '':
            return value
        
        valid_types = [choice[0] for choice in AccountType.choices]
        if value not in valid_types:
            raise StandardizedValidationError(CoreErrorMessages.INVALID_FIELD.format(field="Type"))
        return value


    def validate_classification(self, value):
        """Validate classification field"""
        if value is None or value == '':
            return value
            
        valid_classifications = [choice[0] for choice in AccountClassification.choices]
        if value not in valid_classifications:
            raise StandardizedValidationError(CoreErrorMessages.INVALID_FIELD.format(field="Classification"))
        return value
    
    def _process_json_item_operation(self, instance, field_name, data, user):
        """Process JSON item operations - optimized version."""
        if not isinstance(data, dict):
            return False
            
        operation = data.get('operation')
        if not operation:
            return False
            
        try:
            # Dispatch based on operation type
            if operation == 'add':
                item = data.get('item')
                if not item:
                    return False
                    
                # Try qualification method first, then tracked method
                for method_name in ['add_qualification_item', 'add_tracked_json_item']:
                    if hasattr(instance, method_name):
                        method = getattr(instance, method_name)
                        return method(field_name, item, user)
                        
            elif operation == 'update':
                item_id = data.get('item_id')
                item = data.get('item')
                id_key = data.get('id_key', 'id')
                
                if not (item_id and item):
                    return False
                    
                # Try both methods
                if hasattr(instance, 'update_qualification_item'):
                    return instance.update_qualification_item(field_name, item_id, item, user, None, id_key)
                elif hasattr(instance, 'update_tracked_json_item'):
                    return instance.update_tracked_json_item(field_name, item_id, item, id_key, user)
                    
            elif operation == 'remove':
                item_id = data.get('item_id')
                id_key = data.get('id_key', 'id')
                
                if not item_id:
                    return False
                    
                # Try both methods
                if hasattr(instance, 'remove_qualification_item'):
                    return instance.remove_qualification_item(field_name, item_id, user, None)
                elif hasattr(instance, 'remove_tracked_json_item'):
                    return instance.remove_tracked_json_item(field_name, item_id, id_key, user)
            
            # Unknown operation
            return False
            
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_OPERATION.format(
                    operation=f"Failed to perform {operation} operation on {field_name}"
                )
            )

    def validate(self, data):
        """Complete validation of Account data."""
        try:
            if self.partial:
                # For PATCH requests, only validate fields that were sent
                fields_to_validate = set(self.initial_data.keys())
                
                # Only validate choice fields if they're being updated
                for field in ['type', 'classification']:
                    if field in fields_to_validate:
                        value = data.get(field)
                        if field == 'type':
                            self.validate_type(value)
                        else:
                            self.validate_classification(value)
                
                # For contact fields, only validate if they're being updated
                contact_fields = {'address', 'city', 'post_code', 'state', 'country', 
                                'phone_number', 'email', 'website', 'linkedin'}
                if contact_fields.intersection(fields_to_validate):
                    # Call parent class's validate_contact_details method
                    data = super(ContactDetailsSerializer, self).validate(data)
                    
            else:
                # For full updates (PUT/POST), validate everything
                data = super(ContactDetailsSerializer, self).validate(data)

                if "city" not in data:
                    raise StandardizedValidationError(CoreErrorMessages.REQUIRED_FIELD.format(field="City"))

            # Get client_id for validations
            client_id = self._get_client_id_from_context()
            instance = getattr(self, 'instance', None)

            if 'company_name' in data:
                data['company_name'] = data['company_name'].upper()

            self.validate_client_scoped_uniqueness(
                data=data,
                unique_fields=['company_name', 'city', 'country'],
                model_class=Account,
                error_message=CoreErrorMessages.UNIQUE_CONSTRAINT.format(
                    fields='company name, city, and country'
                )
            )

            # Parent company validation if needed
            if 'parent_company_id' in data:
                parent_id = data.get('parent_company_id')
                if parent_id is not None:
                    self._validate_parent_company(parent_id, client_id, instance)

            # Team and account owner validation if needed
            if {'account_owner_id', 'team_owner_id'}.intersection(data.keys()):
                self._validate_account_owner_and_team(data, client_id)
            
            if 'partner_ids' in data:
                self._validate_partners(data['partner_ids'], self._get_client_id_from_context())
            

            return super().validate(data)

        except serializers.ValidationError as e:
            raise StandardizedValidationError(e.detail)

    def _validate_parent_company(self, parent_id, client_id, instance):
        """Validate parent company relationships."""
        try:
            parent = Account.objects.get(id=parent_id)

            if str(parent.client_id) != str(client_id):
                raise StandardizedValidationError(AccountErrorMessages.INVALID_PARENT)

            # Check for self-reference and circular references
            if instance and str(parent.id) == str(instance.id):
               raise StandardizedValidationError(AccountErrorMessages.SELF_PARENT)

            current = parent
            path = {str(current.id)}
            while current.parent_company:
                current = current.parent_company
                if str(current.id) in path or (instance and str(current.id) == str(instance.id)):
                    raise StandardizedValidationError(AccountErrorMessages.CIRCULAR_HIERARCHY)
                path.add(str(current.id))
        except Account.DoesNotExist:
            raise StandardizedValidationError(AccountErrorMessages.PARENT_NOT_FOUND)

    def _validate_account_owner_and_team(self, data, client_id):
        """Validate account owner and team owner relationships."""
        account_owner_id = data.get('account_owner_id')
        team_owner_id = data.get('team_owner_id')

        if account_owner_id is not None:
            try:
                account_owner = User.objects.get(id=account_owner_id)
                if not account_owner.is_active:
                    raise StandardizedValidationError(AccountErrorMessages.USER_INACTIVE)

                if team_owner_id:
                    team = Team.objects.get(id=team_owner_id)
                    if account_owner.team_id != team.id:
                        raise StandardizedValidationError(AccountErrorMessages.TEAM_MISMATCH)
            except User.DoesNotExist:
                raise StandardizedValidationError(AccountErrorMessages.INVALID_USER)

        if team_owner_id is not None:
            try:
                team = Team.objects.get(id=team_owner_id)
                if str(team.organization.client_account_id) != str(client_id):
                    raise StandardizedValidationError(AccountErrorMessages.TEAM_MISMATCH)
            except Team.DoesNotExist:
                raise StandardizedValidationError(CoreErrorMessages.OBJECT_NOT_FOUND)

    def _validate_partners(self, partner_ids, client_id):
        """
        Validate that partners exist and have the correct type.
        Uses standardized error handling and client scoping patterns.
        """
        if not partner_ids:
            return
        
        # For each partner ID, validate separately to provide clear error messages
        for partner_id in partner_ids:
            try:
                # Get the partner and validate existence
                try:
                    partner = Account.objects.get(id=partner_id)
                except Account.DoesNotExist:
                    raise StandardizedValidationError(CoreErrorMessages.OBJECT_NOT_FOUND)
                
                # Validate client scope
                if str(partner.client_id) != str(client_id):
                    raise StandardizedPermissionDenied(CoreErrorMessages.CLIENT_MISMATCH)
                
                # Validate partner type
                if partner.type != AccountType.PARTNER:
                    raise StandardizedValidationError(
                        CoreErrorMessages.INVALID_FIELD.format(field="Partner type")
                    )
                    
            except StandardizedValidationError:
                raise
            except StandardizedPermissionDenied:
                raise
            except Exception as e:
                raise StandardizedValidationError(CoreErrorMessages.UNEXPECTED_ERROR.format(detail=e))
    
    def create(self, validated_data):
        """Handle creation with partners."""
        partner_ids = validated_data.pop('partner_ids', None)
        
        # Create the account
        instance = super().create(validated_data)
        
        # Add partners if provided
        if partner_ids:
            user = self.context.get('request').user if self.context.get('request') else None
            self._add_partners(instance, partner_ids, user)
            
        return instance
                          
    def update(self, instance, validated_data):
        """
        Override update to handle JSON item operations and partners.
        """
        # Get user from request context
        user = self.context.get('request').user if self.context.get('request') else None
        
        # Store original values for tracking changes
        original_values = {}
        for field_name in validated_data.keys():
            if hasattr(instance, field_name):
                original_values[field_name] = getattr(instance, field_name)
        
        # Handle partners separately
        partner_ids = validated_data.pop('partner_ids', None)
        
        # Check for JSON item operations in request data
        json_fields = {'objectives', 'motivations', 'metrics', 'pain_points', 'implications'}
        
        for field_name in json_fields:
            # Get the field data from the original request
            if field_name in self.initial_data:
                field_data = self.initial_data[field_name]
                
                # Try to process as an item operation
                if isinstance(field_data, dict) and 'operation' in field_data:
                    # Process operation and remove from validated_data if successful
                    if self._process_json_item_operation(instance, field_name, field_data, user):
                        if field_name in validated_data:
                            validated_data.pop(field_name)
        
        # Call parent update method to handle regular field updates
        instance = super().update(instance, validated_data)
        
        # Explicitly track any fields that might have been missed
        for field_name, old_value in original_values.items():
            new_value = getattr(instance, field_name)
            
            # Only track if value changed
            if old_value != new_value and hasattr(instance, 'track_field_change'):
                instance.track_field_change(field_name, old_value, new_value, user)
        
        # Update partners if provided
        if partner_ids is not None:
            # Store original partners for tracking
            original_partners = list(instance.partners.all().values_list('id', flat=True))
            
            # Update partners
            self._update_partners(instance, partner_ids, user)
            
            # Track partner changes
            new_partners = list(instance.partners.all().values_list('id', flat=True))
            if original_partners != new_partners and hasattr(instance, 'track_field_change'):
                instance.track_field_change('partners', original_partners, new_partners, user)
        
        return instance
    
    def _add_partners(self, instance, partner_ids, user):
        """Add partners to the account."""
        for partner_id in partner_ids:
            try:
                partner = Account.objects.get(id=partner_id)
                instance.add_partner(partner, user)
            except Account.DoesNotExist:
                pass  # Already validated in _validate_partners
    
    def _update_partners(self, instance, partner_ids, user):
        """Update partners for the account (replace existing partners)."""
        # Get existing partners
        current_partners = set(instance.partners.all().values_list('id', flat=True))
        new_partners = set(partner_ids)
        
        # Remove partners that are no longer in the list
        for partner_id in current_partners - new_partners:
            try:
                partner = Account.objects.get(id=partner_id)
                instance.remove_partner(partner, user)
            except Account.DoesNotExist:
                pass
        
        # Add new partners
        for partner_id in new_partners - current_partners:
            try:
                partner = Account.objects.get(id=partner_id)
                instance.add_partner(partner, user)
            except Account.DoesNotExist:
                pass