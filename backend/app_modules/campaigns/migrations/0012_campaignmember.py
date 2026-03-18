import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('module_campaigns', '0011_alter_campaigncontact_status'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='CampaignMember',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('client_id', models.UUIDField(db_index=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('role', models.CharField(
                    choices=[
                        ('OWNER', 'Campaign Owner'),
                        ('EXECUTOR', 'Executor'),
                        ('RECEIVER', 'Receiver'),
                        ('OBSERVER', 'Observer'),
                    ],
                    default='OBSERVER',
                    max_length=20,
                    verbose_name='Role',
                )),
                ('is_primary_owner', models.BooleanField(default=False, verbose_name='Is Primary Owner')),
                ('added_at', models.DateTimeField(auto_now_add=True, verbose_name='Added At')),
                ('campaign', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='members',
                    to='module_campaigns.campaign',
                    verbose_name='Campaign',
                )),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='campaign_memberships',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='User',
                )),
                ('added_by', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='+',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Added By',
                )),
                ('created_by', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='+',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('updated_by', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='+',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'db_table': 'module_campaign_members',
                'verbose_name': 'Campaign Member',
                'verbose_name_plural': 'Campaign Members',
                'ordering': ['campaign', 'role', 'added_at'],
            },
        ),
    ]