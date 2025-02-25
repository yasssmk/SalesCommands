from django.urls import path
from .views.transcript_analysis_views import TranscriptAnalysisView

urlpatterns = [
    path('analyze-transcript/', TranscriptAnalysisView.as_view(), name='analyze-transcript'),
]