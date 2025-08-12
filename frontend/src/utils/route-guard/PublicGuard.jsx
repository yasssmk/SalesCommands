// frontend/src/utils/route-guard/PublicGuard.jsx

'use client';
import PropTypes from 'prop-types';
import { useEffect } from 'react';
import { useRouter, usePathname } from 'next/navigation';

// project imports
import Loader from 'components/Loader';
import { useAuth } from 'hooks/useAuth';
import { authConfig, debugLog } from 'config/auth';
import { getAndClearLastRoute } from 'api/auth';

// ==============================|| PUBLIC GUARD (GUEST GUARD) ||============================== //

/**
 * ✅ GUARD POUR PAGES PUBLIQUES - Version Unifiée
 * 
 * Utilise le hook useAuth centralisé au lieu de créer son propre context
 * 
 * RESPONSABILITÉS :
 * ✅ Rediriger vers dashboard si utilisateur déjà connecté  
 * ✅ Permettre l'accès aux pages d'auth si non connecté
 * ✅ Afficher loader pendant vérification d'authentification
 * ✅ Gestion d'erreur gracieuse
 * 
 * USAGE :
 * - Wraps app/(auth)/layout.jsx
 * - Utilisé pour login, register, forgot-password
 */
export default function PublicGuard({ children, fallback = null }) {
  const { isAuthenticated, isLoading, error } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  // ==============================|| AUTO-REDIRECT LOGIC ||============================== //

  useEffect(() => {
    // Si authentifié et sur une page publique, rediriger vers dashboard
    if (!isLoading && isAuthenticated) {
      debugLog('🚀 PublicGuard: User already authenticated, redirecting...');
      
      // Récupérer la dernière route visitée ou utiliser dashboard par défaut
      const lastRoute = getAndClearLastRoute();
      const redirectPath = lastRoute && lastRoute !== pathname ? lastRoute : authConfig.PAGES.DASHBOARD;
      
      debugLog('🚀 PublicGuard: Redirecting to:', redirectPath);
      
      // Délai court pour éviter les conflits de navigation
      setTimeout(() => {
        router.push(redirectPath);
      }, 100);
    }
  }, [isAuthenticated, isLoading, pathname, router]);

  // ==============================|| LOADING STATE ||============================== //

  // Afficher loader pendant la vérification d'authentification
  if (isLoading) {
    debugLog('⏳ PublicGuard: Authentication check in progress...');
    return fallback || <Loader />;
  }

  // ==============================|| ERROR STATE ||============================== //

  // Gestion d'erreur gracieuse (permet quand même l'accès aux pages publiques)
  if (error) {
    debugLog('⚠️ PublicGuard: Auth error detected, allowing access to public pages:', error);
    // On permet quand même l'accès aux pages publiques en cas d'erreur auth
    // Car l'utilisateur pourrait avoir besoin de se reconnecter
  }

  // ==============================|| AUTHENTICATED STATE ||============================== //

  // Si authentifié, ne pas afficher le contenu (redirection en cours)
  if (isAuthenticated) {
    debugLog('🔄 PublicGuard: Authenticated user detected, redirect in progress...');
    return fallback || <Loader />;
  }

  // ==============================|| RENDER PUBLIC CONTENT ||============================== //

  // Afficher les pages publiques pour les utilisateurs non authentifiés
  debugLog('✅ PublicGuard: Rendering public content for unauthenticated user');
  return children;
}

PublicGuard.propTypes = {
  children: PropTypes.node.isRequired,
  fallback: PropTypes.node,
};

// Guard simple et efficace - utilise composants existants uniquement