from rest_framework import serializers
from .models import ProductAdmin

class ProductAdminSerializer(serializers.ModelSerializer):

    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = ProductAdmin
        fields = ['email', 'password']

    def validate_password(self, value):
        # Add logic for more complex password rules in the future
        if len(value) < 8:
            raise serializers.ValidationError("Password must be at least 8 characters long.")
        return value

    def create(self, validated_data):
        validated_data['password'] = self.validate_password(validated_data['password'])
        return ProductAdmin.objects.create_user(
            email=validated_data['email'],
            password=validated_data['password']
        )

