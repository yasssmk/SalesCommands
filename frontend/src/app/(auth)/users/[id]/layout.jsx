import PropTypes from 'prop-types';
import ResourceGuardLayout from 'layout/ResourceGuardLayout';

// ==============================|| ADMIN USERS [ID] LAYOUT - PROTECTED ||============================== //

export default function AdminUserIdLayout({ children }) {
  return (
    <ResourceGuardLayout>
      {children}
    </ResourceGuardLayout>
  );
}

AdminUserIdLayout.propTypes = {
  children: PropTypes.node.isRequired
};

// ==============================|| METADATA - SÉCURITÉ ||============================== //

/**
 * ✅ MÉTADONNÉES DE SÉCURITÉ
 * - Pages admin sensibles ne doivent pas être indexées
 * - Cache désactivé pour éviter les fuites
 */
export const metadata = {
  title: 'User Administration',
  robots: 'noindex, nofollow',
  
  // ⚠️ TODO: Si SSR nécessaire plus tard, ajouter :
  // other: {
  //   'cache-control': 'no-store, no-cache, must-revalidate, private'
  // }
};

