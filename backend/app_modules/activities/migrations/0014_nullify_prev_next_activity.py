
from django.db import migrations


def nullify_prev_next(apps, schema_editor):
    """
    NULL out deprecated previous_activity and next_activity linked-list fields.
    These fields are replaced by sequence_position + campaign_contact FK.
    """
    Activity = apps.get_model('module_activities', 'Activity')

    updated = Activity.objects.filter(
        previous_activity__isnull=False
    ).update(previous_activity=None)

    print(f"\n  nullified previous_activity on {updated} activities")

    updated = Activity.objects.filter(
        next_activity__isnull=False
    ).update(next_activity=None)

    print(f"  nullified next_activity on {updated} activities")


def reverse_nullify(apps, schema_editor):
    """Irreversible — data cannot be restored."""
    pass


class Migration(migrations.Migration):

    dependencies = [
        # Replace with actual last migration name
        ('module_activities', '0013_activity_source_activity'),
    ]

    operations = [
        migrations.RunPython(
            nullify_prev_next,
            reverse_code=reverse_nullify,
        ),
    ]