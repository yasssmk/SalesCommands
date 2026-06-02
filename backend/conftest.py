# backend/conftest.py
"""
Root conftest — discovered by pytest before any sub-package conftest.
Ensures sqlite OPTIONS stripping runs at the earliest possible moment.
"""


def pytest_configure(config):
    from django.conf import settings as dj_settings
    default_db = dj_settings.DATABASES.get('default', {})
    if (
        default_db.get('ENGINE', '').endswith('sqlite3')
        and 'OPTIONS' in default_db
        and 'options' in default_db['OPTIONS']
    ):
        default_db['OPTIONS'] = {
            k: v for k, v in default_db['OPTIONS'].items()
            if k != 'options'
        }
