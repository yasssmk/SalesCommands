# backend/tests/signals/test_choices_endpoint.py
"""
S1b — the signal choices endpoint (GET /module-signals/choices/) must expose
`impact_types` (ImpactType) and `human_impacts` (HumanImpactType) so the front
edit form (EditImpactContent) can populate its two Impact selects — mirror of
how signal_whats / signal_dimensions / scope_levels are already served.

RED before the fix (both keys absent from the payload), GREEN once
SignalChoicesView.get emits them. Each entry is a {value,label} object, the
shape InlineEditableValue(type="select") consumes verbatim.
"""

import pytest
from django.urls import reverse

from app_modules.signals.constants import ImpactType, HumanImpactType


def _choices_data(authed_api):
    """GET the choices endpoint and return its `data` block."""
    resp = authed_api.get(reverse('module_signals:choices'))
    assert resp.status_code == 200
    body = resp.json()
    return body['data'] if isinstance(body, dict) and 'data' in body else body


@pytest.mark.django_db
class TestChoicesEndpointImpactAxes:
    """impact_types + human_impacts served as [{value,label}], matching the enums."""

    def test_impact_types_present_and_match_enum(self, authed_api_a):
        data = _choices_data(authed_api_a)
        assert 'impact_types' in data
        got = data['impact_types']
        assert isinstance(got, list) and len(got) > 0
        assert all(set(o.keys()) == {'value', 'label'} for o in got)
        assert [(o['value'], o['label']) for o in got] == list(ImpactType.choices)

    def test_human_impacts_present_and_match_enum(self, authed_api_a):
        data = _choices_data(authed_api_a)
        assert 'human_impacts' in data
        got = data['human_impacts']
        assert isinstance(got, list) and len(got) > 0
        assert all(set(o.keys()) == {'value', 'label'} for o in got)
        assert [(o['value'], o['label']) for o in got] == list(HumanImpactType.choices)
