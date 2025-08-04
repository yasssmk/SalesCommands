from django.apps import AppConfig


class CampaignConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.campaign'
    
    verbose_name = 'Campaign Management'
    
    def ready(self):
        """
        Importe les signaux au démarrage de l'application.
        Cette méthode est appelée une fois que Django a chargé tous les modèles.
        """
        # Importer les signaux pour les enregistrer
        try:
            import apps.campaign.signals
            print("[CAMPAIGN] Signals registered successfully")
        except ImportError as e:
            print(f"[CAMPAIGN] Failed to import signals: {str(e)}")
        except Exception as e:
            print(f"[CAMPAIGN] Unexpected error loading signals: {str(e)}")