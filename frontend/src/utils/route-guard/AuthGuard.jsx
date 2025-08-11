'use client';
import PropTypes from 'prop-types';
import { useEffect, useState } from 'react';
import { useRouter, usePathname } from 'next/navigation';

// project-import
import Loader from 'components/Loader';
import { useAuth } from 'hooks/useAuth';
import { authConfig, debugLog } from 'config/auth';

// ==============================|| AUTH GUARD ||============================== //

export default function AuthGuard({ children, fallback = null, requireAuth = true }) {
  const router = useRouter();
  const pathname = usePathname();
  const { isAuthenticated, isLoading, user, error } = useAuth();
  const [isReady, setIsReady] = useState(false);

  // Pages publiques qui ne nécessitent pas d'authentification
  const publicPages = [
    authConfig.PAGES.LOGIN,
    '/register',
    '/forgot-password',
    '/reset-password',
  ];

  useEffect(() => {
    // Attendre que l'authentification soit initialisée
    if (!isLoading) {
      if (requireAuth) {
        // Page protégée - nécessite une authentification
        if (isAuthenticated) {
          debugLog('AuthGuard: Utilisateur authentifié, accès autorisé');
          setIsReady(true);
        } else {
          debugLog('AuthGuard: Utilisateur non authentifié, redirection vers login');
          router.push(authConfig.PAGES.LOGIN);
        }
      } else {
        // Page publique - pas d'authentification requise
        setIsReady(true);
        
        // Si authentifié et sur une page de login/register, rediriger vers dashboard
        if (isAuthenticated && [authConfig.PAGES.LOGIN, '/register'].includes(pathname)) {
          debugLog('AuthGuard: Utilisateur déjà connecté, redirection vers dashboard');
          router.push(authConfig.PAGES.DASHBOARD);
        }
      }
    }
  }, [isAuthenticated, isLoading, requireAuth, pathname, router]);

  // Affichage du loader pendant la vérification
  if (isLoading || !isReady) {
    return fallback || <Loader />;
  }

  // Si erreur d'authentification et page protégée
  if (error && requireAuth) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center p-6 bg-red-50 rounded-lg border border-red-200">
          <h2 className="text-lg font-semibold text-red-700 mb-2">
            Erreur d'authentification
          </h2>
          <p className="text-red-600 mb-4">{error}</p>
          <button
            onClick={() => router.push(authConfig.PAGES.LOGIN)}
            className="px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700 transition-colors"
          >
            Retour à la connexion
          </button>
        </div>
      </div>
    );
  }

  // Pour les pages protégées, vérifier l'authentification
  if (requireAuth && !isAuthenticated) {
    return null; // Redirection en cours
  }

  // Afficher le contenu
  return children;
}

AuthGuard.propTypes = {
  children: PropTypes.node.isRequired,
  fallback: PropTypes.node,
  requireAuth: PropTypes.bool,
};

// ==============================|| PUBLIC GUARD ||============================== //

/**
 * Guard pour les pages publiques (login, register, etc.)
 * Redirige vers le dashboard si déjà connecté
 */
export function PublicGuard({ children, fallback = null }) {
  return (
    <AuthGuard requireAuth={false} fallback={fallback}>
      {children}
    </AuthGuard>
  );
}

PublicGuard.propTypes = {
  children: PropTypes.node.isRequired,
  fallback: PropTypes.node,
};

// ==============================|| ROLE GUARD ||============================== //

/**
 * Guard pour protéger les pages selon le rôle utilisateur
 */
export function RoleGuard({ children, allowedRoles = [], fallback = null }) {
  const { user, isAuthenticated, isLoading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!isLoading && isAuthenticated && user) {
      const userRole = user.role || user.role_name;
      
      if (!allowedRoles.includes(userRole)) {
        debugLog('RoleGuard: Accès refusé pour le rôle:', userRole);
        // Rediriger vers une page d'accès refusé ou le dashboard
        router.push('/access-denied');
      }
    }
  }, [user, isAuthenticated, isLoading, allowedRoles, router]);

  // D'abord vérifier l'authentification
  if (!isAuthenticated || isLoading) {
    return (
      <AuthGuard fallback={fallback}>
        {children}
      </AuthGuard>
    );
  }

  // Ensuite vérifier les rôles
  if (user) {
    const userRole = user.role || user.role_name;
    
    if (!allowedRoles.includes(userRole)) {
      return (
        <div className="flex items-center justify-center min-h-screen">
          <div className="text-center p-6 bg-yellow-50 rounded-lg border border-yellow-200">
            <h2 className="text-lg font-semibold text-yellow-700 mb-2">
              Accès restreint
            </h2>
            <p className="text-yellow-600 mb-4">
              Vous n'avez pas les permissions nécessaires pour accéder à cette page.
            </p>
            <button
              onClick={() => router.push(authConfig.PAGES.DASHBOARD)}
              className="px-4 py-2 bg-yellow-600 text-white rounded hover:bg-yellow-700 transition-colors"
            >
              Retour au tableau de bord
            </button>
          </div>
        </div>
      );
    }
  }

  return children;
}

RoleGuard.propTypes = {
  children: PropTypes.node.isRequired,
  allowedRoles: PropTypes.arrayOf(PropTypes.string),
  fallback: PropTypes.node,
};