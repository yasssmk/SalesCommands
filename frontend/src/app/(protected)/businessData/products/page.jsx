// frontend/src/app/(protected)/businessData/products/page.jsx
import ProductCatalogListPage from "views/businessData/products/list";

// ==============================|| PRODUCTS ADMIN PAGE ||============================== //

/**
 * Next.js App Router page component for the Product catalog list.
 *
 * Renders a paginated, searchable table of ProductCatalog entries.
 * Add / Edit / Delete are admin-only, gated in the view and enforced
 * server-side by ScopedPermission; reads are open to all authenticated
 * users.
 *
 * Protected by AuthGuard (via layout).
 */
export default function ProductsRoute() {
  return <ProductCatalogListPage />;
}
