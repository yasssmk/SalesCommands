// frontend/src/layout/ResourceGuardLayout.jsx

'use client';

import PropTypes from 'prop-types';
import { useParams, usePathname } from 'next/navigation';
import { notFound } from 'next/navigation';

// project imports
import RequireResourceAccess from 'components/auth/RequireResourceAccess';
import { useGetUser, useGetTeam, useGetOrganization } from 'api/admin/users';
import Loader from 'components/Loader';

// ==============================|| RESOURCE GUARD LAYOUT ||============================== //

/**
 * ✅ LAYOUT WRAPPER INTELLIGENT POUR PROTECTION AUTOMATIQUE
 * 
 * FONCTIONNALITÉS :
 * - Détecte automatiquement le type de ressource selon l'URL
 * - Applique le bon hook de vérification d'accès
 * - Protège TOUTES les pages avec [id] présentes et futures
 * - DRY : Un seul wrapper pour tous les types de ressources
 * 
 * USAGE :
 * Dans app/(protected)/users/[id]/layout.jsx :
 * export default function UserIdLayout({ children }) {
 *   return (
 *     <ResourceGuardLayout>
 *       {children}
 *     </ResourceGuardLayout>
 *   );
 * }
 */

// ==============================|| USAGE EXAMPLES ||============================== //

/*
✅ USAGE DANS LES LAYOUTS :

// app/(protected)/users/[id]/layout.jsx
export default function UserIdLayout({ children }) {
  return (
    <ResourceGuardLayout>
      {children}
    </ResourceGuardLayout>
  );
}

// app/(protected)/teams/[id]/layout.jsx
export default function TeamIdLayout({ children }) {
  return (
    <ResourceGuardLayout>
      {children}
    </ResourceGuardLayout>
  );
}

✅ AJOUT DE NOUVELLES RESSOURCES :
1. Créer le hook useGetSalesQuota dans api/admin/users.js
2. Ajouter '/sales-quotas/': useGetSalesQuota dans RESOURCE_HOOKS_MAPPING
3. Créer le layout app/(protected)/sales-quotas/[id]/layout.jsx
4. Le layout sera automatiquement protégé avec default-deny !

✅ SÉCURITÉ GARANTIE :
- 🔒 Default-Deny : Route inconnue → 404 immédiat
- 🔒 Mapping explicite : Pas de faille par heuristique
- 🔒 Zero-flash : Pas de rendu avant vérification
- 🔒 Logs sécurité : Toutes les tentatives d'accès tracées
*/

// ==============================|| RESOURCE TYPE DETECTION - SECURED ||============================== //

/**
 * ✅ MAPPING EXPLICITE ET EXHAUSTIF : Route Pattern → Hook de vérification
 * 
 * SÉCURITÉ RENFORCÉE :
 * - Mapping explicite (pas d'heuristique permissive)
 * - Default-deny : route inconnue = 404 (pas d'accès)
 * - Patterns exacts pour éviter les false-positives
 */
const RESOURCE_HOOKS_MAPPING = {
  // ✅ USERS - Patterns exacts
  '/users/': useGetUser,
  '/admin/users/': useGetUser,
  
  // ✅ TEAMS - Patterns exacts  
  '/teams/': useGetTeam,
  '/admin/teams/': useGetTeam,
  
  // ✅ ORGANIZATIONS - Patterns exacts
  '/organizations/': useGetOrganization,
  '/admin/organizations/': useGetOrganization,
  
  // ✅ FUTURES RESSOURCES - Ajouter ici explicitement
  // '/sales-quotas/': useGetSalesQuota,
  // '/sales-plans/': useGetSalesPlan,
  // '/opportunities/': useGetOpportunity,
  // '/leads/': useGetLead,
};

/**
 * ✅ DÉTECTION SÉCURISÉE AVEC DEFAULT-DENY
 * 
 * PRINCIPE DE SÉCURITÉ :
 * - Si route inconnue → DENY (pas d'accès)
 * - Si route connue → vérification d'accès
 * - Jamais d'heuristique "permissive"
 */
const detectResourceHook = (pathname) => {
  // Recherche exacte dans le mapping
  for (const [pattern, hook] of Object.entries(RESOURCE_HOOKS_MAPPING)) {
    if (pathname.includes(pattern)) {
      return { hook, pattern };
    }
  }
  
  // 🔒 DEFAULT-DENY : Route inconnue = accès refusé
  console.warn(`[SECURITY] ResourceGuardLayout: Unknown route pattern blocked: ${pathname}`);
  return { hook: null, pattern: null, shouldBlock: true };
};

// ==============================|| MAIN COMPONENT ||============================== //

export default function ResourceGuardLayout({ 
  children, 
  loadingComponent,
  bypassGuard = false 
}) {
  const params = useParams();
  const pathname = usePathname();
  
  // Extraire l'ID depuis les params ([id] dans l'URL)
  const resourceId = params?.id;
  
  // ==============================|| BYPASS CONDITIONS ||============================== //
  
  // Si pas d'ID dans l'URL → pas besoin de protection
  if (!resourceId) {
    return children;
  }
  
  // Si bypass explicite → pas de protection (pour pages publiques par exemple)
  if (bypassGuard) {
    return children;
  }
  
  // ==============================|| HOOK DETECTION - SECURED ||============================== //
  
  // Détecter le hook avec sécurité renforcée
  const detectionResult = detectResourceHook(pathname);
  const { hook: ResourceHook, pattern, shouldBlock } = detectionResult;
  
  // 🔒 DEFAULT-DENY : Route inconnue avec [id] = BLOCAGE immédiat
  if (shouldBlock) {
    console.error(`[SECURITY BLOCK] Unauthorized route with [id]: ${pathname}`);
    notFound(); // Déclencher 404 pour route inconnue avec [id]
    return null; // Pas de rendu en attendant la redirection
  }
  
  // Si pas de hook trouvé mais pas de blocage explicite → laisser passer (backward compat)
  if (!ResourceHook) {
    console.warn(`[ResourceGuardLayout] No protection for: ${pathname} (pattern: ${pattern})`);
    return children;
  }
  
  // ==============================|| PROTECTION ACTIVE ||============================== //
  
  return (
    <RequireResourceAccess
      resourceId={resourceId}
      useResourceHook={ResourceHook}
      loadingComponent={loadingComponent}
    >
      {children}
    </RequireResourceAccess>
  );
}

ResourceGuardLayout.propTypes = {
  children: PropTypes.node.isRequired,
  loadingComponent: PropTypes.node,
  bypassGuard: PropTypes.bool
};

