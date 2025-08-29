// frontend/src/app/404/page.js

import Error404 from 'views/maintenance/404';

// ==============================|| 404 EXPLICIT ROUTE ||============================== //

/**
 * ✅ ROUTE EXPLICITE /404
 * 
 * Cette page est accessible via l'URL /404 pour :
 * - Les redirections manuelles (router.push('/404'))
 * - Les liens directs vers /404
 * - Compatibilité avec les anciens systèmes
 * 
 * Note: Next.js utilisera automatiquement app/not-found.js pour les vraies 404s.
 */
export default function Explicit404Page() {
  return <Error404 />;
}

// Métadonnées
export const metadata = {
  title: '404 - Page Not Found | SalesCommands',
  description: 'The page you are looking for does not exist.',
  robots: 'noindex, nofollow' // Ne pas indexer les pages 404
};