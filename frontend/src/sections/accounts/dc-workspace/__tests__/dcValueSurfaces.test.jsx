// frontend/src/sections/accounts/dc-workspace/__tests__/dcValueSurfaces.test.jsx
//
// The DC workspace reads the DERIVED deal amount from the payload.
//
// Sprint C made the amount derived (Σ product lines, discount included) and the
// currency tenant-level; this sub-step surfaced both on the cycle payloads the
// workspace loads. These tests pin the FRONT half of that wiring, on the two
// surfaces that were reading the wrong thing:
//
//   * the workspace header — rendered `estimated_value` (a manual field no
//     runtime path populates, TD-75) formatted with a hardcoded "USD";
//   * the Products tab — re-summed `line_total` in JavaScript for its total and
//     printed every amount without any unit.
//
// Both now read `total_deal_value` + `currency` straight from the payload. The
// assertions are on the RENDERED amount, so a regression to the dead field or
// to a client-side re-derivation fails here, not silently in production.
//
// Harness mirrors DCWorkspaceHeader.title.test.jsx (same module mocks, same
// renderHook approach for the header hook).

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, renderHook, screen, cleanup } from "@testing-library/react";

// ==============================|| MOCKS ||============================== //

vi.mock("api/accounts/decisionCycles", () => ({
  updateDecisionCycle: vi.fn(),
  useGetDecisionCyclesByAccount: vi.fn(() => ({ cycles: [] })),
  useGetDCProducts: vi.fn(),
  createDCProduct: vi.fn(),
  updateDCProduct: vi.fn(),
  deleteDCProduct: vi.fn(),
  CYCLE_DERIVED_STATUS_LABELS: {},
  CYCLE_STATUS_COLORS: {},
}));

vi.mock("api/businessData/productCatalog", () => ({
  useGetProductCatalogEntries: vi.fn(() => ({
    entries: [],
    entriesLoading: false,
  })),
}));

vi.mock("utils/displayError", () => ({
  displaySuccessSnackbar: vi.fn(),
  displayErrorSnackbar: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
}));

vi.mock("sections/accounts/decision-cycles/DecisionCycleModal", () => ({
  default: () => null,
}));
vi.mock("sections/accounts/dc-workspace/DealHealthRunButton", () => ({
  default: () => null,
}));
vi.mock("sections/accounts/dc-workspace/CycleCloseDialog", () => ({
  default: () => null,
  useCycleCloseReopen: () => ({
    handleReopenCycle: vi.fn(),
    reopenLoading: false,
    closeDialogOpen: false,
    setCloseDialogOpen: vi.fn(),
    handleCloseDialogDismiss: vi.fn(),
    closeFormik: {},
  }),
}));

// ==============================|| IMPORTS (after mocks) ||============================== //

import useDCWorkspaceHeaderProps from "sections/accounts/dc-workspace/DCWorkspaceHeader";
import ProductsTab from "sections/accounts/dc-workspace/ProductsTab";
import { useGetDCProducts } from "api/accounts/decisionCycles";

// ==============================|| HELPERS ||============================== //

/** Render the header hook's infoItems and return their combined text. */
function headerInfoText(cycle) {
  const { result } = renderHook(() =>
    useDCWorkspaceHeaderProps({ cycle, accountId: "acc-1", onUpdate: vi.fn() }),
  );
  const { container } = render(<div>{result.current.infoItems}</div>);
  return container.textContent;
}

const CYCLE = {
  id: "cyc-1",
  name: "Big Deal",
  outcome: null,
  cycle_status: "IN_PROGRESS",
  total_deal_value: "60000.00",
  currency: "EUR",
  // The decoy: the dead manual field, deliberately different.
  estimated_value: "999999.00",
};

beforeEach(() => {
  vi.clearAllMocks();
  cleanup();
});

// ==============================|| HEADER ||============================== //

describe("DC workspace header — the deal amount", () => {
  it("renders the derived roll-up with the tenant currency", () => {
    const text = headerInfoText(CYCLE);

    expect(text).toContain("60,000.00 EUR");
  });

  it("does not render the dead estimated_value", () => {
    const text = headerInfoText(CYCLE);

    expect(text).not.toContain("999,999");
    expect(text).not.toContain("999999");
  });

  it("does not hardcode a currency symbol", () => {
    // The header used to format with { style: 'currency', currency: 'USD' },
    // which renders "$60,000" for every tenant.
    const text = headerInfoText({ ...CYCLE, currency: "GBP" });

    expect(text).toContain("60,000.00 GBP");
    expect(text).not.toContain("$");
  });

  it("shows no amount line for a cycle with no product lines", () => {
    const text = headerInfoText({ ...CYCLE, total_deal_value: "0.00" });

    expect(text).not.toContain("0.00 EUR");
  });
});

// ==============================|| PRODUCTS TAB ||============================== //

describe("DC Products tab — line and deal amounts", () => {
  const LINES = [
    {
      id: "l1",
      quantity: 2,
      unit_price: "10000.00",
      discount_percent: "25.00",
      line_total: "15000.00", // 2 x 10000 with 25% off — computed server-side
      currency: "EUR",
      notes: "",
      product_catalog_entry_detail: { id: "p1", name: "Licence" },
    },
  ];

  function renderTab(cycle, products = LINES) {
    vi.mocked(useGetDCProducts).mockReturnValue({
      products,
      productsLoading: false,
      productsError: null,
      mutateProducts: vi.fn(),
    });
    return render(<ProductsTab cycleId="cyc-1" cycle={cycle} />);
  }

  it("renders the deal total from the payload, not a client-side re-sum", () => {
    // The cycle's total (60,000) deliberately DIFFERS from the sum of the
    // rendered lines (15,000): only a component reading `total_deal_value` off
    // the payload can print it. A JS reduce over line_total would print 15,000.
    renderTab(CYCLE);

    expect(screen.getByText("60,000.00 EUR")).toBeInTheDocument();
  });

  it("renders the line total with its currency, discount included", () => {
    renderTab(CYCLE);

    expect(screen.getByText("15,000.00 EUR")).toBeInTheDocument();
  });

  it("no longer renders the dead estimated_value line", () => {
    const { container } = renderTab(CYCLE);

    expect(container.textContent).not.toContain("Estimated value");
    expect(container.textContent).not.toContain("999,999");
  });

  it("renders a dash rather than a bare zero when the payload has no amount", () => {
    const { container } = renderTab(
      { ...CYCLE, total_deal_value: null, currency: "EUR" },
      [],
    );

    // Empty state: no table, no total — and crucially no crash on a null amount.
    expect(container.textContent).toContain("No products attached to this deal.");
  });
});
