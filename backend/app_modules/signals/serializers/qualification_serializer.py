# # app_modules/signals/serializers/qualification_serializer.py
# """
# Concrete serializers for QualificationSignal.

# Inherits all shared logic from base_serializer and binds Meta.model
# to QualificationSignal. No extra model fields beyond field_name
# (which is already on BaseSignal) — the only concrete addition is
# constraining signal_type to 'qualification' via HiddenField.
# """

# from rest_framework import serializers

# from ..models import QualificationSignal
# from .base_serializer import (
#     BaseSignalListSerializer,
#     BaseSignalDetailSerializer,
#     BaseSignalCreateSerializer,
#     BaseSignalUpdateSerializer,
# )


# # =============================================================================
# # LIST
# # =============================================================================

# class QualificationSignalListSerializer(BaseSignalListSerializer):
#     """Lightweight serializer for QualificationSignal list endpoints."""

#     class Meta(BaseSignalListSerializer.Meta):
#         model  = QualificationSignal
#         fields = BaseSignalListSerializer.Meta.fields


# # =============================================================================
# # DETAIL
# # =============================================================================

# class QualificationSignalDetailSerializer(BaseSignalDetailSerializer):
#     """Full detail serializer for QualificationSignal retrieve endpoints."""

#     class Meta(BaseSignalDetailSerializer.Meta):
#         model  = QualificationSignal
#         fields = BaseSignalDetailSerializer.Meta.fields


# # =============================================================================
# # CREATE
# # =============================================================================

# class QualificationSignalCreateSerializer(BaseSignalCreateSerializer):
#     """
#     Create serializer for QualificationSignal.

#     Fixes signal_type to 'qualification' via HiddenField so the view and
#     SignalManager always receive the correct routing key without requiring
#     the client to pass it explicitly.
#     """

#     signal_type = serializers.HiddenField(default='qualification')

#     class Meta(BaseSignalCreateSerializer.Meta):
#         model  = QualificationSignal
#         fields = BaseSignalCreateSerializer.Meta.fields


# # =============================================================================
# # UPDATE
# # =============================================================================

# class QualificationSignalUpdateSerializer(BaseSignalUpdateSerializer):
#     """Restricted PATCH serializer for QualificationSignal."""

#     class Meta(BaseSignalUpdateSerializer.Meta):
#         model  = QualificationSignal
#         fields = BaseSignalUpdateSerializer.Meta.fields