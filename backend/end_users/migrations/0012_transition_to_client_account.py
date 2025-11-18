# Generated migration for Team model transition
from django.db import migrations, models
import django.db.models.deletion


def populate_client_account(apps, schema_editor):
    """
    Populate client_account from organization.
    Every team gets its organization's client_account.
    """
    Team = apps.get_model('end_users', 'Team')
    Organization = apps.get_model('end_users', 'Organization')
    
    for team in Team.objects.select_related('organization'):
        if team.organization_id:
            try:
                org = Organization.objects.get(id=team.organization_id)
                team.client_account_id = org.client_account_id
                team.save(update_fields=['client_account_id'])
            except Organization.DoesNotExist:
                # Skip if organization doesn't exist (shouldn't happen)
                pass


class Migration(migrations.Migration):

    dependencies = [
        ('end_users', '0011_mark_admin_roles_as_locked'),  
    ]

    operations = [
        # 1. Add client_account field (nullable temporarily)
        migrations.AddField(
            model_name='team',
            name='client_account',
            field=models.ForeignKey(
                null=True,
                blank=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='teams',
                to='end_users.clientaccount',
                help_text='Client this team belongs to.',
            ),
        ),
        
        # 2. Populate client_account from organization
        migrations.RunPython(
            code=populate_client_account,
            reverse_code=migrations.RunPython.noop,
        ),
        
        # 3. Make client_account non-nullable
        migrations.AlterField(
            model_name='team',
            name='client_account',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='teams',
                to='end_users.clientaccount',
                help_text='Client this team belongs to.',
            ),
        ),
        
        # 4. Add parent_team field (for hierarchy)
        migrations.AddField(
            model_name='team',
            name='parent_team',
            field=models.ForeignKey(
                null=True,
                blank=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='direct_child_teams',
                to='end_users.team',
                help_text='Direct parent team in the hierarchy.',
            ),
        ),
        
        # 5. Add description field
        migrations.AddField(
            model_name='team',
            name='description',
            field=models.TextField(
                blank=True,
                null=True,
                verbose_name='Process Description'
            ),
        ),
        
        # 6. Remove old unique_together constraint
        migrations.AlterUniqueTogether(
            name='team',
            unique_together=set(),
        ),
        
        # 7. Remove organization FK
        migrations.RemoveField(
            model_name='team',
            name='organization',
        ),
        
        # 8. Add new unique_together constraint
        migrations.AlterUniqueTogether(
            name='team',
            unique_together={('name', 'client_account')},
        ),
    ]