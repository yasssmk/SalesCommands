# # app_modules/signals/views/qualification_signal_views.py
# """
# QualificationSignalViewSet — CRUD + lifecycle actions for QualificationSignal.

# Inherits all shared logic from BaseSignalViewSet.
# The only responsibility of this class is wiring the correct serializers
# and queryset for QualificationSignal.
# """

# from ..models import QualificationSignal
# from ..serializers import (
#     QualificationSignalListSerializer,
#     QualificationSignalDetailSerializer,
#     QualificationSignalCreateSerializer,
#     QualificationSignalUpdateSerializer,
# )
# from .base_views import BaseSignalViewSet


# class QualificationSignalViewSet(BaseSignalViewSet):
#     """
#     API endpoints for QualificationSignal.

#     Endpoints (mounted at /signals/qualification/ via urls.py):
#       GET    /                    → list
#       POST   /                    → create
#       GET    /{id}/               → retrieve
#       PATCH  /{id}/               → partial_update
#       DELETE /{id}/               → destroy
#       POST   /{id}/validate/      → validate_signal
#       POST   /{id}/reject/        → reject_signal
#       POST   /{id}/merge/         → merge_signal
#       POST   /{id}/supersede/     → supersede_signal
#     """

#     queryset = QualificationSignal.objects.all()
#     model_label = 'qualification_signal'

#     list_serializer_class   = QualificationSignalListSerializer
#     detail_serializer_class = QualificationSignalDetailSerializer
#     create_serializer_class = QualificationSignalCreateSerializer
#     update_serializer_class = QualificationSignalUpdateSerializer