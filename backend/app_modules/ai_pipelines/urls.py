# app_modules/ai_pipelines/urls.py
"""
URL configuration for the ai_pipelines module.

Mounted under /module-ai-pipelines/ in salescommands/urls.py.

Routes
------
    POST /module-ai-pipelines/activity-extraction/run/
        -> ActivityExtractionView (Sprint B5)

        Unified endpoint: orchestrates Qualification + NextSteps
        pipelines on a single transcript. Preferred entry point.

    POST /module-ai-pipelines/transcript-signals/extract/
        -> TranscriptSignalsExtractView (DEPRECATED — see TD-10)

        Legacy qualification-only endpoint. Returns Deprecation +
        Sunset headers. Will be removed after frontend migration.
"""

from django.urls import path

from .views import ActivityExtractionView, LastRunView, TranscriptSignalsExtractView


urlpatterns = [
    path(
        'activity-extraction/run/',
        ActivityExtractionView.as_view(),
        name='activity-extraction-run',
    ),
    path(
        'last-run/',
        LastRunView.as_view(),
        name='last-run',
    ),
    path(
        'transcript-signals/extract/',
        TranscriptSignalsExtractView.as_view(),
        name='transcript-signals-extract',
    ),
]