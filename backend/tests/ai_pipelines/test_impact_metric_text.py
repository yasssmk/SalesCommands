# backend/tests/ai_pipelines/test_impact_metric_text.py
"""
TD-279 C3 (PO decision): the Impact description `metric_text` (UI: "Describe
the impact" / "Impact description") is filled by the LLM (pain_impact v2) --
one short sentence describing the consequence, with the figures as said.

  * Real pipeline path (FakeProvider -> persist_stage): metric_text stored
    stripped; témoin: absent / blank -> empty (CharField blank, the model
    default), the signal is KEPT; an over-long text is cut to the model's
    max_length (never dropped).
  * Prompt text: metric_text in the impact schema, the "figured consequence of
    a pain is ALSO an impact" rule, never compute a figure; version v2.
"""

import json

import pytest

from app_modules.signals.models import ImpactSignal


pytestmark = pytest.mark.django_db

METRIC_MAX = ImpactSignal._meta.get_field('metric_text').max_length


def _impact(**overrides):
    payload = {
        'what': 'OPS', 'dimension': 'TIME', 'impact_type': 'TIME',
        'scope_level': 'BUSINESS', 'target_departments': [],
        'summary': 'Support agents lose hours every week re-typing tickets',
        'source_quote': 'each agent loses about three hours a week, twelve agents',
        'confidence': 0.9, 'is_inferred': False,
    }
    payload.update(overrides)
    return payload


def _run(account, activity, user_a, fake_provider, impact):
    from app_modules.ai_pipelines.pipelines.transcript_signals import (
        QualificationSignalsPipeline,
    )
    fake_provider.replies = {'pain_impact': json.dumps({'pains': [], 'impacts': [impact]})}
    return QualificationSignalsPipeline().run(
        transcript='A transcript for the impact metric_text test.',
        activity=activity, user=user_a, client_id=account.client_id,
    )['signals_by_stage']['impact']


class TestMetricTextPersisted:

    def test_metric_text_is_stored_stripped(
        self, account, activity, user_a, fake_provider, patch_active_provider,
    ):
        text = '  About 36 hours a week lost on re-typing (3 h x 12 agents).  '
        [signal] = _run(account, activity, user_a, fake_provider, _impact(metric_text=text))
        signal.refresh_from_db()
        assert signal.metric_text == text.strip()

    @pytest.mark.parametrize('absent', [None, '', '   '])
    def test_temoin_absent_metric_text_is_empty_and_the_signal_is_kept(
        self, absent, account, activity, user_a, fake_provider, patch_active_provider,
    ):
        [signal] = _run(account, activity, user_a, fake_provider, _impact(metric_text=absent))
        signal.refresh_from_db()
        assert signal.metric_text == ''
        assert ImpactSignal.objects.filter(id=signal.id).exists()

    def test_over_long_metric_text_is_cut_to_the_model_length(
        self, account, activity, user_a, fake_provider, patch_active_provider,
    ):
        [signal] = _run(account, activity, user_a, fake_provider,
                        _impact(metric_text='x' * (METRIC_MAX + 40)))
        signal.refresh_from_db()
        assert signal.metric_text == 'x' * METRIC_MAX


class TestPainImpactPromptV2:

    @staticmethod
    def _prompt():
        from app_modules.ai_pipelines.prompts.transcript_signals.pain_impact_v1 import (
            build_pain_impact_request,
        )
        return ' '.join(build_pain_impact_request('TRANSCRIPT').split())

    def test_metric_text_in_the_impact_schema(self):
        assert '"metric_text": <one short sentence describing the consequence' in self._prompt()

    def test_figured_consequence_of_a_pain_is_also_an_impact(self):
        prompt = self._prompt()
        assert 'A FIGURED consequence of a pain' in prompt
        assert 'is ALSO emitted as an IMPACT' in prompt

    def test_figures_kept_never_computed(self):
        prompt = self._prompt()
        assert 'every figure that is said' in prompt
        assert 'NEVER compute a figure that is not said' in prompt

    def test_examples_do_not_reuse_test_transcripts(self):
        prompt = self._prompt()
        for word in ('temps plein', 'quatre-vingts', 'dix-huit', 'Logistix', 'forecast'):
            assert word not in prompt

    def test_version(self):
        from app_modules.ai_pipelines.prompts.transcript_signals.pain_impact_v1 import (
            PAIN_IMPACT_PROMPT_VERSION,
        )
        assert PAIN_IMPACT_PROMPT_VERSION == 'v2'
