# tests/ai_pipelines/test_cache_replay_isolation.py
"""
Test that cache replay queries filter by source_run to prevent
cross-run signal leakage (TD-11 fix).
"""

import pytest
from unittest.mock import MagicMock, patch

from app_modules.ai_pipelines.views.activity_extraction_view import (
    ActivityExtractionView,
)


@pytest.mark.django_db
class TestCacheReplayIsolation:
    """
    Verify that _serialize_cached_qualif_signals and
    _serialize_cached_nextstep_signals scope queries by source_run,
    so signals from run #1 do not leak into run #2's cache replay.
    """

    def test_qualif_cache_filters_by_source_run(self):
        """
        _serialize_cached_qualif_signals must pass source_run=run
        to every signal queryset filter.
        """
        run = MagicMock()
        run.source_activity = MagicMock()
        ser_ctx = {'request': MagicMock()}

        mock_qs = MagicMock()
        mock_qs.filter.return_value = []

        with patch(
            'app_modules.ai_pipelines.views.activity_extraction_view.PainSignalDetailSerializer'
        ), patch(
            'app_modules.ai_pipelines.views.activity_extraction_view.ObjectiveSignalDetailSerializer'
        ), patch(
            'app_modules.ai_pipelines.views.activity_extraction_view.ImpactSignalDetailSerializer'
        ), patch(
            'app_modules.ai_pipelines.views.activity_extraction_view.TechStackSignalDetailSerializer'
        ), patch(
            'app_modules.ai_pipelines.views.activity_extraction_view.BlockerSignalDetailSerializer'
        ), patch(
            'app_modules.signals.models.PainSignal.objects', mock_qs,
        ), patch(
            'app_modules.signals.models.ObjectiveSignal.objects', mock_qs,
        ), patch(
            'app_modules.signals.models.ImpactSignal.objects', mock_qs,
        ), patch(
            'app_modules.signals.models.TechStackSignal.objects', mock_qs,
        ), patch(
            'app_modules.signals.models.BlockerSignal.objects', mock_qs,
        ):
            ActivityExtractionView._serialize_cached_qualif_signals(run, ser_ctx)

            for call_args in mock_qs.filter.call_args_list:
                assert call_args[1].get('source_run') == run, (
                    f"Expected source_run={run} in filter kwargs, "
                    f"got {call_args}"
                )

    def test_nextstep_cache_filters_by_source_run(self):
        """
        _serialize_cached_nextstep_signals must pass source_run=run
        to the NextStepSignal queryset filter.
        """
        run = MagicMock()
        run.source_activity = MagicMock()
        ser_ctx = {'request': MagicMock()}

        mock_qs = MagicMock()
        mock_qs.filter.return_value = []

        with patch(
            'app_modules.ai_pipelines.views.activity_extraction_view.NextStepSignalDetailSerializer'
        ), patch(
            'app_modules.signals.models.NextStepSignal.objects', mock_qs,
        ):
            ActivityExtractionView._serialize_cached_nextstep_signals(run, ser_ctx)

            mock_qs.filter.assert_called_once()
            call_kwargs = mock_qs.filter.call_args[1]
            assert call_kwargs.get('source_run') == run, (
                f"Expected source_run={run} in filter kwargs, "
                f"got {call_kwargs}"
            )
