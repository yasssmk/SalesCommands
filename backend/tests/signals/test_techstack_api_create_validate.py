# backend/tests/signals/test_techstack_api_create_validate.py
"""
API-level proof that a TechStackSignal is created and validated on its
own identity — no tech catalogue involved (S10).

What this replaces
------------------
tests/signals/test_techstack_pending_catalog_link.py covered the
catalogue-linking workflow: a PENDING signal with a null
tech_catalog_entry, PATCHed to attach a catalogue row, then validated.
Two guards enforced that workflow and both are gone with the catalogue:

  * TechStackSignalCreateSerializer marked `tech_catalog_entry` as
    required=True, so the manual/API create path could not produce a
    signal at all without first curating a catalogue row.
  * SignalManager.validate refused to promote a TechStackSignal whose
    tech_catalog_entry was null.

The tool's identity now lives on the signal (`tech_name`, plus the
normalised key derived in save()) and its commercial reading on the
three qualification booleans, so a rep can capture a tool and validate
it in one pass.

Endpoints under test:
  POST  /module-signals/tech-stack/
  PATCH /module-signals/tech-stack/{id}/
  POST  /module-signals/tech-stack/{id}/validate/

URL + auth harness mirrors the file this one replaces (reverse() on the
module_signals namespace + the authed_api_a fixture).
"""

import pytest
from django.urls import reverse
from rest_framework import status

from app_modules.signals.constants import SignalStatus
from app_modules.signals.models import TechStackSignal


pytestmark = pytest.mark.django_db(transaction=True)


# =============================================================================
# URL HELPERS
# =============================================================================

def _url_list():
    return reverse('module_signals:tech-stack-list')


def _url_detail(pk):
    return reverse('module_signals:tech-stack-detail', kwargs={'pk': pk})


def _url_validate(pk):
    return reverse('module_signals:tech-stack-validate', kwargs={'pk': pk})


def _payload(account, activity, **overrides):
    body = {
        'account': str(account.id),
        'source_activity': str(activity.id),
        'tech_name': 'Salesforce',
        'source_quote': 'We run the whole pipeline in Salesforce',
    }
    body.update(overrides)
    return body


# =============================================================================
# A — CREATE WITHOUT A CATALOGUE
# =============================================================================

class TestCreateWithoutCatalogue:

    def test_create_succeeds_with_only_a_tech_name(
        self, authed_api_a, account, activity,
    ):
        """
        The core unblocking: this exact request used to 400 with
        "A tech stack signal must reference a tech catalog entry."
        """
        response = authed_api_a.post(
            _url_list(), _payload(account, activity), format='json',
        )

        assert response.status_code == status.HTTP_201_CREATED, response.data

        sig = TechStackSignal.objects.get(account=account)
        assert sig.tech_name == 'Salesforce'
        assert sig.tech_name_normalized == 'salesforce'

    def test_created_signal_carries_the_qualification_booleans(
        self, authed_api_a, account, activity,
    ):
        # is_competitor (8b) and is_integration (9b) were both retired from the
        # serializer surface. is_to_replace is the sole writable qualification.
        response = authed_api_a.post(
            _url_list(),
            _payload(
                account, activity,
                tech_name='HubSpot',
                is_to_replace=True,
            ),
            format='json',
        )

        assert response.status_code == status.HTTP_201_CREATED, response.data

        sig = TechStackSignal.objects.get(account=account)
        assert sig.is_integration is False
        assert sig.is_to_replace is True

    def test_booleans_default_false_when_omitted(
        self, authed_api_a, account, activity,
    ):
        authed_api_a.post(_url_list(), _payload(account, activity), format='json')

        sig = TechStackSignal.objects.get(account=account)
        assert (sig.is_integration, sig.is_to_replace) == (False, False)

    def test_create_without_a_tech_name_is_rejected(
        self, authed_api_a, account, activity,
    ):
        payload = _payload(account, activity)
        payload.pop('tech_name')

        response = authed_api_a.post(_url_list(), payload, format='json')

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_with_a_blank_tech_name_is_rejected(
        self, authed_api_a, account, activity,
    ):
        """allow_blank=False plus the explicit whitespace check."""
        for blank in ('', '   '):
            response = authed_api_a.post(
                _url_list(),
                _payload(account, activity, tech_name=blank),
                format='json',
            )
            assert response.status_code == status.HTTP_400_BAD_REQUEST, blank

    def test_normalized_key_is_not_writable_from_the_api(
        self, authed_api_a, account, activity,
    ):
        """It is derived in save(); a caller cannot author it."""
        authed_api_a.post(
            _url_list(),
            _payload(
                account, activity,
                tech_name='  Salesforce   CRM ',
                tech_name_normalized='hand-written',
            ),
            format='json',
        )

        sig = TechStackSignal.objects.get(account=account)
        assert sig.tech_name_normalized == 'salesforce crm'


# =============================================================================
# B — VALIDATE WITHOUT A CATALOGUE
# =============================================================================

