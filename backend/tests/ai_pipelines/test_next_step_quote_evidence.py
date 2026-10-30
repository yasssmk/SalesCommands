# backend/tests/ai_pipelines/test_next_step_quote_evidence.py
"""
Sprint Next steps 3.6 -- server check of a next step's source_quote (project
rule: a deterministic check rather than a prompt rule), through the REAL
pipeline path (FakeProvider -> NextStepsPipeline -> NextStepExtractor).

  * the TD-279 quote check is REUSED (people_evidence.check_quote_evidence,
    the "quote found in the transcript" part of check_people_evidence --
    nothing of the role): one algorithm, TranscriptText.contains after the
    speaker label is removed;
  * a quote not found -> the next step is KEPT, metadata.evidence_check =
    {status: "quote_not_found", detail: {parts, parts_found}} -- the status
    values of PeopleEvidenceStatus, so the front reuses PEOPLE_EVIDENCE_PILL;
    never a deletion;
  * a faithful quote carries no mark;
  * exposed by the next-step List and Detail serializers.

The real case (PO v3 run, atelier/call_20): a quote SPLICED from two
non-adjacent lines -- Thomas "... il faudra le former." + Isabelle "Et si
tout est validé, on lance le pilote avec Karim en janvier." -- with a speaker
label in the middle: real content, not verbatim.
"""

import json
from pathlib import Path

import pytest
from django.urls import reverse

from app_modules.ai_pipelines.constants import PeopleEvidenceStatus


pytestmark = pytest.mark.django_db

ATELIER = (Path(__file__).resolve().parents[2] / 'evals' / 'td279' / 'transcript_atelier.txt'
           ).read_text(encoding='utf-8')

SPLICED = ('Karim, le responsable des grands comptes, est partant pour un pilote, mais il '
           'faudra le former. Isabelle Roux: Et si tout est validé, on lance le pilote avec '
           'Karim en janvier.')
FAITHFUL = "Thomas Lefèvre: Envoyez-les avant vendredi, s'il vous plaît."
INVENTED = 'Karim a déjà suivi la formation en septembre.'


def _ns(title, quote):
    return {
        'suggested_title': title, 'suggested_activity_type': 'TASK',
        'carried_by_prospect': False, 'suggested_due_date': None, 'suggested_date_text': '',
        'suggested_decision_step': None, 'suggested_people_names': [],
        'suggested_internal_names': [], 'suggested_objective': '',
        'suggested_success_criterion': '', 'suggested_topics': '', 'source_quote': quote,
        'confidence': 0.9, 'is_inferred': False,
    }


@pytest.fixture
def stored(account, activity, user_a, fake_provider, patch_active_provider):
    from app_modules.ai_pipelines.pipelines.next_steps import NextStepsPipeline
    fake_provider.replies = {'next_steps': json.dumps({'signals': [
        _ns('Launch the pilot with Karim', SPLICED),
        _ns('Send the DPA and SOC 2 report', FAITHFUL),
        _ns('Train Karim', INVENTED),
    ]})}
    result = NextStepsPipeline().run(transcript=ATELIER, activity=activity, user=user_a,
                                     client_id=account.client_id)
    signals = {s.suggested_title: s for s in result['signals']}
    for s in signals.values():
        s.refresh_from_db()
    return result, signals


def test_a_spliced_quote_is_kept_and_marked(stored):
    _result, signals = stored
    spliced = signals['Launch the pilot with Karim']
    assert spliced.metadata['evidence_check'] == {
        'status': PeopleEvidenceStatus.QUOTE_NOT_FOUND.value,
        # Both parts are lines of the transcript, not adjacent: real content.
        'detail': {'parts': 2, 'parts_found': 2},
    }
    assert spliced.source_quote == SPLICED     # kept as given, nothing rewritten


def test_an_invented_quote_is_kept_and_marked(stored):
    _result, signals = stored
    assert signals['Train Karim'].metadata['evidence_check'] == {
        'status': PeopleEvidenceStatus.QUOTE_NOT_FOUND.value,
        'detail': {'parts': 1, 'parts_found': 0},
    }


def test_a_faithful_quote_carries_no_mark(stored):
    _result, signals = stored
    faithful = signals['Send the DPA and SOC 2 report']
    assert 'evidence_check' not in (faithful.metadata or {})
    assert faithful.source_quote == "Envoyez-les avant vendredi, s'il vous plaît."


def test_never_a_deletion_and_counted(stored):
    result, signals = stored
    assert len(signals) == 3
    assert result['run'].sub_calls[-1]['persist_counts']['quote_not_found'] == 2


def test_exposed_by_the_list_and_detail_serializers(stored, authed_api_a):
    _result, signals = stored
    spliced = signals['Launch the pilot with Karim']
    detail = authed_api_a.get(reverse('module_signals:next-step-detail', kwargs={'pk': spliced.pk}))
    assert detail.status_code == 200, detail.content
    # GET retrieve returns the serializer payload directly (no wrapper).
    assert detail.json()['metadata']['evidence_check']['status'] == 'quote_not_found'
    listing = authed_api_a.get(reverse('module_signals:next-step-list'))
    assert listing.status_code == 200, listing.content
    body = listing.json()
    rows = body.get('results') or body.get('data', {}).get('results') or body
    if isinstance(rows, dict):
        rows = rows.get('results', rows)
    by_id = {r['id']: r for r in rows}
    assert by_id[str(spliced.pk)]['metadata']['evidence_check']['status'] == 'quote_not_found'
    faithful = by_id[str(signals['Send the DPA and SOC 2 report'].pk)]
    assert 'evidence_check' not in (faithful['metadata'] or {})


def test_the_people_check_reuses_the_same_quote_check():
    """One algorithm: check_people_evidence's "quote found" step IS
    check_quote_evidence."""
    from app_modules.ai_pipelines.services import people_evidence
    from app_modules.ai_pipelines.services.transcript_text import TranscriptText
    text = TranscriptText(ATELIER)
    assert people_evidence.check_quote_evidence(INVENTED, text)[0] == PeopleEvidenceStatus.QUOTE_NOT_FOUND
    assert people_evidence.check_people_evidence('Thomas Lefèvre', INVENTED, text) == \
        PeopleEvidenceStatus.QUOTE_NOT_FOUND
    assert people_evidence.check_quote_evidence('Envoyez-les avant vendredi', text) == \
        (PeopleEvidenceStatus.OK, None)
