# app_modules/ai_pipelines/urls.py
"""
URL configuration for the ai_pipelines module.

Mounted under /module-ai-pipelines/ in salescommands/urls.py.

Routes
------
    POST /module-ai-pipelines/transcript-signals/extract/
        -> TranscriptSignalsExtractView

        Extract Pain / Objective / TechStack signals from a sales-call
        transcript. See the view module docstring for the full
        request / response contract.

Future endpoints (deferred to follow-up sprints):
    POST /module-ai-pipelines/game-plan/generate/
        -> Pre-call preparation guide generator
    POST /module-ai-pipelines/sentiment-analysis/run/
        -> Per-contact rhetorical / sentiment analysis
"""

from django.urls import path

from .views import TranscriptSignalsExtractView


urlpatterns = [
    path(
        'transcript-signals/extract/',
        TranscriptSignalsExtractView.as_view(),
        name='transcript-signals-extract',
    ),
]