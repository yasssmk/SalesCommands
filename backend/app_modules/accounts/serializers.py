# backend/app_modules/accounts/serializers.py
"""
Serializers for CompanyAccount (Administration module).

Follows the same patterns as TeamSerializer for consistency.
Preserves all business logic from legacy AccountSerializer.
"""

from rest_framework import serializers
from django.utils.translation import gettext_lazy as _
from core.serializers import ContactDetailsSerializer
from core.client_scope import ClientScopeManager
from core.error_messages import CoreErrorMessages, AccountErrorMessages
from core.exceptions import StandardizedValidationError, StandardizedPermissionDenied
from end_users.models import User
from app_modules.accounts.models import CompanyAccount, AccountType, AccountClassification


# ============================================================================
# HELPER SERIALIZERS
# ============================================================================


class AccountManagerSerializer(serializers.ModelSerializer):
    """Serializer for the account manager summary."""
    class Meta:
        model = User
        fields = ['id', 'email', 'first_name', 'last_name', 'role_name', 'team']
        read_only_fields = fields


# ============================================================================
# LIST SERIALIZER (Performance optimized)
# ============================================================================

class CompanyAccountListSerializer(ClientScopeManager.SerializerMixin, serializers.ModelSerializer):
    """
    Lightweight serializer for company account lists (performance optimized).
    
    Principles:
        - Minimum fields for table display
        - SerializerMethodField for relations (avoid N+1)
        - No deep nested serializers
    """
    
    # Relations as simple objects (frontend-friendly)
    account_owner = serializers.SerializerMethodField(read_only=True)
    team = serializers.SerializerMethodField(read_only=True)
    parent_company = serializers.SerializerMethodField(read_only=True)
    
    # Display fields
    type_display = serializers.SerializerMethodField(read_only=True)
    classification_display = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = CompanyAccount
        fields = [
            # Identity
            'id', 'company_name', 'industry',
            
            # Type/Classification
            'type', 'type_display',
            'classification', 'classification_display',
            
            # Location
            'city', 'country',
            
            # Relations (simple objects)
            'account_owner', 'team', 'parent_company',
            
            # Timestamps
            'created_at', 'updated_at'
        ]
        read_only_fields = fields
    
    def get_account_owner(self, obj):
        """Return account owner as minimal object."""
        if obj.account_owner:
            return {
                'id': str(obj.account_owner_id),
                'name': obj.account_owner.get_full_name(),
                'email': obj.account_owner.email,
            }
        return None
    
    def get_team(self, obj):
        """Return team derived from account_owner."""
        if obj.account_owner and obj.account_owner.team:
            return {
                'id': str(obj.account_owner.team_id),
                'name': obj.account_owner.team.name,
            }
        return None
    
    def get_parent_company(self, obj):
        """Return parent company as minimal object."""
        if obj.parent_company:
            return {
                'id': str(obj.parent_company_id),
                'company_name': obj.parent_company.company_name,
            }
        return None
    
    def get_type_display(self, obj):
        """Get display name for type."""
        return obj.get_type_display() if obj.type else None
    
    def get_classification_display(self, obj):
        """Get display name for classification."""
        return obj.get_classification_display() if obj.classification else None


# ============================================================================
# MAIN SERIALIZER (Full details)
# ============================================================================

