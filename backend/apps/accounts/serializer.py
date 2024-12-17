from rest_framework import serializers
from .models import Account
from phonenumber_field.modelfields import PhoneNumberField
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

# Serializer for Account model
class AccountSerializer(serializers.ModelSerializer):
    # Fields to expose in the API
    company_name = serializers.CharField(max_length=255)
    industry = serializers.CharField(max_length=100, allow_blank=True, required=False)
    address = serializers.CharField(allow_blank=True, required=False)
    city = serializers.CharField(max_length=50)
    post_code = serializers.CharField(max_length=20, allow_blank=True, required=False)
    country = serializers.CharField(max_length=50)
    website = serializers.CharField(max_length=255, allow_blank=True, required=False)
    type = serializers.CharField(max_length=50, allow_blank=True, required=False)
    phone_number = serializers.CharField(max_length=20, allow_blank=True, required=False)
    number_of_employees = serializers.IntegerField(required=False)
    potential = serializers.DecimalField(max_digits=15, decimal_places=2, required=False)
    classification = serializers.CharField(max_length=50, allow_blank=True, required=False)
    is_parent_company = serializers.BooleanField(default=False)
    is_child_company = serializers.BooleanField(default=False)
    parent_company = serializers.PrimaryKeyRelatedField(queryset=Account.objects.all(), required=False)

    # Validation for phone_number
    def validate_phone_number(self, value):
        if value:
            try:
                from phonenumbers import parse, is_valid_number
                phone = parse(value)
                if not is_valid_number(phone):
                    raise ValidationError(_('Invalid phone number.'))
            except Exception:
                raise ValidationError(_('Invalid phone number format.'))
        return value

    # Validation for website URL (basic check for valid URL format)
    def validate_website(self, value):
        if value and not value.startswith(('http://', 'https://')):
            raise ValidationError(_('Website URL should start with "http://" or "https://".'))
        return value

    # Custom validation to ensure that both `is_parent_company` and `is_child_company` are not True at the same time
    def validate(self, data):
        if data.get('is_parent_company') and data.get('is_child_company'):
            raise ValidationError(_('A company cannot be both a parent and a child company.'))
        return data

    class Meta:
        model = Account
        fields = '__all__'
        # Optionally you can exclude fields if you don't want to expose certain fields in the API
        # exclude = ['account_owner', 'created_at', 'updated_at']
