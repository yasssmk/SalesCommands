from rest_framework import serializers
from core.constants import COUNTRIES

class ContactDetailsSerializer(serializers.Serializer):
    """
    Base serializer for contact-related fields (used by Account and Contact).
    """

    address = serializers.CharField(required=False, allow_blank=True)
    city = serializers.CharField(required=False, allow_blank=True)
    post_code = serializers.CharField(required=False, allow_blank=True)
    state = serializers.CharField(required=False, allow_blank=True)

    country = serializers.ChoiceField(choices=COUNTRIES, required=True)

    phone_number = serializers.CharField(required=False, allow_blank=True)
    email = serializers.EmailField(required=False, allow_blank=True)

    website = serializers.URLField(required=False, allow_blank=True)
    linkedin = serializers.URLField(required=False, allow_blank=True)
