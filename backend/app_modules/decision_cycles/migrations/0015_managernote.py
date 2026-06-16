# Hand-written migration for ManagerNote model.

import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("decision_cycles", "0014_decisioncycle_readiness_score"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ManagerNote",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("client_id", models.UUIDField(verbose_name="Client ID")),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True, verbose_name="Created At"),
                ),
                (
                    "updated_at",
                    models.DateTimeField(auto_now=True, verbose_name="Updated At"),
                ),
                (
                    "content",
                    models.TextField(verbose_name="Content"),
                ),
                (
                    "decision_cycle",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="manager_notes",
                        to="decision_cycles.decisioncycle",
                        verbose_name="Decision Cycle",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Created By",
                    ),
                ),
                (
                    "updated_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Updated By",
                    ),
                ),
            ],
            options={
                "db_table": "manager_notes",
                "verbose_name": "Manager Note",
                "verbose_name_plural": "Manager Notes",
                "ordering": ["-created_at"],
                "indexes": [
                    models.Index(
                        fields=["decision_cycle", "-created_at"],
                        name="mn_cycle_date_idx",
                    ),
                ],
            },
        ),
    ]
