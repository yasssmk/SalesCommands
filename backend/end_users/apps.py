from django.apps import AppConfig



class EndUsersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'end_users'
    
    def ready(self):
        import end_users.signals  # Register signals