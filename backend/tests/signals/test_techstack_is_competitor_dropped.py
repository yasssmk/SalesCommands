"""
Sub-step 8b — schema drop of TechStackSignal.is_competitor.

The manual Competitor tag was fully retired in sub-step 8-bis (every live
reader/writer removed; audit STEP 7 clean). The historical data was migrated
to CompetitorSignal by 0031. This test pins the SCHEMA outcome of the column
drop: the model no longer declares `is_competitor`, while the two surviving
qualification booleans (`is_integration`, `is_to_replace`) stay declared and
untouched.

Read entirely off the model's own `_meta` — the real path for "is this field
part of the model?".
"""
from app_modules.signals.models.tech_stack_signal import TechStackSignal


def _field_names():
    return {f.name for f in TechStackSignal._meta.get_fields()}


class TestTechStackIsCompetitorDropped:

    def test_is_competitor_field_is_gone(self):
        # Before the RemoveField migration this is RED (field still declared);
        # after the drop the field is absent from the model.
        assert 'is_competitor' not in _field_names()

    def test_the_surviving_qualification_flag_stays(self):
        # is_integration was dropped in 9c; is_to_replace is the sole survivor.
        names = _field_names()
        assert 'is_integration' not in names
        assert 'is_to_replace' in names
