# app_modules/activities/migrations/0018_activity_next_step_signal.py
"""
Add `next_step_signal` FK on Activity, pointing to
module_signals.NextStepSignal.

Cross-app dependency
--------------------
This migration depends on module_signals.0017_nextstepsignal which
creates the NextStepSignal table. The split is required because Django
builds the cross-app FK from module_activities to module_signals —
module_signals must own the NextStepSignal table BEFORE
module_activities can add a FK to it.

Cardinality
-----------
DB-level ForeignKey (not OneToOne). The product contract is "logically
1:1" (one suggestion → one materialised Activity), but uniqueness is
NOT enforced at the schema layer because:

  * Soft duplicates from retries / network failures should not raise.
  * The reverse accessor `next_step_signal.created_activities` thus
    returns a queryset, not a single instance — defensively coded for
    edge cases.

on_delete=SET_NULL preserves Activity rows if the originating
NextStepSignal is hard-deleted. REJECTING a NextStepSignal does NOT
affect this FK (status change only, no DB cascade) — by design, so
audit can trace "this Activity was materialised from a suggestion
that was later rejected".
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('module_activities', '0017_activity_source_decision_cycle'),
        ('module_signals', '0017_nextstepsignal'),
    ]

    operations = [
        migrations.AddField(
            model_name='activity',
            name='next_step_signal',
            field=models.ForeignKey(
                blank=True,
                help_text=(
                    'Originating NextStepSignal this Activity was '
                    'materialised from (LLM-extracted post-call '
                    'suggestion that the rep accepted). Null for '
                    'Activities created directly without an LLM '
                    'suggestion.'
                ),
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='created_activities',
                to='module_signals.nextstepsignal',
                verbose_name='Next Step Signal',
            ),
        ),
    ]
