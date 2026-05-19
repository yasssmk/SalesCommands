# app_modules/ai_pipelines/views/__init__.py
"""
Views package for ai_pipelines.

Re-exports the public view classes so callers (notably urls.py) can
import them from the package root:

    from app_modules.ai_pipelines.views import TranscriptSignalsExtractView

When new endpoints land (future game-plan generator, etc.), add their
view classes here and to __all__.
"""

from .transcript_signals_view import TranscriptSignalsExtractView


__all__ = ['TranscriptSignalsExtractView']