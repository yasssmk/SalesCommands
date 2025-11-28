from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'app_modules.accounts'
    label = 'module_accounts'
    verbose_name = 'Accounts Module'
