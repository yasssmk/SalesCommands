# tests/integration/test_throttling.py
import pytest
from rest_framework.test import APIClient
from rest_framework import status
from django.core.cache import cache

pytestmark = pytest.mark.django_db(transaction=True)

LOGIN_URL = "/client/login/"  # chemin utilisé dans tes appels curl


# ============================================================================
# Fixtures globales (réglages tests)
# ============================================================================
@pytest.fixture(autouse=True)
def _throttle_test_settings(settings):
    """
    - Active le throttling.
    - Réduit fortement les quotas pour des tests rapides.
    - Utilise un cache en mémoire (isolé pour les tests).
    - Désactive la whitelist IP pour ne pas bypasser le throttle.
    """
    settings.THROTTLING_ENABLED = True

    rf = dict(getattr(settings, "REST_FRAMEWORK", {}))
    base_rates = rf.get("DEFAULT_THROTTLE_RATES", {})
    base_rates.update({
        "anon": "100/minute",
        "user": "100/minute",
        "login": "3/minute",     # 3 tentatives/min → la 4e doit renvoyer 429
        # "password": "2/minute", # (non testé ici)
        # "burst": "10/minute",   # (non testé ici)
    })
    rf["DEFAULT_THROTTLE_RATES"] = base_rates
    settings.REST_FRAMEWORK = rf

    # Cache en mémoire pour les tests (plus rapide, propre)
    settings.CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "test-throttle",
            "TIMEOUT": None,
            "OPTIONS": {"MAX_ENTRIES": 10000},
        }
    }

    # On neutralise la whitelist pour que les tests déclenchent bien le throttle
    settings.THROTTLE_WHITELIST_IPS = []

    # Nettoyage du cache avant/après chaque test
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def api():
    """Client API sans CSRF checks (inutile pour /client/login/)"""
    return APIClient(enforce_csrf_checks=False)


# ============================================================================
# Helpers
# ============================================================================
def _post_login(api: APIClient, email: str, ip: str = "203.0.113.10"):
    """
    Envoie une tentative de login avec un IP contrôlé via X-Forwarded-For,
    et un mot de passe volontairement invalide pour obtenir 401 tant que non limité.
    """
    return api.post(
        LOGIN_URL,
        {"email": email, "password": "wrong"},
        format="json",
        HTTP_X_FORWARDED_FOR=ip,
    )


# ============================================================================
# Tests throttling login (scope "login")
# ============================================================================
def test_login_throttle_hits_429_after_quota(api):
    """
    Avec rate 'login' = 3/minute :
      - 3 premières tentatives -> 401 (invalid credentials)
      - 4e tentative -> 429 (Too Many Requests) + Retry-After
    """
    # 3 tentatives autorisées
    for _ in range(3):
        resp = _post_login(api, email="alice@test.com", ip="203.0.113.10")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    # 4e = throttled
    resp = _post_login(api, email="alice@test.com", ip="203.0.113.10")
    assert resp.status_code == status.HTTP_429_TOO_MANY_REQUESTS
    assert "Retry-After" in resp.headers
    assert str(resp.headers["Retry-After"]).isdigit()


def test_login_throttle_is_scoped_by_email(api):
    """
    Le throttle 'login' est calculé sur (IP + email).
    Après saturation pour email A, un autre email à la même IP ne doit pas être bloqué.
    """
    # Sature pour email A
    for _ in range(3):
        _post_login(api, email="alice@test.com", ip="198.51.100.5")
    resp = _post_login(api, email="alice@test.com", ip="198.51.100.5")
    assert resp.status_code == status.HTTP_429_TOO_MANY_REQUESTS

    # Même IP, autre email → devrait passer (401 et pas 429)
    resp = _post_login(api, email="bob@test.com", ip="198.51.100.5")
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED


def test_login_throttle_is_scoped_by_ip(api):
    """
    Le throttle 'login' inclut l'IP : changer d'IP doit réinitialiser le compteur.
    """
    # Sature pour IP1
    for _ in range(3):
        _post_login(api, email="charlie@test.com", ip="203.0.113.10")
    resp = _post_login(api, email="charlie@test.com", ip="203.0.113.10")
    assert resp.status_code == status.HTTP_429_TOO_MANY_REQUESTS

    # Même email, IP différente → devrait passer (401)
    resp = _post_login(api, email="charlie@test.com", ip="203.0.113.11")
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED


def test_login_throttle_whitelisted_ip_is_not_limited(api, settings):
    """
    Vérifie qu'une IP whitelisted ne subit pas de throttling.
    On remet la whitelist à ['127.0.0.1'] et on envoie XFF=127.0.0.1.
    """
    settings.THROTTLE_WHITELIST_IPS = ["127.0.0.1"]

    # Même après plusieurs tentatives, doit rester à 401 (pas 429)
    for _ in range(5):
        resp = _post_login(api, email="dana@test.com", ip="127.0.0.1")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED
