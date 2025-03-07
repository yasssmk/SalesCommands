from ..models import StandardDepartment
from rest_framework import serializers
from core.exceptions import StandardizedValidationError

class StandardDepartmentSerializer(serializers.ModelSerializer):
    """
    Read-only serializer for StandardDepartment model.
    Used for internal taxonomy and mapping purposes only.
    """
    
    # Add display name for the choice field
    name_display = serializers.SerializerMethodField()
    
    class Meta:
        model = StandardDepartment
        fields = ['id', 'name', 'name_display']
        read_only_fields = fields  # Make all fields read-only

    def get_name_display(self, obj):
        """
        Get the display name for the department choice
        """
        return obj.get_name_display()

    def create(self, validated_data):
        """
        Prevent creation through API
        """
        raise StandardizedValidationError(
            "Standard departments cannot be created through the API"
        )

    def update(self, instance, validated_data):
        """
        Prevent updates through API
        """
        raise StandardizedValidationError(
            "Standard departments cannot be modified through the API"
        )