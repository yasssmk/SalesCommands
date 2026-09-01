# app_modules/signals/migrations/0041_remove_pain_impact_target_department.py
"""
Drop the legacy single-FK target_department from PainSignal and ImpactSignal.

Sub-step 2d of the "Signal scope (department)" sprint — the finition for
Pain/Impact, and the last step of the FK→M2M chantier (Constraint was done in
1a-1d). The single-FK target_department has no remaining reader or writer in
live code on either model:

  * 2a added the multi-department M2M target_departments (migration 0039) and
    backfilled it (0040);
  * 2b recabled every reader (serializers, clustering incl. the perimeter /
    department filters, prep_call, deal_health, aggregated endpoint) onto the
    M2M;
  * 2c moved extraction onto the M2M.

Audit confirms only the historical backfill migrations 0039/0040 reference the
FK (they read it against their own historical model state and are unaffected).

  * RemoveField ×2 — reversible: reversing re-adds the nullable FKs from the
    historical state carried by 0040, restoring the (empty) columns. No
    data-migration step: the M2Ms already carry the departments.

Only PainSignal and ImpactSignal are touched. Objective and People keep their
own target_department FK; Constraint already dropped its FK in 0038. The M2M
target_departments and scope_level on Pain/Impact are untouched.

Scope note: the unrelated signalclusterarchival.signal_type choices drift that
makemigrations proposes alongside is intentionally NOT included — it is a
pre-existing, choices-only (no-DDL) drift left by the People sprint and belongs
to a dedicated sanitization migration, not to this scope-M2M sub-step. Same
stance as migrations 0027/0028/0031/0036/0038/0039. This migration is
hand-written so it carries ONLY the two RemoveField operations.
"""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("module_signals", "0040_backfill_pain_impact_target_departments"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="painsignal",
            name="target_department",
        ),
        migrations.RemoveField(
            model_name="impactsignal",
            name="target_department",
        ),
    ]
