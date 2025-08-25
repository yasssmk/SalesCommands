// frontend/src/utils/route-guard/PublicGuard.jsx

'use client';
import PropTypes from 'prop-types';
import { useEffect } from 'react';
import { useRouter, usePathname } from 'next/navigation';

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
  const pathname = usePathname();

   const redirectIfAuthenticatedPages = [
    '/login',
    '/register', 
    '/forgot-password'
  ];

  // ==============================|| AUTO-REDIRECT LOGIC ||============================== //

  useEffect(() => {
    // Vérifier si on est sur une page qui doit rediriger
    const shouldRedirect = redirectIfAuthenticatedPages.some(page => 
      pathname === page || pathname.startsWith(page)
    );

    // Si connecté ET sur une page qui doit rediriger → aller vers dashboard
    if (!isLoading && isAuthenticated && shouldRedirect) {
      debugLog('🚀 PublicGuard: User authenticated on login/register page, redirecting to dashboard');
      router.push(authConfig.PAGES.DASHBOARD);
    }
  }, [isLoading, isAuthenticated, pathname, router]);

  // ==============================|| RENDER LOGIC ||============================== //

  // Afficher loader pendant vérification auth
  if (isLoading) {
    return <Loader />;
  }

   // Pour les pages qui doivent rediriger (login, register)
  const shouldRedirect = redirectIfAuthenticatedPages.some(page => 
    pathname === page || pathname.startsWith(page)
  );
  
  if (isAuthenticated && shouldRedirect) {
    return null; // On redirige, pas besoin d'afficher
  }

  // Si pas connecté, afficher la page auth
  return children;
}

PublicGuard.propTypes = {
  children: PropTypes.node.isRequired
};