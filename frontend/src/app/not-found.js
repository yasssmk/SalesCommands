// frontend/src/app/not-found.js

import Error404 from 'views/maintenance/404';

// ==============================|| NOT FOUND PAGE ||============================== //

/**
 * ✅ PAGE 404 NEXT.JS APP ROUTER
 * 
 * Cette page est automatiquement affichée par Next.js quand :
 * - Une route n'existe pas
 * - On appelle notFound() dans un composant
 * - RequireResourceAccess redirige vers une ressource inexistante
 * 
 * SÉCURITÉ :
 * - Pas de détail sur l'ID/ressource demandée
 * - Bouton retour vers la page d'accueil
 */
export default function NotFound() {
  return <Error404 />;
}

// Métadonnées pour le SEO
export const metadata = {
  title: '404 - Page Not Found | SalesCommands',
  description: 'The page you are looking for does not exist.'
};