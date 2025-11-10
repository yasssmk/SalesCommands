import RolesListApp from 'views/admin/roles/list';

// ==============================|| ROLES & PERMISSIONS PAGE ||============================== //

/**
 * Next.js App Router page component for Roles & Permissions
 * 
 * This page is protected by AuthGuard (via layout)
 * Imports the actual component from views/admin/roles/list.jsx
 */
export default function AdminRolesPage() {
  return <RolesListApp />;
}

// ==============================|| METADATA ||============================== //

/**
 * Page metadata for SEO and security
 */
export const metadata = {
  title: 'Roles & Permissions',
  description: 'Manage user roles and permissions',
  robots: 'noindex, nofollow' // Admin pages should not be indexed
};