from rest_framework import serializers
from .models import Contact
from core.serializers import ContactDetailsSerializer
from accounts.serializers import AccountSerializer

class ContactSerializer(serializers.ModelSerializer, ContactDetailsSerializer):
    """
    Serializer for Contact model.
    """

    # Write field for account relationship
    account_id = serializers.PrimaryKeyRelatedField(
        source='account',
        queryset=Contact.objects.all(),
        required=False,
        allow_null=True,
        write_only=True
    )

    # Read field for account details
    account = AccountSerializer(read_only=True)

    class Meta:
        model = Contact
        fields = [
            'id', 'first_name', 'last_name', 'job_title', 'account', 'account_id',
            'created_at', 'updated_at', 'address', 'city', 'post_code', 'state', 'country',
            'phone_number', 'email', 'website', 'linkedin'
        ]
        read_only_fields = ['created_at', 'updated_at']
