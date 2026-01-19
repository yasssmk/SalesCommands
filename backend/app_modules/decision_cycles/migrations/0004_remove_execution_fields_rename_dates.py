# Generated manually for field cleanup and renames

from django.db import migrations, models


class Migration(migrations.Migration):
    """
    Remove execution fields from DecisionStep and rename date fields.
    
    Rationale:
    - step_type, scheduled_date, scheduled_time belong to Activity (execution)
    - DecisionStep represents buyer milestones, not execution scheduling
    - expected_date renamed to expected_end for clarity
    - started_at renamed to start_date for consistency
    """

    dependencies = [
        ('decision_cycles', '0003_remove_decisionstep_expected_days_and_more'),
    ]

    operations = [
        # ======================================================================
        # STEP 1: Remove indexes BEFORE removing fields
        # ======================================================================
        migrations.RemoveIndex(
            model_name='decisionstep',
            name='ds_step_type_idx',
        ),
        migrations.RemoveIndex(
            model_name='decisionstep',
            name='ds_scheduled_idx',
        ),
        
        # ======================================================================
        # STEP 2: Remove execution fields (belong to Activity now)
        # ======================================================================
        migrations.RemoveField(
            model_name='decisionstep',
            name='step_type',
        ),
        migrations.RemoveField(
            model_name='decisionstep',
            name='scheduled_date',
        ),
        migrations.RemoveField(
            model_name='decisionstep',
            name='scheduled_time',
        ),
        
        # ======================================================================
        # STEP 3: Rename date fields for clarity
        # ======================================================================
        migrations.RenameField(
            model_name='decisionstep',
            old_name='expected_date',
            new_name='expected_end',
        ),
        migrations.RenameField(
            model_name='decisionstep',
            old_name='started_at',
            new_name='start_date',
        ),
        
        # ======================================================================
        # STEP 4: Update field properties (make expected_end required)
        # ======================================================================
        migrations.AlterField(
            model_name='decisionstep',
            name='expected_end',
            field=models.DateField(
                verbose_name='Expected End Date',
                help_text='Expected date for step validation/completion (mandatory for deal temporality)'
            ),
        ),
        migrations.AlterField(
            model_name='decisionstep',
            name='start_date',
            field=models.DateTimeField(
                blank=True,
                null=True,
                verbose_name='Start Date',
                help_text='When work on this step began (computed from first activity)'
            ),
        ),
    ]