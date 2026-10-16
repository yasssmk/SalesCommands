# app_modules/signals/migrations/0045_techstack_usage_scope_three_cases.py
"""
TechStack usage in THREE cases (Sprint TechStack, T0).

PO decision: usage at the prospect is DEPARTMENT (+ the departments using the
tool), COMPANY or UNKNOWN. TEAM is retired, "not said" is UNKNOWN (never
null), and DEPARTMENT <=> at least one usage department.

  * AlterField usage_scope — choices {DEPARTMENT, COMPANY, UNKNOWN} (COMPANY
    labelled "Company"), default UNKNOWN. null stays allowed at the DB level
    only so this migration can be reversed.
  * AlterField usage_departments — help_text only.
  * RunPython — normalise every existing row:
        has usage departments           -> DEPARTMENT
        no department, COMPANY          -> COMPANY (unchanged)
        no department, anything else    -> UNKNOWN
          (TEAM, DEPARTMENT without department, null, UNKNOWN)
    Every MODIFIED row records its ORIGIN value (null included) in
    metadata['usage_scope_migrated_from']; untouched rows get no marker.

  * reverse: restore the origin from the marker and remove the marker.
  * idempotent: a second run changes nothing and never overwrites the
    recorded origin.

Rows are written with QuerySet.update() so updated_at / updated_by are left
as they were (a data normalisation is not a user edit). Uses apps.get_model
(historical model state), never a direct import.
"""

from django.db import migrations, models
from django.db.models import Exists, OuterRef


MARKER = 'usage_scope_migrated_from'


def _target_scope(origin, has_departments):
    if has_departments:
        return 'DEPARTMENT'
    if origin == 'COMPANY':
        return 'COMPANY'
    return 'UNKNOWN'


def forwards(apps, schema_editor):
    TechStackSignal = apps.get_model('module_signals', 'TechStackSignal')
    Link = TechStackSignal.usage_departments.through
    rows = TechStackSignal.objects.annotate(
        has_departments=Exists(
            Link.objects.filter(techstacksignal_id=OuterRef('pk'))
        ),
    )
    for signal in rows.iterator():
        target = _target_scope(signal.usage_scope, signal.has_departments)
        if signal.usage_scope == target:
            continue
        metadata = dict(signal.metadata or {})
        metadata.setdefault(MARKER, signal.usage_scope)
        TechStackSignal.objects.filter(pk=signal.pk).update(
            usage_scope=target, metadata=metadata,
        )


def reverse(apps, schema_editor):
    TechStackSignal = apps.get_model('module_signals', 'TechStackSignal')
    for signal in TechStackSignal.objects.filter(
        metadata__has_key=MARKER,
    ).iterator():
        metadata = dict(signal.metadata)
        origin = metadata.pop(MARKER)
        TechStackSignal.objects.filter(pk=signal.pk).update(
            usage_scope=origin, metadata=metadata,
        )


class Migration(migrations.Migration):

    dependencies = [
        ('core_modules', '0001_initial'),
        ('module_signals', '0044_alter_constraintsignal_rigidity'),
    ]

    operations = [
        migrations.AlterField(
            model_name='techstacksignal',
            name='usage_departments',
            field=models.ManyToManyField(blank=True, help_text='The set of departments that USE this tool (multi-department: a tool can be used by Sales and Marketing at once). An attribute of the observation, populated by extraction and manual entry. Non-empty iff usage_scope is DEPARTMENT.', related_name='tech_stack_signals_used_by', to='core_modules.standarddepartment', verbose_name='Usage Departments'),
        ),
        migrations.AlterField(
            model_name='techstacksignal',
            name='usage_scope',
            field=models.CharField(blank=True, choices=[('DEPARTMENT', 'Department'), ('COMPANY', 'Company'), ('UNKNOWN', 'Unknown')], default='UNKNOWN', help_text='How the tool is used at the prospect: DEPARTMENT (the departments are in usage_departments — DEPARTMENT <=> at least one), COMPANY (company-wide) or UNKNOWN (not said).', max_length=20, null=True, verbose_name='Usage Scope'),
        ),
        migrations.RunPython(forwards, reverse),
    ]
