"""
Sub-step 9c — schema drop of TechStackSignal.is_integration (last act of the
Competitors sprint).

The manual Integration tag was retired in sub-step 9b (every live reader/writer
removed; audit clean) and an integration requirement now lives as a TECHNICAL
ConstraintSignal. This test pins the SCHEMA outcome of the column drop: the
model no longer declares `is_integration`, while `is_to_replace` — the sole
surviving qualification boolean — stays declared and untouched.

Read entirely off the model's own `_meta` — the real path for "is this field
part of the model?".
"""
from app_modules.signals.models.tech_stack_signal import TechStackSignal


def _field_names():
    return {f.name for f in TechStackSignal._meta.get_fields()}


class TestTechStackIsIntegrationDropped:

    def test_is_integration_field_is_gone(self):
        # Before the RemoveField migration this is RED (field still declared);
        # after the drop the field is absent from the model.
        assert 'is_integration' not in _field_names()

    def test_is_to_replace_survives(self):
        assert 'is_to_replace' in _field_names()
