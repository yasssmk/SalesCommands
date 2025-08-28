# backend/core/cache_headers_middleware.py

"""
Middleware pour ajouter des headers anti-cache aux réponses API.
Garantit l'isolation multi-tenant en empêchant le cache navigateur/proxy.
"""

from django.conf import settings 
from django.utils.cache import patch_cache_control, patch_vary_headers


class NoCacheHeadersMiddleware:
    """
    Ajoute des headers no-cache aux réponses API pour éviter
    les fuites de données inter-tenant via le cache navigateur.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        # Récupérer les préfixes depuis settings avec fallback par défaut
        self.api_prefixes = getattr(
            settings, 
            'API_ENDPOINT_PREFIXES',
            ['/client/', '/app/', '/campaign/', '/leads/', '/activities/', 
             '/opportunities/', '/signals/', '/insights/', '/product_admin/']
        )
    
    def __call__(self, request):
        response = self.get_response(request)
        
        # Appliquer uniquement aux endpoints API
        if self._is_api_endpoint(request.path):
            # Utiliser les helpers Django pour éviter écrasements/doublons
            patch_cache_control(
                response,
                no_store=True,
                no_cache=True,
                must_revalidate=True,
                private=True,
                max_age=0
            )
            
            # Ajouter Vary headers sans écraser les existants
            patch_vary_headers(response, ['Cookie', 'Authorization'])
            
            # Header Pragma pour compatibilité HTTP/1.0
            if 'Pragma' not in response:
                response['Pragma'] = 'no-cache'
            
            # Expires pour compatibilité anciens navigateurs
            if 'Expires' not in response:
                response['Expires'] = '0'
        
        return response
    
    def _is_api_endpoint(self, path):
        """
        Détermine si le path est un endpoint API qui nécessite les headers no-cache.
        """
        return any(path.startswith(prefix) for prefix in self.api_prefixes)