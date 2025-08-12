// frontend/src/utils/route-guard/PublicGuard.jsx

'use client';
import PropTypes from 'prop-types';
import { useEffect } from 'react';
import { useRouter } from 'next/navigation';

// project imports
import Loader from 'components/Loader';
import { useAuth } from 'hooks/useAuth';
import { authConfig, debugLog } from 'config/auth';

// ==============================|| PUBLIC GUARD - MVP ULTRA-SIMPLE ||============================== //

/**
 * ✅ GUARD POUR PAGES PUBLIQUES (login, register, forgot-password)
 * 
 * RESPONSABILITÉ UNIQUE :
 * - SI utilisateur connecté → redirige vers dashboard "/"
 * - SINON → affiche la page auth (children)
 * 
 * USAGE :
 * - app/(auth)/layout.jsx → <PublicGuard>{children}</PublicGuard>
 */
export default function PublicGuard({ children }) {
  const { isAuthenticated, isLoading } = useAuth();
  const router = useRouter();

  // ==============================|| AUTO-REDIRECT LOGIC ||============================== //

  useEffect(() => {
    // Si connecté et sur page publique → rediriger vers dashboard
    if (!isLoading && isAuthenticated) {
      debugLog('🚀 PublicGuard: User authenticated, redirecting to dashboard');
      router.push(authConfig.PAGES.DASHBOARD);
    }
  }, [isLoading, isAuthenticated, router]);

  // ==============================|| RENDER LOGIC ||============================== //

  // Afficher loader pendant vérification auth
  if (isLoading) {
    return <Loader />;
  }

  // Si connecté, on redirige (pas besoin d'afficher children)
  if (isAuthenticated) {
    return null;
  }

  // Si pas connecté, afficher la page auth
  return children;
}

PublicGuard.propTypes = {
  children: PropTypes.node.isRequired
};