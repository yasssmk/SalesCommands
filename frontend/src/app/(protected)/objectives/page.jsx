// frontend/src/app/(protected)/objectives/page.jsx

import ObjectivesListPage from 'views/objectives/list';

// ==============================|| MY OBJECTIVES PAGE ||============================== //

/**
 * Next.js App Router page for the current user's personal objectives.
 * Protected by AuthGuard (via the (protected) layout).
 */
export default function ObjectivesPage() {
  return <ObjectivesListPage />;
}

export const metadata = {
  title: 'My Objectives',
  description: 'Set and track your personal sales objectives',
  robots: 'noindex, nofollow',
};
