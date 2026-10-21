# backend/tests/ai_pipelines/test_blocker_prompt_v4.py
"""
TD-279 C6 (PO decision): blocker prompt v4 -- a blocker is what STOPS the
deal today OR what can SLOW it (a concern, an objection or a future risk the
PROSPECT expresses: adoption, resistance to change, doubt on an
integration...), always said in the transcript, never imagined. A firm
requirement stays a CONSTRAINT; the blocking threat that follows from it is a
blocker. raised_by_name unchanged.
"""

import pytest


def _prompt():
    from app_modules.ai_pipelines.prompts.transcript_signals.blocker_v1 import (
        build_blocker_request,
    )
    # Neutral transcript: only the prompt's own text is checked.
    return ' '.join(build_blocker_request('TRANSCRIPT').split())


class TestBlockerPromptV4:

    def test_definition_covers_stop_today_or_slow_down(self):
        prompt = _prompt()
        assert 'what STOPS the deal today OR what can SLOW it' in prompt
        assert 'a concern, an objection or a future risk the PROSPECT expresses' in prompt
        assert 'adoption by the users, resistance to change, doubt about an integration' in prompt
        # The v3 wording ("currently STOPS" only) is gone.
        assert 'A BLOCKER is what currently STOPS the deal' not in prompt

    def test_a_risk_must_be_said_never_imagined(self):
        prompt = _prompt()
        assert 'A risk is emitted ONLY when the PROSPECT says it in the transcript' in prompt
        assert 'never a risk you imagine yourself' in prompt

    def test_constraint_vs_blocking_threat(self):
        prompt = _prompt()
        assert 'Blocker vs. Constraint (important distinction)' in prompt
        assert 'A firm REQUIREMENT the solution must meet is a CONSTRAINT' in prompt
        assert 'the THREAT of blocking the deal that follows from it is a BLOCKER' in prompt

    def test_raised_by_name_unchanged(self):
        prompt = _prompt()
        assert '"raised_by_name":' in prompt
        assert 'ATTRIBUTION RULES (raised_by_name)' in prompt

    @pytest.mark.parametrize('word', [
        # Logistix demo + "atelier business case" test transcripts
        'Logistix', 'Criminelle', 'Isabelle', 'Thomas', 'Laurent', 'Karim', 'Claire',
        'DSI', 'SOC 2', 'Europe', 'hébergement', 'hébergées', 'commerciaux', 'Francfort',
        'Salesforce', 'Azure',
    ])
    def test_examples_do_not_reuse_test_transcripts(self, word):
        assert word not in _prompt()

    def test_version(self):
        from app_modules.ai_pipelines.prompts.transcript_signals.blocker_v1 import (
            BLOCKER_PROMPT_VERSION,
        )
        assert BLOCKER_PROMPT_VERSION == 'v4'
