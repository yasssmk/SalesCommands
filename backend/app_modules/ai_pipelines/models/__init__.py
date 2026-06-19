# app_modules/ai_pipelines/models/__init__.py
"""
Public API for the AI Pipelines models package.

Currently exposes the audit record model AIPipelineRun. Future
pipelines that need their own persistent models (e.g. cached prompt
embeddings, retrieval indices, async job tracking) will be added
here.

Note on package layout:
    The module uses a `models/` PACKAGE (one file per model) rather
    than a single `models.py`, following the convention established
    by app_modules/signals/. Django's auto-discovery treats both
    forms identically as long as every concrete model is importable
    from this __init__.
"""

from .pipeline_run import AIPipelineRun
from .prep_call import PrepCallSnapshot

__all__ = [
    'AIPipelineRun',
    'PrepCallSnapshot',
]