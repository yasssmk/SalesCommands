// frontend/src/app/(protected)/territories/page.jsx

import TerritoriesListPage from 'views/territories/list';

// ==============================|| TERRITORIES PAGE ||============================== //

/**
 * Next.js App Router page component for Territories
 * 
 * Located in Go-To-Market section (not Admin)
 * Protected by AuthGuard (via layout)
 */
export default function TerritoriesPage() {
  return <TerritoriesListPage />;
}

// ==============================|| METADATA ||============================== //

export const metadata = {
  title: 'Territories',
  description: 'Manage sales territories and account segments',
  robots: 'noindex, nofollow'
};