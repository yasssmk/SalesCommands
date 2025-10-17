// frontend/src/utils/route-guard/AuthGuard.jsx

'use client';
import PropTypes from 'prop-types';
import { useEffect } from 'react';
import { useRouter, usePathname } from 'next/navigation';

// project imports
import Loader from 'components/Loader';
import { useAuth } from 'hooks/useAuth';
import { authConfig, debugLog } from 'config/auth';

// ==============================|| AUTH GUARD - WITH DEGRADED MODE ||============================== //

/**
 * ✅ GUARD POUR PAGES PROTÉGÉES (dashboard, profile, settings)
 * 
 * COMPORTEMENT:
 * - SI utilisateur pas connecté ET backend accessible → redirige vers login
 * - SI utilisateur connecté → affiche la page protégée
 * - SI mode dégradé (backend down) → affiche la page normalement, snackbar gère l'avertissement
 * 
 * USAGE:
 * - app/(dashboard)/layout.jsx → <AuthGuard>{children}</AuthGuard>
 */
export default function AuthGuard({ children }) {
  const { isAuthenticated, isLoading, isNetworkDown } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  // ==============================|| AUTH-REDIRECT LOGIC ||============================== //

  useEffect(() => {
    // ✅ Si mode dégradé: laisser l'utilisateur sur la page (snackbar gère l'avertissement)
    if (isNetworkDown) {
      debugLog('⚠️ AuthGuard: Network down mode - page visible, no redirect');
      return;
    }

    // ✅ Si pas connecté et backend accessible → rediriger vers login
    if (!isLoading && !isAuthenticated) {
      debugLog('🛡️ AuthGuard: User not authenticated, redirecting to login');
      router.push(authConfig.PAGES.LOGIN);
    }
  }, [isLoading, isAuthenticated, isNetworkDown, pathname, router]);

  // ==============================|| RENDER LOGIC ||============================== //

  // ✅ Afficher loader UNIQUEMENT pendant vérification initiale
  if (isLoading) {
    return <Loader />;
  }

  // ✅ CRITIQUE: En mode dégradé, afficher la page normalement
  // Le snackbar avertit déjà l'utilisateur du problème réseau
  if (isNetworkDown) {
    debugLog('🌐 AuthGuard: Degraded mode - showing page with offline warning');
    return children;
  }

  // Si pas connecté ET backend accessible, on redirige
  if (!isAuthenticated) {
    return null;
  }

  // Si connecté, afficher la page protégée
  return children;
}

AuthGuard.propTypes = {
  children: PropTypes.node.isRequired
};