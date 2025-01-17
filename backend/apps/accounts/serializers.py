from rest_framework import serializers
from .models import Account
from phonenumbers import parse, is_valid_number
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

class AccountSerializer(serializers.ModelSerializer):
    # Field for write operations
    parent_id = serializers.UUIDField(
        source='parent_company_id',
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
            'city', 'post_code', 'state', 'country', 'website', 
            'type', 'phone_number', 'created_at', 'updated_at',
            'number_of_employees', 'potential', 'classification',
            'parent_company', 'parent_id', 'direct_child_companies',
            'email', 'linkedin'
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
    
    def validate(self, data):
        # Convert company name to uppercase
        company_name = data.get('company_name')
        if company_name:
            data['company_name'] = company_name.upper()
        
        # Get the current instance for update operations
        instance = getattr(self, 'instance', None)
        
        # Validate unique constraint
        if Account.objects.filter(
            company_name__iexact=company_name,
            city__iexact=data.get('city'),
            country__iexact=data.get('country')
        ).exclude(pk=instance.pk if instance else None).exists():
            raise serializers.ValidationError({
                "error": "This account already exists."
            })
        
        # Validate parent-child relationship
        parent_id = data.get('parent_company_id')
        if parent_id:
            try:
                parent = Account.objects.get(id=parent_id)
                if instance and parent.id == instance.id:
                    raise serializers.ValidationError({
                        'parent_id': "A company cannot be its own parent."
                    })
                
                # Check for circular references
                if instance:
                    current = parent
                    path = {current.id}
                    while current.parent_company:
                        current = current.parent_company
                        if current.id in path or current.id == instance.id:
                            raise serializers.ValidationError({
                                'parent_id': "Cannot create a circular parent-child relationship."
                            })
                        path.add(current.id)
            except Account.DoesNotExist:
                raise serializers.ValidationError({
                    'parent_id': "Invalid parent company ID."
                })
        
        return data

