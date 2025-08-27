// frontend/src/utils/route-guard/AuthGuard.jsx

'use client';
import PropTypes from 'prop-types';
import { useEffect } from 'react';
import { useRouter, usePathname } from 'next/navigation';

// project imports
import Loader from 'components/Loader';
import { useAuth } from 'hooks/useAuth';
import { authConfig, debugLog } from 'config/auth';


// ==============================|| AUTH GUARD - MVP ULTRA-SIMPLE ||============================== //

/**
 * ✅ GUARD POUR PAGES PROTÉGÉES (dashboard, profile, settings)
 * 
 * RESPONSABILITÉ UNIQUE :
 * - SI utilisateur pas connecté → sauvegarde route + redirige vers login
 * - SINON → affiche la page protégée (children)
 * 
 * USAGE :
 * - app/(dashboard)/layout.jsx → <AuthGuard>{children}</AuthGuard>
 */
export default function AuthGuard({ children }) {
  const { isAuthenticated, isLoading } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  // ==============================|| AUTH-REDIRECT LOGIC ||============================== //

  useEffect(() => {
    // Si pas connecté et sur page protégée → sauvegarder route + rediriger vers login
    if (!isLoading && !isAuthenticated) {
      debugLog('🛡️ AuthGuard: User not authenticated, redirecting to login');
      router.push(authConfig.PAGES.LOGIN);
    }
  }, [isLoading, isAuthenticated, pathname, router]);

  // ==============================|| RENDER LOGIC ||============================== //

  // Afficher loader pendant vérification auth
  if (isLoading) {
    return <Loader />;
  }

  // Si pas connecté, on redirige (pas besoin d'afficher children)
  if (!isAuthenticated) {
    return null;
  }

  // Si connecté, afficher la page protégée
  return children;
}

AuthGuard.propTypes = {
  children: PropTypes.node.isRequired
};