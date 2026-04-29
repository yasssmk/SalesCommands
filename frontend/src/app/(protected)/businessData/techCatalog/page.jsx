// src/app/(protected)/admin/techCatalog/page.jsx
import TechCatalogListPage from 'views/businessData/techCatalog/list';

// ==============================|| TECH CATALOG ADMIN PAGE ||============================== //

/**
 * Next.js App Router page component for the TechCatalog admin list.
 *
 * Renders a paginated, searchable table of TechCatalog entries with
 * Add / Edit / Delete actions. Admin-only writes (enforced server-side
 * by ScopedPermission); reads are open to all authenticated users.
 *
 * Protected by AuthGuard (via layout).
 */
export default function TechCatalogRoute() {
  return <TechCatalogListPage />;
}