# backend/tests/ai_pipelines/test_quote_label_prefix.py
"""
TD-279 (PO, after the V + V-bis + D eval) -- the LLM sometimes copies the
speaker label at the head of a quote ("Criminelle Husky: Et c'est moi...").
At the COMMON point every transcript_signals stage goes through
(TranscriptSignalExtractor.persist_stage), a leading label is removed --
ONLY when it is a speaker label of THIS transcript (transcript_text label
reading), never any other ":". REAL path: FakeProvider -> persist_stage.
"""

import json

import pytest

from app_modules.signals.constants import InfluenceLevel, PeopleRole


pytestmark = pytest.mark.django_db

TRANSCRIPT = '\n'.join([
    'Atelier projet - 2026/10/20 14:00 CEST - Transcript',
    '00:00:00',
    'Julien Moreau: Bonjour à tous.',
    'Claire Dubois: Isabelle Roux, notre DAF, tient le budget.',
    "Criminelle Husky: Et c'est moi qui préparerai les chiffres du business case.",
    'Criminelle Husky: Objectif : réduire de moitié le temps de saisie.',
])
OWN_LINE = "Et c'est moi qui préparerai les chiffres du business case."


def _person(full_name, source_quote):
    return {
        'full_name': full_name, 'job_title': None,
        'role': PeopleRole.CHAMPION.value, 'influence': InfluenceLevel.HIGH.value,
        'department': None, 'notes': 'Prepares the figures.',
        'source_quote': source_quote, 'confidence': 0.9, 'is_inferred': False,
    }


def _blocker(source_quote):
    return {
        'summary': 'A concern on the budget.', 'source_quote': source_quote,
        'confidence': 0.85, 'is_inferred': False, 'raised_by_name': None,
    }


def _impact(source_quote):
    return {
        'what': 'OPS', 'dimension': 'TIME', 'impact_type': 'TIME',
        'scope_level': 'BUSINESS', 'target_departments': [],
        'summary': 'Data entry takes too long', 'source_quote': source_quote,
        'confidence': 0.9, 'is_inferred': False,
    }


def _run(account, activity, user_a, fake_provider, **replies):
    from app_modules.ai_pipelines.pipelines.transcript_signals import (
        QualificationSignalsPipeline,
    )
    fake_provider.replies = replies
    stages = QualificationSignalsPipeline().run(
        transcript=TRANSCRIPT, activity=activity, user=user_a,
        client_id=account.client_id,
    )['signals_by_stage']
    for signals in stages.values():
        for signal in signals:
            signal.refresh_from_db()
    return stages


class TestPeople:

    def test_a_label_copied_before_her_own_line_is_removed(
        self, account, activity, user_a, fake_provider, patch_active_provider,
    ):
        [signal] = _run(account, activity, user_a, fake_provider, people=json.dumps({
            'signals': [_person('Criminelle Husky', f'Criminelle Husky: {OWN_LINE}')]}),
        )['people']
        assert signal.source_quote == OWN_LINE
        assert signal.role == PeopleRole.CHAMPION
        assert signal.metadata['evidence_check'] == {'status': 'ok'}

    def test_her_label_before_another_speakers_line_is_not_about_her(
        self, account, activity, user_a, fake_provider, patch_active_provider,
    ):
        # Without the label removal the prefixed quote is "not found"; once
        # removed, it is found -- and it is Claire's line, not hers.
        [signal] = _run(account, activity, user_a, fake_provider, people=json.dumps({
            'signals': [_person('Criminelle Husky',
                                'Criminelle Husky: Isabelle Roux, notre DAF, tient le budget.')]}),
        )['people']
        assert signal.source_quote == 'Isabelle Roux, notre DAF, tient le budget.'
        assert signal.role == PeopleRole.UNKNOWN
        assert signal.metadata['evidence_check']['status'] == 'quote_not_about_person'


class TestEveryStage:

    def test_blocker_quote_label_removed(
        self, account, activity, user_a, fake_provider, patch_active_provider,
    ):
        [signal] = _run(account, activity, user_a, fake_provider, blocker=json.dumps({
            'signals': [_blocker('Claire Dubois: Isabelle Roux, notre DAF, tient le budget.')]}),
        )['blocker']
        assert signal.source_quote == 'Isabelle Roux, notre DAF, tient le budget.'

    def test_impact_quote_label_removed_merged_stage(
        self, account, activity, user_a, fake_provider, patch_active_provider,
    ):
        [signal] = _run(account, activity, user_a, fake_provider, pain_impact=json.dumps({
            'pains': [], 'impacts': [_impact(
                'Criminelle Husky: Objectif : réduire de moitié le temps de saisie.')]}),
        )['impact']
        # Only the leading LABEL goes; the "Objectif :" of the line stays.
        assert signal.source_quote == 'Objectif : réduire de moitié le temps de saisie.'

    def test_a_colon_that_is_not_a_label_is_kept(
        self, account, activity, user_a, fake_provider, patch_active_provider,
    ):
        [signal] = _run(account, activity, user_a, fake_provider, blocker=json.dumps({
            'signals': [_blocker('Objectif : réduire de moitié le temps de saisie.')]}),
        )['blocker']
        assert signal.source_quote == 'Objectif : réduire de moitié le temps de saisie.'

    def test_a_name_that_is_not_a_speaker_of_this_transcript_is_kept(
        self, account, activity, user_a, fake_provider, patch_active_provider,
    ):
        [signal] = _run(account, activity, user_a, fake_provider, blocker=json.dumps({
            'signals': [_blocker('Paul Martin: le budget est gelé.')]}),
        )['blocker']
        assert signal.source_quote == 'Paul Martin: le budget est gelé.'
