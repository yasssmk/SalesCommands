# app_modules/decision_cycles/migrations/0025_people_signals_to_stakeholders.py
"""
Sprint « Cycle de vie des contacts », étape 3 -- the VALIDATED People signals
of a decision cycle become its Stakeholders.

Grouping, EXACT (never guessed, TD-279 principle), per (tenant, decision
cycle):
  1. a signal linked to a contact          -> (dc, contact)
  2. else a signal with a name             -> (dc, normalised name, department)
  3. else a department-only signal         -> (dc, department)
("Marc" and "Marc Dupont" are two stakeholders -- to be linked by hand.)

Per group: ONE Stakeholder; current_signal = the MOST RECENT signal
(created_at, then id); full_name / department copied from it; every signal
of the group gets PeopleSignal.stakeholder. PENDING / REJECTED signals, and
signals without a decision cycle, are NOT migrated. A signal with no
contact, no name and no department is skipped (cannot identify anyone).

The signals are never modified otherwise (règle doublons). Queryset writes
on historical models: no model save(), no receiver -- full_name_normalized is
computed here with a FROZEN copy of PeopleSignal._normalize_full_name.

Reverse (lossless): PeopleSignal.stakeholder back to NULL, every Stakeholder
deleted -- the signals hold all the source data.
"""

from django.db import migrations


def _normalize_full_name(value):
    """FROZEN copy of PeopleSignal._normalize_full_name (lowercase, trim,
    collapse whitespace) -- a migration never imports live model code."""
    if not value:
        return ''
    return ' '.join(str(value).lower().split())


def _group_key(ps):
    if ps.target_contact_id:
        return ('contact', ps.client_id, ps.decision_cycle_id, ps.target_contact_id)
    name = _normalize_full_name(ps.full_name)
    if name:
        return ('name', ps.client_id, ps.decision_cycle_id, name, ps.target_department_id)
    if ps.target_department_id:
        return ('dept', ps.client_id, ps.decision_cycle_id, ps.target_department_id)
    return None


def forwards(apps, schema_editor):
    PeopleSignal = apps.get_model('module_signals', 'PeopleSignal')
    Stakeholder = apps.get_model('decision_cycles', 'Stakeholder')

    signals = (
        PeopleSignal.objects
        .filter(status='VALIDATED', decision_cycle_id__isnull=False)
        .order_by('-created_at', '-id')        # most recent FIRST in each group
        .only('id', 'client_id', 'decision_cycle_id', 'target_contact_id',
              'target_department_id', 'full_name', 'created_at')
    )

    groups = {}
    for ps in signals.iterator():
        key = _group_key(ps)
        if key is None:
            continue
        groups.setdefault(key, []).append(ps)

    for members in groups.values():
        current = members[0]                   # the most recent
        stakeholder = Stakeholder.objects.create(
            client_id=current.client_id,
            decision_cycle_id=current.decision_cycle_id,
            contact_id=current.target_contact_id,
            full_name=current.full_name or '',
            full_name_normalized=_normalize_full_name(current.full_name),
            department_id=current.target_department_id,
            current_signal_id=current.id,
        )
        PeopleSignal.objects.filter(id__in=[m.id for m in members]).update(
            stakeholder_id=stakeholder.id,
        )


def reverse(apps, schema_editor):
    PeopleSignal = apps.get_model('module_signals', 'PeopleSignal')
    Stakeholder = apps.get_model('decision_cycles', 'Stakeholder')
    PeopleSignal.objects.filter(stakeholder_id__isnull=False).update(stakeholder_id=None)
    Stakeholder.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('decision_cycles', '0024_stakeholder'),
        ('module_signals', '0051_peoplesignal_stakeholder'),
    ]

    operations = [
        migrations.RunPython(forwards, reverse),
    ]
