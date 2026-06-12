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

    (Legacy /transcript-signals/extract/ endpoint removed — TD-10 complete.)
"""

from django.urls import path

from .views import ActivityExtractionView, DealHealthRunView, LastRunView


urlpatterns = [
    path(
        'activity-extraction/run/',
        ActivityExtractionView.as_view(),
        name='activity-extraction-run',
    ),
    path(
        'deal-health/run/',
        DealHealthRunView.as_view(),
        name='deal-health-run',
    ),
    path(
        'last-run/',
        LastRunView.as_view(),
        name='last-run',
    ),
]