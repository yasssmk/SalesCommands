'use client';
import PropTypes from 'prop-types';
import { useEffect } from 'react';
import { useRouter } from 'next/navigation';

// project-import
import Loader from 'components/Loader';
import { useAuth } from 'hooks/useAuth';

// ==============================|| AUTH GUARD ||============================== //

export default function AuthGuard({ children }) {
  const router = useRouter();
  const { isAuthenticated, isLoading } = useAuth();

  useEffect(() => {
    // Redirection si pas authentifié
    if (!isLoading && !isAuthenticated) {
      router.push('/login');
    }
  }, [isAuthenticated, isLoading, router]);

  // Affichage du loader pendant la vérification
  if (isLoading) {
    return <Loader />;
  }

  // Si pas authentifié, ne rien afficher (redirection en cours)
  if (!isAuthenticated) {
    return null;
  }

  // Si authentifié, afficher le contenu
  return children;
}

AuthGuard.propTypes = { 
  children: PropTypes.any 
};