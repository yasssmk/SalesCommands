from rest_framework import serializers
from .models import Account
from phonenumbers import parse, is_valid_number
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

class AccountSerializer(serializers.ModelSerializer):
    
    # Field for write operations
    parent_company_id = serializers.PrimaryKeyRelatedField(
        source='parent_company',
        queryset=Account.objects.all(),
        required=False,
        allow_null=True,
        write_only=True
    )
    
    # Fields for read operations
    parent_company = serializers.SerializerMethodField(read_only=True)
    direct_child_companies = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Account
        fields = [
            'id', 'company_name', 'industry', 'address', 
            'city', 'post_code', 'country', 'website', 
            'type', 'phone_number', 'created_at', 'updated_at',
            'number_of_employees', 'potential', 'classification',
            'parent_company', 'parent_company_id', 'direct_child_companies'
        ]
        read_only_fields = ['created_at', 'updated_at']

    def get_parent_company(self, obj):
        if obj.parent_company:
            return {
                'id': obj.parent_company.id,
                'company_name': obj.parent_company.company_name,
                'type': obj.parent_company.type
            }
        return None

    def get_direct_child_companies(self, obj):
        return [{
            'id': child.id,
            'company_name': child.company_name,
            'type': child.type
        } for child in obj.direct_child_companies.all()]

    # def validate_phone_number(self, value):
    #     if value:
    #         try:
    #             phone = parse(value, None)
    #             if not is_valid_number(phone):
    #                 raise ValidationError(_('Invalid phone number.'))
    #         except Exception:
    #             raise ValidationError(_('Invalid phone number format.'))
    #     return value

    # def validate_website(self, value):
    #     if value and not value.startswith(('http://', 'https://')):
    #         raise ValidationError(_('Website URL should start with "http://" or "https://".'))
    #     return value

    def validate(self, data):


        company_name = data.get('company_name')
        city = data.get('city')
        country = data.get('country')

        if Account.objects.filter(
            company_name=company_name, city=city, country=country
        ).exclude(pk=self.instance.pk if self.instance else None).exists():
            raise serializers.ValidationError({
                "error": _("An account with this company name, city, and country already exists.")
            })

        """
        Comprehensive validation for account relationships
        """
        parent_company = data.get('parent_company')
        
        if parent_company and self.instance:
            # Check for self-referencing
            if parent_company.id == self.instance.id:
                raise serializers.ValidationError({
                    'parent_company_id': _("A company cannot be its own parent.")
                })

            # Check for circular references
            current = parent_company
            path = {current.id}
            
            while current.parent_company:
                current = current.parent_company
                if current.id in path:
                    raise serializers.ValidationError({
                        'parent_company_id': _("Circular parent-child relationship detected.")
                    })
                if current.id == self.instance.id:
                    raise serializers.ValidationError({
                        'parent_company_id': _("Cannot create a circular parent-child relationship.")
                    })
                path.add(current.id)

        return data

