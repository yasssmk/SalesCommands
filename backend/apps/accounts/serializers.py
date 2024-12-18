# from rest_framework import serializers
# from .models import Account
# from phonenumber_field.modelfields import PhoneNumberField
# from django.core.exceptions import ValidationError
# from django.utils.translation import gettext_lazy as _

# # Serializer for Account model
# class AccountSerializer(serializers.ModelSerializer):
#     # Fields to expose in the API
#     company_name = serializers.CharField(max_length=255)
#     industry = serializers.CharField(max_length=100, allow_blank=True, required=False)
#     address = serializers.CharField(allow_blank=True, required=False)
#     city = serializers.CharField(max_length=50)
#     post_code = serializers.CharField(max_length=20, allow_blank=True, required=False)
#     country = serializers.CharField(max_length=50)
#     website = serializers.CharField(max_length=255, allow_blank=True, required=False)
#     type = serializers.CharField(max_length=50, allow_blank=True, required=False)
#     phone_number = serializers.CharField(max_length=20, allow_blank=True, required=False)
#     number_of_employees = serializers.IntegerField(required=False)
#     potential = serializers.DecimalField(max_digits=15, decimal_places=2, required=False)
#     classification = serializers.CharField(max_length=50, allow_blank=True, required=False)
#     is_parent_company = serializers.BooleanField(default=False)
#     is_child_company = serializers.BooleanField(default=False)
#     parent_company = serializers.PrimaryKeyRelatedField(queryset=Account.objects.all(), required=False)

#     class Meta:
#         model = Account
#         fields = '__all__'
#         # Optionally you can exclude fields if you don't want to expose certain fields in the API
#         # exclude = ['account_owner', 'created_at', 'updated_at']
    

#     # Validation for phone_number
#     def validate_phone_number(self, value):
#         if value:
#             try:
#                 from phonenumbers import parse, is_valid_number
#                 phone = parse(value)
#                 if not is_valid_number(phone):
#                     raise ValidationError(_('Invalid phone number.'))
#             except Exception:
#                 raise ValidationError(_('Invalid phone number format.'))
#         return value

#     # Validation for website URL (basic check for valid URL format)
#     def validate_website(self, value):
#         if value and not value.startswith(('http://', 'https://')):
#             raise ValidationError(_('Website URL should start with "http://" or "https://".'))
#         return value

#     # Custom validation to ensure that both `is_parent_company` and `is_child_company` are not True at the same time
#     # def validate(self, data):
#     #     if data.get('is_parent_company') and data.get('is_child_company'):
#     #         raise ValidationError(_('A company cannot be both a parent and a child company.'))
#     #     return data

    
#     def validate_parent_company(self, value):
#         """Ensure no circular relationships."""
#         if self.instance and self.instance.id == value.id:
#             raise serializers.ValidationError("A company cannot be its own parent.")
#         if self.instance and value in self.instance.direct_child_companies.all():
#             raise serializers.ValidationError("A parent company cannot be a child of its own descendants.")
#         return value

from rest_framework import serializers
from .models import Account
from phonenumbers import parse, is_valid_number
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

class AccountSerializer(serializers.ModelSerializer):
    # Nested representation of parent company
    parent_company = serializers.SerializerMethodField()
    children = serializers.SerializerMethodField()

    class Meta:
        model = Account
        fields = [
            'id', 'company_name', 'industry', 'address', 
            'city', 'post_code', 'country', 'website', 
            'type', 'phone_number', 'created_at', 'updated_at',
            'number_of_employees', 'potential', 'classification',
            'parent_company', 'children'
        ]
        read_only_fields = ['created_at', 'updated_at']

    def get_parent_company(self, obj):
        if obj.parent_company:
            return {
                'id': obj.parent_company.id,
                'company_name': obj.parent_company.company_name
            }
        return None

    def get_children(self, obj):
        return [{
            'id': child.id,
            'company_name': child.company_name
        } for child in obj.direct_child_companies.all()]

    def validate_phone_number(self, value):
        if value:
            try:
                phone = parse(value, None)
                if not is_valid_number(phone):
                    raise ValidationError(_('Invalid phone number.'))
            except Exception:
                raise ValidationError(_('Invalid phone number format.'))
        return value

    def validate_website(self, value):
        if value and not value.startswith(('http://', 'https://')):
            raise ValidationError(_('Website URL should start with "http://" or "https://".'))
        return value

    def validate(self, data):
        """
        Comprehensive validation for account relationships
        - Prevents circular references
        - Ensures no self-referencing
        - Checks for potential circular parent-child relationships
        """
        # Check for self-referencing
        if data.get('parent_company') and self.instance:
            if data['parent_company'].id == self.instance.id:
                raise serializers.ValidationError({
                    'parent_company': _("A company cannot be its own parent.")
                })

        # Prevent circular references in parent-child relationships
        if data.get('parent_company'):
            parent = data['parent_company']
            current = parent
            path = set()

            while current:
                # Detect if we've seen this company before (circular reference)
                if current.id in path:
                    raise serializers.ValidationError(
                        _("Circular parent-child relationship detected.")
                    )
                
                # If we're updating an existing instance, prevent it becoming a child of its own descendants
                if self.instance and current.id == self.instance.id:
                    raise serializers.ValidationError(
                        _("Cannot create a circular parent-child relationship.")
                    )

                path.add(current.id)
                current = current.parent_company

        return data

