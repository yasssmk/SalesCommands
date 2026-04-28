# app_modules/tech_catalog/serializers.py
"""
Serializers for the TechCatalog module.

Four serializers, each with a focused responsibility:

    * TechCatalogListSerializer   — lightweight list view
    * TechCatalogSerializer       — full read view
    * TechCatalogCreateSerializer — write path for POST
    * TechCatalogUpdateSerializer — restricted write path for PATCH

The split follows the established CompanyAccount pattern: separating
read serializers from write serializers keeps the read surface small
(no `extra_kwargs` noise) and gives each write path its own validation
shape (Create injects `client_id`, Update keeps every field optional).

product_name auto-fill:
    The model's `clean()` auto-populates `product_name` from
    `company_name` when blank — we mirror that behaviour here so that
    the unique-constraint check sees the resolved value, not the blank
    that the client submitted. Without this mirror, two POSTs with
    `{"company_name": "Notion", "product_name": ""}` would both pass
    the uniqueness check at the serializer level (different blanks)
    but collide at the DB level.

Tenant isolation:
    All write serializers use `ClientScopeManager.SerializerMixin` to
    pull `client_id` from the JWT context and run the
    `validate_client_scoped_uniqueness` helper. The read serializers
    don't write so they don't need it, but inheriting from the mixin
    costs nothing and keeps the imports uniform.
"""

from rest_framework import serializers

from core.client_scope import ClientScopeManager
from core.error_messages import CoreErrorMessages
from core.exceptions import StandardizedValidationError

from app_modules.tech_catalog.models import TechCatalog


# =============================================================================
# LIST SERIALIZER (lightweight)
# =============================================================================

class TechCatalogListSerializer(
    ClientScopeManager.SerializerMixin,
    serializers.ModelSerializer,
):
    """
    Lightweight serializer for the table view.

    Includes everything the admin needs to scan the catalog in a row:
    both names, the two commercial flags, the vendor URL, and the last
    update timestamp. No audit FKs (created_by, updated_by) — those
    only matter on the detail view.
    """

    class Meta:
        model = TechCatalog
        fields = [
            'id',
            'company_name',
            'product_name',
            'vendor_url',
            'is_competitor',
            'is_integration_target',
            'created_at',
            'updated_at',
        ]
        read_only_fields = fields


# =============================================================================
# DETAIL SERIALIZER (full read view)
# =============================================================================

class TechCatalogSerializer(
    ClientScopeManager.SerializerMixin,
    serializers.ModelSerializer,
):
    """
    Full read serializer for the retrieve endpoint.

    Adds `client_id` and the audit FK ids on top of the list payload.
    The audit FKs are exposed as bare ids (not nested user objects) —
    the admin UI doesn't surface them, but they're useful for support
    and SOC 2 trails. If a richer audit display is ever needed,
    upgrade these to nested compact serializers at that point.
    """

    class Meta:
        model = TechCatalog
        fields = [
            'id',
            'client_id',
            'company_name',
            'product_name',
            'vendor_url',
            'is_competitor',
            'is_integration_target',
            'created_by',
            'updated_by',
            'created_at',
            'updated_at',
        ]
        read_only_fields = fields


# =============================================================================
# CREATE SERIALIZER
# =============================================================================

class TechCatalogCreateSerializer(
    ClientScopeManager.SerializerMixin,
    serializers.ModelSerializer,
):
    """
    Write serializer for POST /tech-catalog/.

    Required fields: company_name. product_name is required on the
    model but defaulted to company_name in `validate()` when blank, so
    the API client may omit it.

    `client_id` is injected from the JWT context and tenant-scoped
    uniqueness on `(company_name, product_name)` is enforced before
    save() — the catch from the DB-level unique constraint would still
    work as a safety net but is harder to translate into a friendly
    error.
    """

    class Meta:
        model = TechCatalog
        fields = [
            'company_name',
            'product_name',
            'vendor_url',
            'is_competitor',
            'is_integration_target',
        ]
        extra_kwargs = {
            'company_name': {
                'required': True,
                'allow_blank': False,
                'error_messages': {
                    'required': CoreErrorMessages.REQUIRED_FIELD.format(
                        field='Company name'
                    ),
                    'blank': CoreErrorMessages.REQUIRED_FIELD.format(
                        field='Company name'
                    ),
                },
            },
            'product_name': {
                # Optional at the API surface; we resolve blanks to
                # company_name in validate() below before the unique
                # check runs.
                'required': False,
                'allow_blank': True,
            },
            'vendor_url': {
                'required': False,
                'allow_null': True,
            },
            'is_competitor': {'required': False},
            'is_integration_target': {'required': False},
        }

    def validate(self, attrs):
        """
        Cross-field validation:

            1. Strip whitespace on both names — keeps storage clean and
               aligns the unique-check input with what the model's
               `clean()` would produce at save time.
            2. Auto-fill `product_name` from `company_name` when the
               client omitted or blanked it.
            3. Inject `client_id` from the JWT context.
            4. Enforce tenant-scoped uniqueness on
               (company_name, product_name).
        """
        # 1. Normalize whitespace
        company_name = (attrs.get('company_name') or '').strip()
        product_name = (attrs.get('product_name') or '').strip()

        # 2. Auto-fill product_name when blank
        if not product_name:
            product_name = company_name

        attrs['company_name'] = company_name
        attrs['product_name'] = product_name

        # 3. Inject client_id (raises if missing — handled by mixin)
        client_id = self._get_client_id_from_context()
        attrs['client_id'] = client_id

        # 4. Tenant-scoped uniqueness
        self.validate_client_scoped_uniqueness(
            data=attrs,
            unique_fields=['company_name', 'product_name'],
            model_class=TechCatalog,
            error_message=CoreErrorMessages.UNIQUE_CONSTRAINT.format(
                fields='company name and product name'
            ),
        )

        return attrs

    def create(self, validated_data):
        """
        Create with proper audit fields.

        We instantiate without saving so we can pass `user=` to save(),
        which sets created_by / updated_by via ModuleBaseModel.save()'s
        kwarg contract.
        """
        user = self.context.get('request').user if self.context.get('request') else None

        instance = TechCatalog(**validated_data)
        instance.save(user=user)

        return instance


