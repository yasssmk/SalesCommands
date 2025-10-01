from django.apps import AppConfig



class EndUsersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'end_users'
    
    def ready(self):
        try:
            # Import des signaux pour les enregistrer
            from end_users.signals import sales_plan_signals
            from end_users.signals import cache_invalidation 
            import end_users.signals
            
            print("[END_USERS] Sales Plan signals loaded successfully")
            print("[END_USERS] Cache invalidation signals loaded successfully")
            
        except ImportError as e:
            print(f"[END_USERS] Warning: Could not load sales plan signals: {e}")
        
        except Exception as e:
            print(f"[END_USERS] Error loading signals: {e}")