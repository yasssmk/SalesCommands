# backend/tests/ai_pipelines/test_people_job_title.py
"""
TD-279 D (PO) -- department of a person cited by their job title.

  * Schema + prompt people v9: `job_title` = the job title as said, or null;
    `department` = the function that title designates (neutral examples,
    never taken from the test transcripts); the "null when NOTHING is said"
    rule stays for a person whose function is not said.
  * Server safety net (REAL path, persist_stage): department null and
    job_title given -> resolve_person_department(job_title) (existing
    resolver); job_title stored in metadata.job_title. The identity rule is
    unchanged (no contact, no name, no department -> dropped).
"""

import json

import pytest

from app_modules.signals.constants import InfluenceLevel, PeopleRole


pytestmark = pytest.mark.django_db

TRANSCRIPT = '\n'.join([
    'Alex Martin: Bonjour, merci pour ce créneau.',
    'Sam Durand: Notre service finance validera le budget.',
    'Sam Durand: Le contrôleur de gestion vérifiera les hypothèses de coût.',
    'Sam Durand: Morgan, notre responsable paie, suivra le déploiement.',
])


def _person(source_quote, *, full_name=None, department=None, job_title=None):
    return {
        'full_name': full_name,
        'job_title': job_title,
        'role': PeopleRole.INFLUENCER.value,
        'influence': InfluenceLevel.MEDIUM.value,
        'department': department,
        'notes': 'Checks the figures.',
        'source_quote': source_quote,
        'confidence': 0.9,
        'is_inferred': False,
    }


def _run(account, activity, user_a, fake_provider, people):
    from app_modules.ai_pipelines.pipelines.transcript_signals import (
        QualificationSignalsPipeline,
    )
    fake_provider.replies = {'people': json.dumps({'signals': people})}
    signals = QualificationSignalsPipeline().run(
        transcript=TRANSCRIPT, activity=activity, user=user_a,
        client_id=account.client_id,
    )['signals_by_stage']['people']
    for signal in signals:
        signal.refresh_from_db()
    return signals


def _prompt():
    from app_modules.ai_pipelines.prompts.transcript_signals.people_v1 import (
        build_people_request,
    )
    return ' '.join(build_people_request('TRANSCRIPT').split())


# =============================================================================
# SERVER — persist_stage
# =============================================================================

class TestServerSafetyNet:

    def test_department_null_job_title_resolvable_department_from_the_title(
        self, account, activity, user_a, fake_provider, patch_active_provider,
    ):
        [signal] = _run(account, activity, user_a, fake_provider, [
            _person('Notre service finance validera le budget.', job_title='Finance'),
        ])
        assert signal.target_department.name == 'Finance'
        assert signal.metadata['job_title'] == 'Finance'

    def test_the_department_returned_by_the_model_wins_over_the_title(
        self, account, activity, user_a, fake_provider, patch_active_provider,
    ):
        [signal] = _run(account, activity, user_a, fake_provider, [
            _person('Notre service finance validera le budget.',
                    department='HR', job_title='Finance'),
        ])
        assert signal.target_department.name == 'HR'
        assert signal.metadata['job_title'] == 'Finance'

    def test_a_named_person_keeps_the_title_even_when_unresolved(
        self, account, activity, user_a, fake_provider, patch_active_provider,
    ):
        [signal] = _run(account, activity, user_a, fake_provider, [
            _person('Morgan, notre responsable paie, suivra le déploiement.',
                    full_name='Morgan', job_title='notre responsable paie'),
        ])
        assert signal.full_name == 'Morgan'
        assert signal.target_department is None
        assert signal.metadata['job_title'] == 'notre responsable paie'

    def test_controleur_de_gestion_is_not_resolved_by_the_server(
        self, account, activity, user_a, fake_provider, patch_active_provider,
    ):
        # Characterisation (reported to the PO): the existing resolver only
        # knows a department name or a single word unique to one department;
        # "contrôleur de gestion" resolves to nothing, so the unnamed person
        # with no department is dropped by the unchanged identity rule. The
        # department must come from the model (prompt v9).
        from app_modules.ai_pipelines.services.transcript_signal_extractor import (
            resolve_person_department,
        )
        assert resolve_person_department('le contrôleur de gestion') is None
        assert _run(account, activity, user_a, fake_provider, [
            _person('Le contrôleur de gestion vérifiera les hypothèses de coût.',
                    job_title='le contrôleur de gestion'),
        ]) == []

    def test_the_model_department_keeps_the_controleur(
        self, account, activity, user_a, fake_provider, patch_active_provider,
    ):
        [signal] = _run(account, activity, user_a, fake_provider, [
            _person('Le contrôleur de gestion vérifiera les hypothèses de coût.',
                    department='Finance', job_title='le contrôleur de gestion'),
        ])
        assert signal.full_name == ''
        assert signal.target_department.name == 'Finance'
        assert signal.metadata['job_title'] == 'le contrôleur de gestion'


# =============================================================================
# SCHEMA + PROMPT v9
# =============================================================================

class TestSchemaAndPrompt:

    def test_schema_has_a_nullable_required_job_title(self):
        from app_modules.ai_pipelines.prompts.transcript_signals.people_v1 import (
            PEOPLE_RESPONSE_SCHEMA,
        )
        item = PEOPLE_RESPONSE_SCHEMA['schema']['properties']['signals']['items']
        assert item['properties']['job_title'] == {'type': ['string', 'null']}
        assert 'job_title' in item['required']

    def test_prompt_asks_the_title_and_the_department_it_designates(self):
        prompt = _prompt()
        assert '"job_title":' in prompt
        assert ('When the transcript gives the person\'s job title, `department` '
                'is the function that title designates') in prompt
        assert '"the payroll manager" -> department "HR"' in prompt
        assert '"our accounts payable clerk" -> department "Finance"' in prompt
        # The "nothing said -> null" rule stays, without a job title.
        assert 'WHEN NOTHING is said about this person\'s function' in prompt
        assert 'never fill it with a guess' in prompt

    @pytest.mark.parametrize('word', [
        # Test transcripts (Logistix demo, atelier business case) + this file.
        'contrôleur', 'gestion', 'controller', 'DSI', 'DAF', 'Isabelle', 'Claire',
        # "Marc" is left out: the pre-existing example "our CFO Marc will
        # decide" (v1) is outside step D -- reported to the PO.
        'Thomas', 'Criminelle', 'Laurent', 'Nadia', 'Karim', 'Logistix',
        'Morgan', 'paie',
    ])
    def test_examples_do_not_reuse_test_transcripts(self, word):
        assert word not in _prompt()

    def test_version(self):
        from app_modules.ai_pipelines.prompts.transcript_signals.people_v1 import (
            PEOPLE_PROMPT_VERSION,
        )
        assert PEOPLE_PROMPT_VERSION == 'v9'