class TestValidateWithoutCatalogue:

    def _make_pending(self, account, activity, user, tech_name='Salesforce'):
        from app_modules.signals.constants import SignalSource

        sig = TechStackSignal(
            account=account,
            source_activity=activity,
            tech_name=tech_name,
            source=SignalSource.LLM_EXTRACTED,
            source_quote='We use Salesforce',
        )
        sig.save(user=user, client_id=account.client_id)
        return sig

    def test_pending_extracted_signal_validates_directly(
        self, authed_api_a, account, activity, user_a,
    ):
        """
        The other half of the unblocking: SignalManager.validate used to
        refuse this with the same catalogue error. A rep confirming what
        the LLM heard no longer has to curate a reference row first.
        """
        sig = self._make_pending(account, activity, user_a)
        assert sig.status == SignalStatus.PENDING

        response = authed_api_a.post(_url_validate(sig.id), {}, format='json')

        assert response.status_code == status.HTTP_200_OK, response.data
        sig.refresh_from_db()
        assert sig.status == SignalStatus.VALIDATED
        assert sig.validated_by_id == user_a.id
        assert sig.validated_at is not None

    def test_manual_create_lands_validated_in_one_pass(
        self, authed_api_a, account, activity,
    ):
        """
        MANUAL source is trusted at create (BaseSignal.save() rule 1), so
        a rep capturing a tool by hand gets a VALIDATED signal outright.
        """
        response = authed_api_a.post(
            _url_list(),
            _payload(account, activity, source='MANUAL'),
            format='json',
        )

        assert response.status_code == status.HTTP_201_CREATED, response.data
        sig = TechStackSignal.objects.get(account=account)
        assert sig.status == SignalStatus.VALIDATED


# =============================================================================
# C — EDITING THE NAME
# =============================================================================

class TestEditingTheName:

    def _make_validated(self, account, activity, user, tech_name='Sales force'):
        from app_modules.signals.constants import SignalSource

        sig = TechStackSignal(
            account=account,
            source_activity=activity,
            tech_name=tech_name,
            source=SignalSource.MANUAL,
            source_quote='We use Salesforce',
        )
        sig.save(user=user, client_id=account.client_id)
        return sig

    def test_a_validated_signals_name_can_be_corrected(
        self, authed_api_a, account, activity, user_a,
    ):
        """
        There is no catalogue lock anymore. Fixing a transcription is a
        normal edit, and the grouping key follows automatically.
        """
        sig = self._make_validated(account, activity, user_a)
        assert sig.status == SignalStatus.VALIDATED
        assert sig.tech_name_normalized == 'sales force'

        response = authed_api_a.patch(
            _url_detail(sig.id), {'tech_name': 'Salesforce'}, format='json',
        )

        assert response.status_code == status.HTTP_200_OK, response.data
        sig.refresh_from_db()
        assert sig.tech_name == 'Salesforce'
        assert sig.tech_name_normalized == 'salesforce'

    def test_blanking_the_name_is_refused(
        self, authed_api_a, account, activity, user_a,
    ):
        sig = self._make_validated(account, activity, user_a)

        response = authed_api_a.patch(
            _url_detail(sig.id), {'tech_name': '   '}, format='json',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        sig.refresh_from_db()
        assert sig.tech_name == 'Sales force'

    def test_qualification_booleans_are_patchable(
        self, authed_api_a, account, activity, user_a,
    ):
        sig = self._make_validated(account, activity, user_a)

        # is_competitor was dropped from the serializer AND the model
        # (sub-step 8b), so a PATCH carrying it is silently ignored;
        # is_integration / is_to_replace remain patchable.
        response = authed_api_a.patch(
            _url_detail(sig.id),
            {'is_competitor': True, 'is_to_replace': True},
            format='json',
        )

        assert response.status_code == status.HTTP_200_OK, response.data
        sig.refresh_from_db()
        assert sig.is_to_replace is True
        assert sig.is_integration is False


# =============================================================================
# D — READ SURFACE
# =============================================================================

class TestReadSurface:

    def test_list_exposes_name_and_booleans_and_no_catalogue_key(
        self, authed_api_a, account, activity,
    ):
        authed_api_a.post(
            _url_list(),
            _payload(account, activity, is_to_replace=True),
            format='json',
        )

        response = authed_api_a.get(_url_list())
        assert response.status_code == status.HTTP_200_OK

        payload = response.data
        rows = payload.get('results') or payload.get('data') or payload
        if isinstance(rows, dict):
            rows = rows.get('results') or rows.get('data') or []
        row = rows[0]

        assert row['tech_name'] == 'Salesforce'
        assert row['tech_name_normalized'] == 'salesforce'
        # is_competitor (8b) and is_integration (9b) were both dropped from the
        # read surface. Only is_to_replace survives as a qualification boolean.
        assert 'is_competitor' not in row
        assert 'is_integration' not in row
        assert row['is_to_replace'] is True
        assert 'tech_catalog_entry' not in row
