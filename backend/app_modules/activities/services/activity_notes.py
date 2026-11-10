# app_modules/activities/services/activity_notes.py
"""
The activity's notes (`Activity.outcome_notes`) — sprint « Source / Notes ».

ONE note per activity, filled throughout its lifecycle (PO): no flow erases
or rewrites it. When the SYSTEM has something to say about an activity (a
bulk cancellation: campaign cancel-planned, a target removed, an owner
deactivated), it APPENDS one line at the END of the note:

    empty note (NULL, '' or blank)  ->  "<line>"
    written note                    ->  "<note>" + "\\n\\n" + "<line>"

`notes_with_system_line(line)` is that rule as a database expression, so a
bulk `.update(outcome_notes=notes_with_system_line(LINE), ...)` stays ONE
query. The lines themselves are constants of the module that cancels
(campaigns/constants.py, end_users/constants.py).
"""

from django.db.models import Case, F, TextField, Value, When
from django.db.models.functions import Coalesce, Concat, Trim
from django.db.models.lookups import Exact

from ..constants import NOTES_SYSTEM_LINE_SEPARATOR


def notes_with_system_line(line):
    """`outcome_notes` with `line` appended at its end (module docstring)."""
    text = TextField()
    return Case(
        When(
            Exact(
                Coalesce(Trim('outcome_notes'), Value('', output_field=text), output_field=text),
                '',
            ),
            then=Value(line, output_field=text),
        ),
        default=Concat(
            F('outcome_notes'),
            Value(f'{NOTES_SYSTEM_LINE_SEPARATOR}{line}'),
            output_field=TextField(),
        ),
        output_field=TextField(),
    )
