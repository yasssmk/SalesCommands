# app_modules/core_modules/apps.py
"""
Django AppConfig for Core Modules.
"""

from django.apps import AppConfig
from django.db import connection
from django.db.models.signals import post_migrate


def populate_standard_departments(sender, **kwargs):
    """
    Ensures that StandardDepartment is populated after migrations.
    Fetches values directly from DepartmentChoices.
    """
    from app_modules.core_modules.models import StandardDepartment

    # Check if the table exists before inserting data
    with connection.cursor() as cursor:
        cursor.execute("SELECT to_regclass('standard_departments')")
        table_exists = cursor.fetchone()[0]

    if table_exists:
        for dept in StandardDepartment.DepartmentChoices.values:
            StandardDepartment.objects.get_or_create(name=dept)




class CoreModulesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'app_modules.core_modules'
    label = 'core_modules'
    verbose_name = 'Core Modules'

    def ready(self):
        """
        This ensures that standard departments are inserted after migrations run.
        """
        post_migrate.connect(populate_standard_departments, sender=self)
