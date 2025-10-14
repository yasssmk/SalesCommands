# backend/core/middleware/test_503_middleware.py
# ⚠️ MIDDLEWARE TEMPORAIRE POUR TEST - À SUPPRIMER APRÈS

"""
Middleware de test pour simuler une vraie erreur 503 Service Unavailable.
Intercepte les requêtes avant qu'elles n'atteignent la vue.
"""

import logging
from django.http import JsonResponse

logger = logging.getLogger(__name__)


class Test503Middleware:
    """
    Middleware temporaire pour simuler une vraie erreur 503.
    
    Simule une indisponibilité du service au niveau infrastructure,
    comme si le serveur était surchargé ou un service critique était down.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        # Flag pour activer/désactiver la simulation
        self.SIMULATE_503 = True  # Mettre à False pour désactiver
        
    def __call__(self, request):
        # Vérifier si on doit simuler l'erreur 503
        if self.SIMULATE_503 and request.path == '/client/login/':
            logger.error("🧪 [TEST MIDDLEWARE] Simulating 503 - Service Unavailable")
            
            # Retourner une vraie réponse 503 comme le ferait un serveur surchargé
            # IMPORTANT : Pas de structure JSON propre DRF, juste une erreur brute
            return JsonResponse(
                {
                    'detail': 'Service Temporarily Unavailable',
                    'error': 'The server is currently unable to handle the request due to temporary overloading or maintenance.'
                },
                status=503,
                # Ajouter les headers typiques d'une erreur 503
                headers={
                    'Retry-After': '30',  # Suggère de réessayer dans 30 secondes
                    'X-Error-Type': 'infrastructure'
                }
            )
        
        # Sinon, continuer normalement
        response = self.get_response(request)
        return response