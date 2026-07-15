// frontend/src/views/home/index.jsx

'use client';

import { useUserPermissions } from 'hooks/useUserPermissions';

import RepHome from './RepHome';
import ManagerHome from './ManagerHome';

// ==============================|| HOME — role-aware entry ||============================== //

/**
 * Picks the Home experience by role: managers and admins get the
 * observer/control overview; everyone else gets the rep's action view.
 */
export default function HomePage() {
  const { isManager, isAdmin } = useUserPermissions();

  if (isManager || isAdmin) {
    return <ManagerHome />;
  }
  return <RepHome />;
}
