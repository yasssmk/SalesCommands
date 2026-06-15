from django.apps import AppConfig


class DecisionCyclesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'app_modules.decision_cycles'
    label = 'decision_cycles'
    verbose_name = 'Decision Cycles'

    def ready(self):
        """Register readiness recompute signals when app is ready."""
        try:
            from app_modules.decision_cycles.signals import readiness_recompute  # noqa: F401
        except ImportError as e:
            import logging
            logging.getLogger('app_modules.decision_cycles').warning(
                "readiness_recompute_import_failed", exc_info=e
            )