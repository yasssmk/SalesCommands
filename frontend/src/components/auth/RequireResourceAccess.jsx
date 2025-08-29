// frontend/src/components/auth/RequireResourceAccess.jsx

'use client';

import PropTypes from 'prop-types';
import { notFound } from 'next/navigation';
import { useEffect } from 'react';

// project imports
import Loader from 'components/Loader';

// ==============================|| REQUIRE RESOURCE ACCESS ||============================== //

/**
 * ✅ GARDE D'ACCÈS GÉNÉRIQUE POUR RESSOURCES SENSIBLES
 * 
 * SÉCURITÉ RENFORCÉE :
 * - Zéro rendu tant que l'accès n'est pas confirmé (pas de flash)
 * - notFound() en cas d'erreur (déclenche app/not-found.js - pas de détail sur l'ID) 
 * - Client-only (pas de pré-render RSC)
 * 
 * USAGE :
 * <RequireResourceAccess 
 *   resourceId="123"
 *   useResourceHook={useGetUser}
 *   loadingComponent={<CustomLoader />}
 * >
 *   <ChangePasswordForm />
 * </RequireResourceAccess>
 */
export default function RequireResourceAccess({
  resourceId,
  useResourceHook,
  children,
  loadingComponent
}) {
  // Appeler le hook pour vérifier l'accès à la ressource
  const hookResult = useResourceHook(resourceId);
  
  // Extraire les propriétés communes des hooks (useGetUser, useGetTeam, etc.)
  const isLoading = hookResult.userLoading || hookResult.teamLoading || hookResult.loading || false;
  const error = hookResult.userError || hookResult.teamError || hookResult.error || null;
  const resource = hookResult.user || hookResult.team || hookResult.data || null;

  // ==============================|| ERROR HANDLING ||============================== //

  useEffect(() => {
    // Si erreur 404/403 → déclencher notFound() de Next.js
    if (!isLoading && error) {
      // Analyser le type d'erreur
      const isAccessError = error.status === 404 || 
                           error.status === 403 || 
                           error.message?.includes('404') ||
                           error.message?.includes('403') ||
                           error.message?.includes('not found') ||
                           error.message?.includes('permission denied');
      
      if (isAccessError) {
        notFound(); // Déclenche automatiquement app/not-found.js
        return;
      }
    }
  }, [isLoading, error]);

  // ==============================|| RENDER LOGIC ||============================== //

  // 🔥 ZÉRO RENDU tant que pas confirmé
  if (isLoading) {
    return loadingComponent || <Loader />;
  }

  // Si erreur d'accès → déclencher notFound()
  if (error) {
    const isAccessError = error.status === 404 || 
                         error.status === 403 || 
                         error.message?.includes('404') ||
                         error.message?.includes('403') ||
                         error.message?.includes('not found') ||
                         error.message?.includes('permission denied');
    
    if (isAccessError) {
      notFound(); // Déclenche app/not-found.js
      return null;
    }
    
    // Autres erreurs (réseau, etc.) → notFound() aussi
    notFound();
    return null;
  }

  // Si pas de ressource → pas d'accès
  if (!resource) {
    notFound();
    return null;
  }

  // ✅ ACCÈS CONFIRMÉ → rendre les children
  return children;
}

RequireResourceAccess.propTypes = {
  resourceId: PropTypes.string.isRequired,
  useResourceHook: PropTypes.func.isRequired,
  children: PropTypes.node.isRequired,
  loadingComponent: PropTypes.node
};