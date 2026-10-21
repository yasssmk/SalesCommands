# backend/tests/ai_pipelines/test_objective_target_date.py
"""
TD-279 C2 (PO decision): the Objective deadline `target_date` is extracted by
the LLM (objective v2) and persisted by the server.

  * Real pipeline path (FakeProvider -> persist_stage): target_date
    "2027-03-31" -> stored 2027-03-31; témoin: an invalid / non-ISO date ->
    null, the signal is KEPT; absent -> null.
  * Prompt text: target_date in the output schema, the shared relative-date
    rule (Conversation date) and the end-of-period rule; version v2.
"""

import datetime
import json

import pytest

from app_modules.signals.models import ObjectiveSignal


pytestmark = pytest.mark.django_db


def _objective(**overrides):
    payload = {
        'what': 'OPS', 'dimension': 'TIME', 'scope_level': 'BUSINESS',
        'target_department': None,
        'summary': 'Halve the time spent on manual data entry',
        'source_quote': 'We want to halve the data-entry time by the end of next year',
        'confidence': 0.9, 'is_inferred': False,
    }
    payload.update(overrides)
    return payload


def _run(account, activity, user_a, fake_provider, objective):
    from app_modules.ai_pipelines.pipelines.transcript_signals import (
        QualificationSignalsPipeline,
    )
    fake_provider.replies = {'objective': json.dumps({'signals': [objective]})}
    return QualificationSignalsPipeline().run(
        transcript='A transcript for the objective target date test.',
        activity=activity, user=user_a, client_id=account.client_id,
    )['signals_by_stage']['objective']


class TestTargetDatePersisted:

    def test_iso_target_date_is_stored(
        self, account, activity, user_a, fake_provider, patch_active_provider,
    ):
        [signal] = _run(account, activity, user_a, fake_provider,
                        _objective(target_date='2027-03-31'))
        signal.refresh_from_db()
        assert signal.target_date == datetime.date(2027, 3, 31)

    @pytest.mark.parametrize('bad', ['2027-02-30', 'fin mars', '31/03/2027', 2027, ''])
    def test_temoin_invalid_date_is_null_and_the_signal_is_kept(
        self, bad, account, activity, user_a, fake_provider, patch_active_provider,
    ):
        [signal] = _run(account, activity, user_a, fake_provider, _objective(target_date=bad))
        signal.refresh_from_db()
        assert signal.target_date is None
        assert ObjectiveSignal.objects.filter(id=signal.id).exists()

    def test_absent_target_date_is_null(
        self, account, activity, user_a, fake_provider, patch_active_provider,
    ):
        [signal] = _run(account, activity, user_a, fake_provider, _objective())
        signal.refresh_from_db()
        assert signal.target_date is None


class TestObjectivePromptV2:

    @staticmethod
    def _prompt():
        from app_modules.ai_pipelines.prompts.transcript_signals.objective_v1 import (
            build_objective_request,
        )
        return ' '.join(build_objective_request('TRANSCRIPT').split())

    def test_target_date_in_the_output_schema(self):
        assert '"target_date": "<YYYY-MM-DD' in self._prompt()

    def test_shared_relative_date_rule(self):
        from app_modules.ai_pipelines.prompts.transcript_signals.date_rules import (
            RELATIVE_DATE_RULE,
        )
        assert ' '.join(RELATIVE_DATE_RULE.split()) in self._prompt()

    def test_end_of_period_rule(self):
        prompt = self._prompt()
        assert 'is the LAST day of that period' in prompt
        assert 'null when no deadline is said' in prompt

    def test_techstack_still_carries_the_shared_rule(self):
        from app_modules.ai_pipelines.prompts.transcript_signals.date_rules import (
            RELATIVE_DATE_RULE,
        )
        from app_modules.ai_pipelines.prompts.transcript_signals.techstack_v1 import (
            build_techstack_request,
        )
        assert RELATIVE_DATE_RULE in build_techstack_request('TRANSCRIPT')

    def test_version(self):
        from app_modules.ai_pipelines.prompts.transcript_signals.objective_v1 import (
            OBJECTIVE_PROMPT_VERSION,
        )
        assert OBJECTIVE_PROMPT_VERSION == 'v2'
