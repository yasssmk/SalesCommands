// frontend/src/app/(protected)/businessData/decisionCycles/page.jsx
import DecisionCyclesListPage from "views/businessData/decisionCycles/list";

// ==============================|| DECISION CYCLES PAGE ||============================== //

/**
 * Next.js App Router page component for the Decision Cycles list.
 *
 * Renders a read-only, paginated, searchable table of decision cycles.
 * Clicking a row's account opens the cycle workspace. Reads are open to all
 * authenticated users within the tenant (scoped server-side).
 *
 * Protected by AuthGuard (via layout).
 */
export default function DecisionCyclesRoute() {
  return <DecisionCyclesListPage />;
}
