#!/usr/bin/env python
"""
Script de test pour identifier pourquoi correlation_id n'est pas récupéré
À exécuter depuis : python manage.py shell
"""

def test_contextvars():
    """Test si contextvars fonctionne correctement."""
    print("\n=== TEST CONTEXTVARS ===")
    
    try:
        # Test 1 : Import et utilisation basique
        from contextvars import ContextVar
        test_var = ContextVar('test', default='default')
        
        # Set et get
        test_var.set('test_value')
        result = test_var.get()
        
        if result == 'test_value':
            print("✅ contextvars basique fonctionne")
        else:
            print(f"❌ contextvars basique échoué: {result}")
            return False
            
        # Test 2 : Notre implementation
        from core.logging.context import set_correlation_id, get_correlation_id
        
        # Test set/get
        test_id = "test-correlation-123"
        set_correlation_id(test_id)
        retrieved_id = get_correlation_id()
        
        if retrieved_id == test_id:
            print(f"✅ Notre implémentation fonctionne: {retrieved_id}")
        else:
            print(f"❌ Notre implémentation échoué: attendu '{test_id}', reçu '{retrieved_id}'")
            return False
            
        return True
        
    except ImportError as e:
        print(f"❌ ERREUR Import: {e}")
        return False
    except Exception as e:
        print(f"❌ ERREUR: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_middleware_simulation():
    """Simuler le comportement du middleware."""
    print("\n=== TEST MIDDLEWARE SIMULATION ===")
    
    try:
        from django.test import RequestFactory
        from core.logging.middlewares import RequestIdMiddleware
        from core.logging.context import get_correlation_id, set_correlation_id
        from core.logging.logger import ctx_from_request
        
        # Créer une requête de test
        factory = RequestFactory()
        request = factory.post('/test/path')
        
        print("1. Avant middleware:")
        print(f"   correlation_id = {get_correlation_id()}")
        
        # Créer et exécuter le middleware
        def dummy_get_response(req):
            from django.http import HttpResponse
            return HttpResponse("OK")
        
        middleware = RequestIdMiddleware(dummy_get_response)
        middleware.process_request(request)
        
        print("2. Après middleware.process_request:")
        print(f"   correlation_id depuis context = {get_correlation_id()}")
        print(f"   request.correlation_id = {getattr(request, 'correlation_id', 'NOT SET')}")
        
        # Tester ctx_from_request
        context = ctx_from_request(request)
        print("3. ctx_from_request résultat:")
        print(f"   correlation_id = {context.get('correlation_id')}")
        print(f"   method = {context.get('method')}")
        print(f"   path = {context.get('path')}")
        
        return context.get('correlation_id') != '-'
        
    except Exception as e:
        print(f"❌ ERREUR: {e}")
        import traceback
        traceback.print_exc()
        return False


def check_imports():
    """Vérifier que tous les imports sont corrects."""
    print("\n=== VÉRIFICATION DES IMPORTS ===")
    
    tests = []
    
    # Test core.logging.context
    try:
        from core.logging.context import get_correlation_id, set_correlation_id
        print("✅ core.logging.context importé")
        tests.append(True)
    except ImportError as e:
        print(f"❌ core.logging.context: {e}")
        tests.append(False)
    
    # Test core.logging.logger
    try:
        from core.logging.logger import get_logger, ctx_from_request
        print("✅ core.logging.logger importé")
        
        # Vérifier que ctx_from_request utilise get_correlation_id
        import inspect
        source = inspect.getsource(ctx_from_request)
        if 'get_correlation_id' in source:
            print("   ✅ ctx_from_request appelle get_correlation_id()")
        else:
            print("   ❌ ctx_from_request n'appelle PAS get_correlation_id()")
            tests.append(False)
        tests.append(True)
    except ImportError as e:
        print(f"❌ core.logging.logger: {e}")
        tests.append(False)
    
    # Test dans auth_views
    try:
        from end_users.views.auth.auth_views import UserLoginView
        print("✅ auth_views importé")
        
        # Vérifier les imports dans ce module
        import end_users.views.auth.auth_views as auth_module
        if hasattr(auth_module, 'ctx_from_request'):
            print("   ✅ ctx_from_request disponible dans auth_views")
        else:
            print("   ❌ ctx_from_request NON disponible dans auth_views")
            tests.append(False)
        tests.append(True)
    except ImportError as e:
        print(f"❌ auth_views: {e}")
        tests.append(False)
    
    return all(tests)


def main():
    print("\n" + "="*60)
    print("DIAGNOSTIC CORRELATION_ID")
    print("="*60)
    
    results = []
    
    # Test 1
    print("\n--- Test 1 ---")
    results.append(("contextvars", test_contextvars()))
    
    # Test 2
    print("\n--- Test 2 ---")
    results.append(("Imports", check_imports()))
    
    # Test 3
    print("\n--- Test 3 ---")
    results.append(("Middleware simulation", test_middleware_simulation()))
    
    # Résumé
    print("\n" + "="*60)
    print("RÉSUMÉ")
    print("="*60)
    
    for name, success in results:
        status = "✅" if success else "❌"
        print(f"{status} {name}")
    
    if not all(r[1] for r in results):
        print("\n⚠️  SOLUTION PROBABLE:")
        print("Le problème est probablement dans l'import de get_correlation_id")
        print("dans ctx_from_request() du fichier logger.py")
        print("\nVérifier que logger.py contient bien:")
        print("from .context import get_correlation_id")
        print("ET que cette fonction est appelée dans ctx_from_request()")


if __name__ == "__main__":
    main()

main()