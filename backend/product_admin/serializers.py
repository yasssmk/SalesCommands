from rest_framework import serializers
from .models import ProductAdmin

class ProductAdminSerializer(serializers.ModelSerializer):

    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = ProductAdmin
        fields = ['email', 'password']

    def create(self, validated_data):
        user = ProductAdmin.objects.create_user(
            email=validated_data['email'],
            password=validated_data['password']
        )
        return user

class ProductAdminLoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)