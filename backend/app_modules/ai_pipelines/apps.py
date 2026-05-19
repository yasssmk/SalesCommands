# app_modules/ai_pipelines/apps.py
"""
Django AppConfig for the AI Pipelines module.

Conventions inherited from the rest of the project:
  - Apps live under `app_modules/<name>/` — `name` must reflect the
    full dotted path so INSTALLED_APPS resolves correctly.
  - The `label` is prefixed with `module_` (same as `module_signals`,
    `module_activities`, `module_accounts`, ...). Used as the migrations
    namespace and the cross-app FK string reference (e.g.
    `'module_ai_pipelines.AIPipelineRun'`).
"""

from django.apps import AppConfig


class AIPipelinesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "app_modules.ai_pipelines"
    label = "module_ai_pipelines"
    verbose_name = "AI Pipelines"