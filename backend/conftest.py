# backend/conftest.py
"""
Root conftest — discovered by pytest before any sub-package conftest.

1. Kills residual connections on the test database (TD-31 zombie fix).
2. Strips sqlite-only OPTIONS when running against sqlite.
"""
import logging

logger = logging.getLogger(__name__)


def pytest_configure(config):
    from django.conf import settings as dj_settings

    default_db = dj_settings.DATABASES.get('default', {})

    # When pytest-django tries to create or drop `test_<dbname>`, residual
    # sessions from a prior crashed run block the operation and cause
    # SystemExit: 2.  Terminate them proactively.
    _kill_zombie_test_db_sessions(default_db)

    # Prevent NEW zombie connections during this run.
    # CONN_MAX_AGE=600 in settings.py keeps connections alive after use;
    # those linger when pytest-django tries DROP DATABASE at teardown.
    default_db['CONN_MAX_AGE'] = 0

    if (
        default_db.get('ENGINE', '').endswith('sqlite3')
        and 'OPTIONS' in default_db
        and 'options' in default_db['OPTIONS']
    ):
        default_db['OPTIONS'] = {
            k: v for k, v in default_db['OPTIONS'].items()
            if k != 'options'
        }


def pytest_unconfigure(config):
    """
    Kill any remaining sessions on test_<NAME> after the suite finishes,
    so pytest-django's DROP DATABASE doesn't fail.
    """
    try:
        from django.conf import settings as dj_settings
        default_db = dj_settings.DATABASES.get('default', {})
        _kill_zombie_test_db_sessions(default_db)
    except Exception:
        pass


def _kill_zombie_test_db_sessions(db_settings):
    """
    Connect to the default database and terminate every session holding
    a connection to the test database (test_<NAME>).  No-op on sqlite.
    """
    engine = db_settings.get('ENGINE', '')
    if 'sqlite' in engine:
        return

    db_name = db_settings.get('NAME', '')
    if not db_name:
        return
    test_db_name = f'test_{db_name}'

    try:
        import psycopg2
        conn = psycopg2.connect(
            dbname=db_name,
            user=db_settings.get('USER', ''),
            password=db_settings.get('PASSWORD', ''),
            host=db_settings.get('HOST', ''),
            port=db_settings.get('PORT', ''),
        )
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(
                "SELECT pg_terminate_backend(pid) "
                "FROM pg_stat_activity "
                "WHERE datname = %s AND pid <> pg_backend_pid()",
                (test_db_name,),
            )
            terminated = cur.rowcount
            if terminated:
                logger.info(
                    "Terminated %d zombie connection(s) on %s",
                    terminated, test_db_name,
                )
        conn.close()
    except Exception as exc:
        logger.warning("Could not kill zombie test DB sessions: %s", exc)