class CompanyAccountSerializer(ContactDetailsSerializer, ClientScopeManager.SerializerMixin, serializers.ModelSerializer):
    """
    Full serializer for CompanyAccount with all business logic.
    """
    
    # Field for write operations
    company_name = serializers.CharField(
        error_messages={
            'required': CoreErrorMessages.REQUIRED_FIELD.format(field='Company Name'),
            'invalid': CoreErrorMessages.INVALID_FIELD.format(field='Company Name')
        }
    )
    
    parent_id = serializers.UUIDField(
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
        child=serializers.UUIDField(),
        required=False,
        write_only=True
    )
    
    partners = serializers.SerializerMethodField(read_only=True)

    # JSON fields that support item operations
    qualification_data = serializers.SerializerMethodField(read_only=True)
    qualification_by_department = serializers.SerializerMethodField(read_only=True)
    has_buying_decision = serializers.BooleanField(
        required=False,
        default=True
    )

    # Fields for read operations
    profile_data = serializers.SerializerMethodField(read_only=True)
    parent_company = serializers.SerializerMethodField(read_only=True)
    direct_child_companies = serializers.SerializerMethodField(read_only=True)
    account_owner = AccountManagerSerializer(read_only=True)
    team = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = CompanyAccount
        fields = [
            'id', 'company_name', 'industry', 'address', 
            'city', 'post_code', 'state', 'country', 'website', 
            'type', 'phone_number', 'email_is_valid', 'phone_is_valid',
            'company_size', 'annual_revenue', 'classification',
            'parent_company', 'parent_id', 'direct_child_companies',
            'email', 'linkedin', 'account_owner', 'account_owner_id', 
            'team', 'client_id',
            'profile_data', 'qualification_data', 'qualification_by_department',
            'has_buying_decision',
            'partners', 'partner_ids',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'created_at', 'updated_at', 'client_id',
            'profile_data', 'qualification_data', 'qualification_by_department',
            'tech_stacks_data'
        ]
    
    # ==========================================================================
    # READ HELPERS
    # ==========================================================================
    
    def get_parent_company(self, obj):
        if obj.parent_company:
            return {
                'id': str(obj.parent_company.id),
                'company_name': obj.parent_company.company_name,
                'type': obj.parent_company.type,
                'classification': obj.parent_company.classification
            }
        return None
    
    def get_direct_child_companies(self, obj):
        return [{
            'id': str(child.id),
            'company_name': child.company_name,
            'type': child.type,
            'classification': child.classification
        } for child in obj.direct_child_companies.all()]
    
    def get_team(self, obj):
        """Return team derived from account_owner."""
        if obj.account_owner and obj.account_owner.team:
            return {
                'id': str(obj.account_owner.team_id),
                'name': obj.account_owner.team.name,
            }
        return None
    
    def get_partners(self, obj):
        """Get partner accounts for this account."""
        return [{
            'id': str(partner.id),
            'company_name': partner.company_name,
            'type': partner.type
        } for partner in obj.partners.all()]
    
    def get_profile_data(self, obj):
        """Get profile data from signals."""
        return obj.get_profile_data()
    
    def get_qualification_data(self, obj):
        """Get qualification data from signals."""
        department = self.context.get('department', None)
        source_contact = self.context.get('source_contact', None)
        min_confirmations = self.context.get('min_confirmations', None)

        # return obj.get_qualification_data(
        #     department=department,
        #     source_contact=source_contact,
        #     min_confirmations=min_confirmations,
        # )

        return None 
    
    def get_qualification_by_department(self, obj):
        """Get qualification data organized by department."""
        # return obj.get_qualification_by_department()
        return None
    
    def get_tech_stacks_data(self, obj):
        """Get tech stack data for this account."""
        department = self.context.get('department', None)
        source_contact = self.context.get('source_contact', None)
        min_confirmations = self.context.get('min_confirmations', None)
        
        # return obj.get_tech_stacks_data(
        #     department=department,
        #     source_contact=source_contact,
        #     min_confirmations=min_confirmations,
        # )

        return None

    # ==========================================================================
    # VALIDATION
    # ==========================================================================

    def validate_type(self, value):
        """Validate type field."""
        if value is None or value == '':
            return value
        
        valid_types = [choice[0] for choice in AccountType.choices]
        if value not in valid_types:
            raise StandardizedValidationError(CoreErrorMessages.INVALID_FIELD.format(field="Type"))
        return value

    def validate_classification(self, value):
        """Validate classification field."""
        if value is None or value == '':
            return value
            
        valid_classifications = [choice[0] for choice in AccountClassification.choices]
        if value not in valid_classifications:
            raise StandardizedValidationError(CoreErrorMessages.INVALID_FIELD.format(field="Classification"))
        return value
    
    def validate(self, data):
        """Complete validation of CompanyAccount data."""
        try:
            if self.partial:
                fields_to_validate = set(self.initial_data.keys())
                
                for field in ['type', 'classification']:
                    if field in fields_to_validate:
                        value = data.get(field)
                        if field == 'type':
                            self.validate_type(value)
                        else:
                            self.validate_classification(value)
                
                contact_fields = {'address', 'city', 'post_code', 'state', 'country', 
                                'phone_number', 'email', 'website', 'linkedin'}
                if contact_fields.intersection(fields_to_validate):
                    data = super(ContactDetailsSerializer, self).validate(data)
                    
            else:
                data = super(ContactDetailsSerializer, self).validate(data)

                if "city" not in data:
                    raise StandardizedValidationError(CoreErrorMessages.REQUIRED_FIELD.format(field="City"))

            client_id = self._get_client_id_from_context()
            instance = getattr(self, 'instance', None)

            if 'company_name' in data:
                data['company_name'] = data['company_name'].upper()

            self.validate_client_scoped_uniqueness(
                data=data,
                unique_fields=['company_name', 'city', 'country'],
                model_class=CompanyAccount,
                error_message=CoreErrorMessages.UNIQUE_CONSTRAINT.format(
                    fields='company name, city, and country'
                )
            )

            if 'parent_company_id' in data:
                parent_id = data.get('parent_company_id')
                if parent_id is not None:
                    self._validate_parent_company(parent_id, client_id, instance)

            if {'account_owner_id'}.intersection(data.keys()):
                self._validate_account_owner(data, client_id)
            
            if 'partner_ids' in data:
                self._validate_partners(data['partner_ids'], client_id)

            return super().validate(data)

        except serializers.ValidationError as e:
            raise StandardizedValidationError(e.detail)

    def _validate_parent_company(self, parent_id, client_id, instance):
        """Validate parent company relationships."""
        try:
            parent = CompanyAccount.objects.get(id=parent_id)

            if str(parent.client_id) != str(client_id):
                raise StandardizedValidationError(AccountErrorMessages.INVALID_PARENT)

            if instance and str(parent.id) == str(instance.id):
               raise StandardizedValidationError(AccountErrorMessages.SELF_PARENT)

            current = parent
            path = {str(current.id)}
            while current.parent_company:
                current = current.parent_company
                if str(current.id) in path or (instance and str(current.id) == str(instance.id)):
                    raise StandardizedValidationError(AccountErrorMessages.CIRCULAR_HIERARCHY)
                path.add(str(current.id))
        except CompanyAccount.DoesNotExist:
            raise StandardizedValidationError(AccountErrorMessages.PARENT_NOT_FOUND)

    def _validate_account_owner(self, data, client_id):
        """Validate account owner."""
        account_owner_id = data.get('account_owner_id')

        if account_owner_id is not None:
            try:
                account_owner = User.objects.get(id=account_owner_id)
                if not account_owner.is_active:
                    raise StandardizedValidationError(AccountErrorMessages.USER_INACTIVE)
                if str(account_owner.client_account_id) != str(client_id):
                    raise StandardizedValidationError(AccountErrorMessages.INVALID_USER)
            except User.DoesNotExist:
                raise StandardizedValidationError(AccountErrorMessages.INVALID_USER)

    def _validate_partners(self, partner_ids, client_id):
        """Validate that partners exist and have the correct type."""
        if not partner_ids:
            return
        
        for partner_id in partner_ids:
            try:
                try:
                    partner = CompanyAccount.objects.get(id=partner_id)
                except CompanyAccount.DoesNotExist:
                    raise StandardizedValidationError(CoreErrorMessages.OBJECT_NOT_FOUND)
                
                if str(partner.client_id) != str(client_id):
                    raise StandardizedPermissionDenied(CoreErrorMessages.CLIENT_MISMATCH)
                
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
    
    # ==========================================================================
    # CREATE / UPDATE
    # ==========================================================================
    
    def create(self, validated_data):
        """Handle creation with partners."""
        partner_ids = validated_data.pop('partner_ids', None)
        
        instance = super().create(validated_data)
        
        if partner_ids:
            user = self.context.get('request').user if self.context.get('request') else None
            self._add_partners(instance, partner_ids, user)
            
        return instance
                          
    def update(self, instance, validated_data):
        """Override update to handle partners specifically."""
        user = self.context.get('request').user if self.context.get('request') else None
        
        partner_ids = validated_data.pop('partner_ids', None)
        
        instance = super().update(instance, validated_data)
        
        if partner_ids is not None:
            original_partners = list(instance.partners.all().values_list('id', flat=True))
            
            self._update_partners(instance, partner_ids, user)
            
            new_partners = list(instance.partners.all().values_list('id', flat=True))
            if original_partners != new_partners and hasattr(instance, 'track_field_change'):
                instance.track_field_change('partners', original_partners, new_partners, user)
        
        return instance
    
    def _add_partners(self, instance, partner_ids, user):
        """Add partners to the account."""
        for partner_id in partner_ids:
            try:
                partner = CompanyAccount.objects.get(id=partner_id)
                instance.add_partner(partner, user)
            except CompanyAccount.DoesNotExist:
                pass
    
    def _update_partners(self, instance, partner_ids, user):
        """Update partners for the account (replace existing partners)."""
        current_partners = set(instance.partners.all().values_list('id', flat=True))
        new_partners = set(partner_ids)
        
        for partner_id in current_partners - new_partners:
            try:
                partner = CompanyAccount.objects.get(id=partner_id)
                instance.remove_partner(partner, user)
            except CompanyAccount.DoesNotExist:
                pass
        
        for partner_id in new_partners - current_partners:
            try:
                partner = CompanyAccount.objects.get(id=partner_id)
                instance.add_partner(partner, user)
            except CompanyAccount.DoesNotExist:
                pass


