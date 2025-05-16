from rest_framework import serializers
from core.constants import COUNTRIES
from django.core.exceptions import ValidationError
from core.error_messages import ValidationErrorMessages, CoreErrorMessages
from phonenumbers import parse as parse_phone, is_valid_number
from django.core.validators import URLValidator


    
class ContactDetailsSerializer(serializers.Serializer):
    """Base serializer for contact-related fields"""

    address = serializers.CharField(
        required=False, 
        allow_blank=True,
        error_messages={
            'max_length': ValidationErrorMessages.MAX_LENGTH.format(
                field='Address',
                max_length=1000
            )
        }
    )
    
    city = serializers.CharField(
        required=False, 
        allow_blank=True,
        error_messages={
            'max_length': ValidationErrorMessages.MAX_LENGTH.format(
                field='City',
                max_length=50
            )
        }
    )
    
    post_code = serializers.CharField(
        required=False, 
        allow_blank=True,
        error_messages={
            'max_length': ValidationErrorMessages.MAX_LENGTH.format(
                field='Post code',
                max_length=20
            )
        }
    )
    
    state = serializers.CharField(
        required=False, 
        allow_blank=True,
        error_messages={
            'max_length': ValidationErrorMessages.MAX_LENGTH.format(
                field='State',
                max_length=50
            )
        }
    )

    country = serializers.CharField(
        error_messages={
            'required': CoreErrorMessages.REQUIRED_FIELD.format(field='Country'),
            'invalid': CoreErrorMessages.INVALID_FIELD.format(field='Country')
        }
    )

    phone_number = serializers.CharField(
        required=False, 
        allow_blank=True,
        error_messages={
            'invalid': CoreErrorMessages.INVALID_FIELD.format(field='Phone')
        }
    )
    
    email = serializers.EmailField(
        required=False, 
        allow_blank=True,
        error_messages={
            'invalid': CoreErrorMessages.INVALID_FIELD.format(field='Email')
        }
    )

    website = serializers.URLField(
        required=False, 
        allow_blank=True,
        error_messages={
            'invalid': ValidationErrorMessages.INVALID_URL
        }
    )
    
    linkedin = serializers.URLField(
        required=False, 
        allow_blank=True,
        error_messages={
            'invalid': ValidationErrorMessages.INVALID_URL
        }
    )

    email_is_valid = serializers.BooleanField(default=True)
    phone_is_valid = serializers.BooleanField(default=True)
    phone = serializers.SerializerMethodField(read_only=True)

    def get_phone(self, obj):
        """Get phone as string for campaign compatibility"""
        return str(obj.phone_number) if obj.phone_number else None

    def validate_phone_number(self, value):
        """Validate phone number format"""
        if value:
            try:
                phone_number = parse_phone(value)
                if not is_valid_number(phone_number):
                    raise ValidationError(ValidationErrorMessages.INVALID_PHONE)
                return value
            except Exception:
                raise ValidationError(ValidationErrorMessages.INVALID_PHONE)
        return value

    def validate_website(self, value):
        """Additional website validation"""
        if value:
            try:
                URLValidator()(value)
                return value
            except ValidationError:
                raise ValidationError(ValidationErrorMessages.INVALID_URL)
        return value

    def validate_linkedin(self, value):
        """Validate LinkedIn URL"""
        if value:
            try:
                URLValidator()(value)
                if 'linkedin.com' not in value.lower():
                    raise ValidationError(
                        ValidationErrorMessages.INVALID_LINKEDIN_URL
                    )
                return value
            except ValidationError:
                raise ValidationError(ValidationErrorMessages.INVALID_URL)
        return value
    
    def validate_country(self, value):
        """Validate country field"""
        if self.partial and (value is None or value == ''):
            return value
            
        valid_countries = [choice[0] for choice in COUNTRIES]
        if value not in valid_countries:
            raise serializers.ValidationError(
                CoreErrorMessages.INVALID_FIELD.format(field="Country")
            )
        return value

class ContactValidationMixin:
    """Mixin for common contact validation logic"""
    
    def validate_contact_details(self, data):
        """Validate interdependent contact fields"""
        # If any address field is provided, ensure country is set
        address_fields = ['address', 'city', 'state', 'post_code']
        has_address = any(data.get(field) for field in address_fields)
        
        if has_address and not data.get('country'):
            raise ValidationError({
                'country': CoreErrorMessages.REQUIRED_FIELD.format(
                    field='Country'
                )
            })
            
        # Normalize email
        if 'email' in data and data['email']:
            data['email'] = data['email'].lower().strip()
            
        return data
