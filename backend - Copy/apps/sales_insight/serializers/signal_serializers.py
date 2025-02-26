from rest_framework import serializers
from django.utils.translation import gettext_lazy as _
from core.client_scope import ClientScopeManager
from core.error_messages import CoreErrorMessages
from core.exceptions import StandardizedValidationError
from apps.core_apps.serializers import AccountLinkedSerializerMixin
from apps.accounts_app.accounts.models import Account
from apps.accounts_app.org_units.models import AccountOrganizationUnit
from apps.accounts_app.contacts.models import Contact
from apps.accounts_app.account_product_detail.models import AccountProductDetail
from models.signal_model import Signal

class SignalSerializer(AccountLinkedSerializerMixin, ClientScopeManager.SerializerMixin, serializers.ModelSerializer):
    """
    Serializer for the Signal model with dynamic entity references, ensuring consistency with account linking.
    """

    # Entity References (Read-Only for API output)
    account = serializers.PrimaryKeyRelatedField(
        queryset=Account.objects.all(), required=False, allow_null=True, read_only=True
    )
    org_unit = serializers.PrimaryKeyRelatedField(
        queryset=AccountOrganizationUnit.objects.all(), required=False, allow_null=True, read_only=True
    )
    contact = serializers.PrimaryKeyRelatedField(
        queryset=Contact.objects.all(), required=False, allow_null=True, read_only=True
    )
    account_product_detail = serializers.PrimaryKeyRelatedField(
        queryset=AccountProductDetail.objects.all(), required=False, allow_null=True, read_only=True
    )

    # Entity ID Input Field
    entity_id = serializers.UUIDField(write_only=True)

    # Readable choices for status & confidence
    status_label = serializers.SerializerMethodField()
    confidence_label = serializers.SerializerMethodField()

    class Meta:
        model = Signal
        fields = [
            'id', 'account', 'org_unit', 'contact', 'account_product_detail',
            'entity_type', 'entity_id', 'field_name', 'value', 'signal_type',
            'confidence', 'confidence_label', 'status', 'status_label',
            'source', 'timestamp', 'revisit_date', 'resolved_date',
            'created_at', 'updated_at', 'client_id'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'client_id']

    def get_status_label(self, obj):
        """Returns the human-readable label for the status choice."""
        return obj.get_status_display()

    def get_confidence_label(self, obj):
        """Returns the human-readable label for the confidence choice."""
        return obj.get_confidence_display()

    def validate(self, data):
        """Ensure valid entity references and correct foreign key assignment."""
        data = super().validate(data)  # Perform client scope validation

        entity_type = data.get("entity_type")
        entity_id = data.get("entity_id")

        # Mapping entity types to models
        entity_map = {
            Signal.EntityType.ACCOUNT: Account,
            Signal.EntityType.ORG_UNIT: AccountOrganizationUnit,
            Signal.EntityType.CONTACT: Contact,
            Signal.EntityType.APD: AccountProductDetail,
        }

        model_class = entity_map.get(entity_type)

        if not model_class:
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_FIELD.format(field="Invalid entity type")
            )

        try:
            entity_instance = model_class.objects.get(id=entity_id)
        except model_class.DoesNotExist:
            raise StandardizedValidationError(
                CoreErrorMessages.INVALID_FIELD.format(field=f"Entity {entity_type} not found")
            )

        # Assign the correct entity ForeignKey field dynamically
        if entity_type == Signal.EntityType.ACCOUNT:
            data["account"] = entity_instance
        elif entity_type == Signal.EntityType.ORG_UNIT:
            data["org_unit"] = entity_instance
        elif entity_type == Signal.EntityType.CONTACT:
            data["contact"] = entity_instance
        elif entity_type == Signal.EntityType.APD:
            data["account_product_detail"] = entity_instance

        return data