# ============================================================================
# CREATE SERIALIZER
# ============================================================================

class CompanyAccountCreateSerializer(ClientScopeManager.SerializerMixin, ContactDetailsSerializer, serializers.ModelSerializer):
    """
    Specialized serializer for company account creation.
    
    Business Rules:
        - company_name is required
        - city is required
        - Auto-inject client_id
    """
    
    parent_id = serializers.UUIDField(
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
    
    class Meta:
        model = CompanyAccount
        fields = [
            'company_name', 'industry', 'type', 'classification',
            'company_size', 'annual_revenue', 'has_buying_decision',
            'address', 'city', 'post_code', 'state', 'country',
            'phone_number', 'email', 'website', 'linkedin',
            'parent_id', 'account_owner_id'
        ]
        extra_kwargs = {
            'company_name': {
                'required': True,
                'error_messages': {
                    'required': CoreErrorMessages.REQUIRED_FIELD.format(field='Company Name'),
                }
            },
            'city': {
                'required': True,
                'error_messages': {
                    'required': CoreErrorMessages.REQUIRED_FIELD.format(field='City'),
                }
            }
        }
    
    def validate_company_name(self, value):
        """Validate and normalize company name."""
        if not value or not value.strip():
            raise StandardizedValidationError(
                CoreErrorMessages.REQUIRED_FIELD.format(field='Company Name')
            )
        return value.strip().upper()
    
    def validate_type(self, value):
        """Validate type field."""
        if value is None or value == '':
            return value
        valid_types = [choice[0] for choice in AccountType.choices]
        if value not in valid_types:
            raise StandardizedValidationError(CoreErrorMessages.INVALID_FIELD.format(field="Type"))
        return value

    def validate_classification(self, value):
        """Validate classification field."""
        if value is None or value == '':
            return value
        valid_classifications = [choice[0] for choice in AccountClassification.choices]
        if value not in valid_classifications:
            raise StandardizedValidationError(CoreErrorMessages.INVALID_FIELD.format(field="Classification"))
        return value
    
    def validate(self, attrs):
        """Global validation for account creation."""
        try:
            client_id = self._get_client_id_from_context()
            attrs['client_id'] = client_id
            
            # Validate uniqueness
            self.validate_client_scoped_uniqueness(
                data=attrs,
                unique_fields=['company_name', 'city', 'country'],
                model_class=CompanyAccount,
                error_message=CoreErrorMessages.UNIQUE_CONSTRAINT.format(
                    fields='company name, city, and country'
                )
            )
            
            # Validate parent company if provided
            if 'parent_company_id' in attrs and attrs['parent_company_id']:
                self._validate_parent_company(attrs['parent_company_id'], client_id)
            
            # Validate owner/team
            if 'account_owner_id' in attrs:
                self._validate_account_owner(attrs, client_id)
            
            return attrs
            
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_DATA.format(detail=str(e))
            )
    
    def _validate_parent_company(self, parent_id, client_id):
        """Validate parent company exists and belongs to same client."""
        try:
            parent = CompanyAccount.objects.get(id=parent_id)
            if str(parent.client_id) != str(client_id):
                raise StandardizedValidationError(AccountErrorMessages.INVALID_PARENT)
        except CompanyAccount.DoesNotExist:
            raise StandardizedValidationError(AccountErrorMessages.PARENT_NOT_FOUND)
    
    def _validate_account_owner(self, data, client_id):
        """Validate account owner."""
        account_owner_id = data.get('account_owner_id')
        
        if account_owner_id is None:
            return

        try:
            account_owner = User.objects.get(id=account_owner_id)
            if not account_owner.is_active:
                raise StandardizedValidationError(AccountErrorMessages.USER_INACTIVE)
            if str(account_owner.client_account_id) != str(client_id):
                raise StandardizedValidationError(AccountErrorMessages.INVALID_USER)
        except User.DoesNotExist:
            raise StandardizedValidationError(AccountErrorMessages.INVALID_USER)