# =============================================================================
# UPDATE SERIALIZER
# =============================================================================

class TechCatalogUpdateSerializer(
    ClientScopeManager.SerializerMixin,
    serializers.ModelSerializer,
):
    """
    Write serializer for PATCH /tech-catalog/<id>/.

    All fields optional — only what the admin sends gets written.

    Uniqueness check runs only when one of the two name fields is being
    changed, and uses the post-merge values (instance + payload) so the
    check reflects the row's eventual state.
    """

    class Meta:
        model = TechCatalog
        fields = [
            'company_name',
            'product_name',
            'vendor_url',
            'is_competitor',
            'is_integration_target',
        ]
        extra_kwargs = {
            'company_name': {
                'required': False,
                'allow_blank': False,
                'error_messages': {
                    'blank': CoreErrorMessages.REQUIRED_FIELD.format(
                        field='Company name'
                    ),
                },
            },
            'product_name': {
                'required': False,
                'allow_blank': True,
            },
            'vendor_url': {
                'required': False,
                'allow_null': True,
            },
            'is_competitor': {'required': False},
            'is_integration_target': {'required': False},
        }

    def validate(self, attrs):
        """
        Validation rules on update:

            1. Strip whitespace on any name field present in the payload.
            2. If `product_name` is sent and resolves to blank, auto-fill
               it from the post-merge `company_name` (payload override
               or current instance value).
            3. Enforce tenant-scoped uniqueness on
               (company_name, product_name) — but only when at least one
               of the two name fields is changing. Otherwise the check
               is wasted and would also flag the row's current values
               against itself.

        client_id is NOT touched on update — it is immutable post-create
        and BaseAPIView's perform_update already enforces that.
        """
        # 1. Normalize whitespace
        if 'company_name' in attrs and attrs['company_name'] is not None:
            attrs['company_name'] = attrs['company_name'].strip()
            if not attrs['company_name']:
                # Empty after strip on update → reject; we never let
                # company_name go blank, even silently.
                raise StandardizedValidationError(
                    CoreErrorMessages.REQUIRED_FIELD.format(
                        field='Company name'
                    )
                )

        if 'product_name' in attrs and attrs['product_name'] is not None:
            attrs['product_name'] = attrs['product_name'].strip()

        # 2. Resolve blank product_name → fall back to post-merge company_name
        if 'product_name' in attrs and not attrs['product_name']:
            company = attrs.get(
                'company_name',
                self.instance.company_name if self.instance else '',
            )
            attrs['product_name'] = company

        # 3. Uniqueness — only if a name is changing
        name_changing = 'company_name' in attrs or 'product_name' in attrs
        if name_changing and self.instance:
            uniqueness_data = {
                'company_name': attrs.get(
                    'company_name', self.instance.company_name
                ),
                'product_name': attrs.get(
                    'product_name', self.instance.product_name
                ),
            }
            self.validate_client_scoped_uniqueness(
                data=uniqueness_data,
                unique_fields=['company_name', 'product_name'],
                model_class=TechCatalog,
                error_message=CoreErrorMessages.UNIQUE_CONSTRAINT.format(
                    fields='company name and product name'
                ),
            )

        return attrs

    def update(self, instance, validated_data):
        """
        Apply the patch with audit fields.

        `user=` is forwarded to save() so updated_by gets bumped via
        ModuleBaseModel.save()'s contract.
        """
        user = self.context.get('request').user if self.context.get('request') else None

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save(user=user)

        return instance
        