# backend/core/security_headers.py

"""
Middleware pour ajouter des headers de sécurité aux réponses HTTP.
Version modernisée avec meilleures pratiques de sécurité.
"""

from django.conf import settings


class SecurityHeadersMiddleware:
    """
    Ajoute des headers de sécurité modernes à toutes les réponses.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        
    def __call__(self, request):
        response = self.get_response(request)
        
        # Headers de sécurité modernes - toujours appliqués
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-Frame-Options'] = 'DENY'
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        # X-XSS-Protection supprimé (déprécié)
        
        # Headers Cross-Origin pour isolation
        response.setdefault('Cross-Origin-Opener-Policy', 'same-origin')
        response.setdefault('Cross-Origin-Resource-Policy', 'same-origin')
        
        # Permissions Policy - désactive les APIs dangereuses
        response['Permissions-Policy'] = (
            "geolocation=(), "
            "microphone=(), "
            "camera=(), "
            "payment=(), "
            "usb=(), "
            "magnetometer=()"
        )
        
        # Routes sensibles qui doivent TOUJOURS avoir no-cache
        sensitive_paths = [
            '/admin/',
            '/api/client/user/',
            '/api/client/logout/',
            '/api/client/refresh-token/',
            '/api/admin/',
        ]
        
        # Forcer no-cache pour les routes sensibles
        if any(request.path.startswith(path) for path in sensitive_paths):
            response['Cache-Control'] = 'no-store, no-cache, must-revalidate, private'
            response['Pragma'] = 'no-cache'
            response['Expires'] = '0'
        
        # 🔥 AMÉLIORATION : No-store pour TOUT contenu authentifié
        # Plus robuste que la liste de routes
        try:
            if getattr(request, 'user', None) and request.user.is_authenticated:
                # Si l'utilisateur est connecté, jamais de cache
                response['Cache-Control'] = 'no-store, no-cache, must-revalidate, private'
        except Exception:
            # En cas d'erreur, on continue sans bloquer
            pass
        
        # CSP modernisée en production
        if not settings.DEBUG:
            # 🔥 AMÉLIORATION : Retrait de 'unsafe-eval' pour plus de sécurité
            # Note : Si votre app nécessite eval(), il faudra le rajouter
            response['Content-Security-Policy'] = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com; "  # 'unsafe-eval' retiré
                "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
                "font-src 'self' https://fonts.gstatic.com data:; "
                "img-src 'self' data: https:; "
                "connect-src 'self'; "  # Ajouter vos API externes ici si nécessaire
                "frame-ancestors 'none'"  # Équivalent moderne de X-Frame-Options
            )
        
        return response