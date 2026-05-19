# app_modules/ai_pipelines/services/__init__.py
"""
Services package for ai_pipelines.

Re-exports the public service entry points so callers can import them
from the package root:

    from app_modules.ai_pipelines.services import TranscriptSignalExtractor

When new services land (future game-plan generator, sentiment analyser,
etc.), add them here and to __all__.
"""

from .transcript_signal_extractor import TranscriptSignalExtractor


__all__ = ['TranscriptSignalExtractor']