# ============================================================================
# UPDATE SERIALIZER
# ============================================================================

class CompanyAccountUpdateSerializer(ClientScopeManager.SerializerMixin, ContactDetailsSerializer, serializers.ModelSerializer):
    """
    Serializer for company account modifications (PATCH).
    
    Features:
        - All fields optional
        - Validation for hierarchy changes
        - Name uniqueness check (exclude current instance)
    """
    
    parent_id = serializers.UUIDField(
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
    
    
    partner_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        write_only=True
    )
    
    class Meta:
        model = CompanyAccount
        fields = [
            'company_name', 'industry', 'type', 'classification',
            'company_size', 'annual_revenue', 'has_buying_decision',
            'address', 'city', 'post_code', 'state', 'country',
            'phone_number', 'email', 'website', 'linkedin',
            'parent_id', 'account_owner_id', 'partner_ids'
        ]
        extra_kwargs = {
            'company_name': {'required': False},
            'city': {'required': False},
        }
    
    def validate_company_name(self, value):
        """Validate and normalize company name (exclude current instance)."""
        if not value or not value.strip():
            raise StandardizedValidationError(
                CoreErrorMessages.REQUIRED_FIELD.format(field='Company Name')
            )
        
        value = value.strip().upper()
        client_id = self._get_client_id_from_context()
        
        queryset = CompanyAccount.objects.filter(
            client_id=client_id,
            company_name__iexact=value
        )
        
        if self.instance:
            queryset = queryset.exclude(id=self.instance.id)
        
        if queryset.exists():
            raise StandardizedValidationError(
                CoreErrorMessages.UNIQUE_CONSTRAINT.format(
                    fields=f"company name '{value}'"
                )
            )
        
        return value
    
    def validate_type(self, value):
        """Validate type field."""
        if value is None or value == '':
            return value
        valid_types = [choice[0] for choice in AccountType.choices]
        if value not in valid_types:
            raise StandardizedValidationError(CoreErrorMessages.INVALID_FIELD.format(field="Type"))
        return value

    def validate_classification(self, value):
        """Validate classification field."""
        if value is None or value == '':
            return value
        valid_classifications = [choice[0] for choice in AccountClassification.choices]
        if value not in valid_classifications:
            raise StandardizedValidationError(CoreErrorMessages.INVALID_FIELD.format(field="Classification"))
        return value
    
    def validate(self, attrs):
        """Global validation for updates."""
        try:
            client_id = self._get_client_id_from_context()
            
            if 'parent_company_id' in attrs and attrs['parent_company_id']:
                self._validate_parent_company(attrs['parent_company_id'], client_id, self.instance)
            
            if 'account_owner_id' in attrs:
                self._validate_account_owner(attrs, client_id)
            
            if 'partner_ids' in attrs:
                self._validate_partners(attrs['partner_ids'], client_id)
            
            return attrs
            
        except StandardizedValidationError:
            raise
        except Exception as e:
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_DATA.format(detail=str(e))
            )
    
    def _validate_parent_company(self, parent_id, client_id, instance):
        """Validate parent company relationships."""
        try:
            parent = CompanyAccount.objects.get(id=parent_id)

            if str(parent.client_id) != str(client_id):
                raise StandardizedValidationError(AccountErrorMessages.INVALID_PARENT)

            if instance and str(parent.id) == str(instance.id):
               raise StandardizedValidationError(AccountErrorMessages.SELF_PARENT)

            current = parent
            path = {str(current.id)}
            while current.parent_company:
                current = current.parent_company
                if str(current.id) in path or (instance and str(current.id) == str(instance.id)):
                    raise StandardizedValidationError(AccountErrorMessages.CIRCULAR_HIERARCHY)
                path.add(str(current.id))
        except CompanyAccount.DoesNotExist:
            raise StandardizedValidationError(AccountErrorMessages.PARENT_NOT_FOUND)
    
    def _validate_account_owner(self, data, client_id):
        """Validate account owner."""
        account_owner_id = data.get('account_owner_id')
        
        if account_owner_id is None:
            return

        try:
            account_owner = User.objects.get(id=account_owner_id)
            if not account_owner.is_active:
                raise StandardizedValidationError(AccountErrorMessages.USER_INACTIVE)
            if str(account_owner.client_account_id) != str(client_id):
                raise StandardizedValidationError(AccountErrorMessages.INVALID_USER)
        except User.DoesNotExist:
            raise StandardizedValidationError(AccountErrorMessages.INVALID_USER)

    def _validate_partners(self, partner_ids, client_id):
        """Validate partners."""
        if not partner_ids:
            return
        
        for partner_id in partner_ids:
            try:
                partner = CompanyAccount.objects.get(id=partner_id)
                if str(partner.client_id) != str(client_id):
                    raise StandardizedPermissionDenied(CoreErrorMessages.CLIENT_MISMATCH)
                if partner.type != AccountType.PARTNER:
                    raise StandardizedValidationError(
                        CoreErrorMessages.INVALID_FIELD.format(field="Partner type")
                    )
            except CompanyAccount.DoesNotExist:
                raise StandardizedValidationError(CoreErrorMessages.OBJECT_NOT_FOUND)
    
    def update(self, instance, validated_data):
        """Update with partner handling."""
        user = self.context.get('request').user if self.context.get('request') else None
        partner_ids = validated_data.pop('partner_ids', None)
        
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        instance.save(user=user)
        
        if partner_ids is not None:
            self._update_partners(instance, partner_ids, user)
        
        return instance
    
    def _update_partners(self, instance, partner_ids, user):
        """Update partners for the account."""
        current_partners = set(instance.partners.all().values_list('id', flat=True))
        new_partners = set(partner_ids)
        
        for partner_id in current_partners - new_partners:
            try:
                partner = CompanyAccount.objects.get(id=partner_id)
                instance.remove_partner(partner, user)
            except CompanyAccount.DoesNotExist:
                pass
        
        for partner_id in new_partners - current_partners:
            try:
                partner = CompanyAccount.objects.get(id=partner_id)
                instance.add_partner(partner, user)
            except CompanyAccount.DoesNotExist:
                pass