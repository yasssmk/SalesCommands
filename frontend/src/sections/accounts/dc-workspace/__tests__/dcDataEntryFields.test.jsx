// frontend/src/sections/accounts/dc-workspace/__tests__/dcDataEntryFields.test.jsx
//
// Two backend fields the UI never let a rep touch or read.
//
// FIELD 1 — DISCOUNT. `DealProduct.discount_percent` is a real column with a DB
// CheckConstraint (deal_product_discount_percent_bounds), a serializer validator
// (decision_cycles/serializers.py:1480) and a place in the line-total formula
// (services/deal_value_sql.py:90). The product-line dialog had no input for it,
// so every line was created at 0% and no rep could ever discount a deal from the
// workspace. The table had no column for it either: a discounted line's total
// simply did not equal Qty x Unit Price, with nothing on screen to explain the
// gap.
//
// FIELD 2 — CLOSE DATE. The workspace header derived its "Est. close" chip from
// `created_at + estimated_timeline_days`. That is a DURATION estimate, not a
// close date, and the two are unrelated numbers: editing `expected_close_date`
// in the DC modal moved the backend's `effective_close_date` and left this chip
// showing the same stale derived day. The header now reads
// `effective_close_date` — the backend's single rule
// (decision_cycles/services/close_date_sql.py:116: the manual date, else the
// last dated CLOSING-step activity, else null).
//
// `estimated_timeline_days` is deliberately NOT removed — it is still served
// (serializers.py:394) and kept for a future "days remaining" surface. It is
// only no longer the source of the close date, which the regression tests below
// pin by feeding a cycle that has one and asserting the derived date is absent.
//
// Harness mirrors dcValueSurfaces.test.jsx in this folder — same module mocks,
// same renderHook-then-render approach for the header hook.

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, renderHook, screen, cleanup, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

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
import {
  useGetDCProducts,
  updateDCProduct,
} from "api/accounts/decisionCycles";

// ==============================|| HELPERS ||============================== //

const CYCLE = {
  id: "cyc-1",
  name: "Big Deal",
  outcome: null,
  cycle_status: "IN_PROGRESS",
  total_deal_value: "54000.00",
  currency: "EUR",
};

/** A line discounted 10%: 6 x 10,000 - 10% = 54,000. */
const DISCOUNTED_LINE = {
  id: "l1",
  quantity: 6,
  unit_price: "10000.00",
  discount_percent: "10.00",
  line_total: "54000.00",
  currency: "EUR",
  notes: "",
  product_catalog_entry_detail: { id: "p1", name: "Licence" },
};

function renderTab(products = [DISCOUNTED_LINE], cycle = CYCLE) {
  vi.mocked(useGetDCProducts).mockReturnValue({
    products,
    productsLoading: false,
    productsError: null,
    mutateProducts: vi.fn(),
  });
  return render(<ProductsTab cycleId="cyc-1" cycle={cycle} />);
}

/** Open the EDIT dialog on the first line. Edit mode needs no catalog pick — the
 *  dialog's own submit guard is `editMode || selectedProduct`. */
async function openEditDialog(user) {
  await user.click(screen.getByRole("button", { name: /edit/i }));
  return screen.getByRole("dialog");
}

/** The text of the first line's Discount cell, found by the column's own header
 *  position rather than a fixed index — so this keeps pointing at the right cell
 *  if the table gains a column. */
function discountCellText() {
  const headers = screen.getAllByRole("columnheader").map((h) => h.textContent);
  const column = headers.indexOf("Discount");
  const row = screen.getAllByRole("row")[1];
  return within(row).getAllByRole("cell")[column].textContent;
}

/** Render the header hook's infoItems and return their combined text. */
function headerInfoText(cycle) {
  const { result } = renderHook(() =>
    useDCWorkspaceHeaderProps({ cycle, accountId: "acc-1", onUpdate: vi.fn() }),
  );
  const { container } = render(<div>{result.current.infoItems}</div>);
  return container.textContent;
}

beforeEach(() => {
  vi.clearAllMocks();
  cleanup();
});

// ==============================|| FIELD 1 — THE DISCOUNT INPUT ||============================== //

describe("product line dialog — discount input", () => {
  it("offers a Discount % field", async () => {
    const user = userEvent.setup();
    renderTab();
    const dialog = await openEditDialog(user);

    expect(within(dialog).getByLabelText(/discount %/i)).toBeInTheDocument();
  });

  it("prefills the line's current discount when editing", async () => {
    const user = userEvent.setup();
    renderTab();
    const dialog = await openEditDialog(user);

    // Without this the dialog would silently reset a discounted line to blank,
    // and saving any other field would wipe the discount.
    expect(within(dialog).getByLabelText(/discount %/i)).toHaveValue(10);
  });

  it("sends the typed discount as discount_percent", async () => {
    const user = userEvent.setup();
    vi.mocked(updateDCProduct).mockResolvedValue({ success: true });
    renderTab();
    const dialog = await openEditDialog(user);

    const input = within(dialog).getByLabelText(/discount %/i);
    await user.clear(input);
    await user.type(input, "25");
    await user.click(within(dialog).getByRole("button", { name: "Save" }));

    expect(updateDCProduct).toHaveBeenCalledWith(
      "cyc-1",
      "l1",
      expect.objectContaining({ discount_percent: "25" }),
    );
  });

  it("sends 0 — not null — when the discount is cleared", async () => {
    // The column is NOT NULL with a 0 default, and the serializer rejects null.
    // Clearing the box has to mean "no discount", which is 0, or a rep could
    // never take a discount back off a line.
    const user = userEvent.setup();
    vi.mocked(updateDCProduct).mockResolvedValue({ success: true });
    renderTab();
    const dialog = await openEditDialog(user);

    await user.clear(within(dialog).getByLabelText(/discount %/i));
    await user.click(within(dialog).getByRole("button", { name: "Save" }));

    expect(updateDCProduct).toHaveBeenCalledWith(
      "cyc-1",
      "l1",
      expect.objectContaining({ discount_percent: 0 }),
    );
  });

  it.each([["150"], ["-5"]])(
    "blocks submission of an out-of-range %s and says why",
    async (bad) => {
      // inputProps.max only constrains the spinner; a pasted or typed 150 still
      // reaches state. The backend would 400 — this turns that into an inline
      // message instead of a failed save.
      const user = userEvent.setup();
      renderTab();
      const dialog = await openEditDialog(user);

      const input = within(dialog).getByLabelText(/discount %/i);
      await user.clear(input);
      await user.type(input, bad);

      expect(within(dialog).getByRole("button", { name: "Save" })).toBeDisabled();
      expect(
        within(dialog).getByText(/between 0 and 100/i),
      ).toBeInTheDocument();
      expect(updateDCProduct).not.toHaveBeenCalled();
    },
  );

  it("accepts the boundary values 0 and 100", async () => {
    const user = userEvent.setup();
    vi.mocked(updateDCProduct).mockResolvedValue({ success: true });
    renderTab();
    const dialog = await openEditDialog(user);

    const input = within(dialog).getByLabelText(/discount %/i);
    await user.clear(input);
    await user.type(input, "100");

    // 100 is a legal full discount server-side; the guard must not be
    // off-by-one and reject it.
    expect(within(dialog).getByRole("button", { name: "Save" })).toBeEnabled();
  });

  it("leaves the other fields it must not disturb intact", async () => {
    // Anti-over-correction: adding a field must not drop the ones that worked.
    const user = userEvent.setup();
    vi.mocked(updateDCProduct).mockResolvedValue({ success: true });
    renderTab();
    const dialog = await openEditDialog(user);

    await user.click(within(dialog).getByRole("button", { name: "Save" }));

    expect(updateDCProduct).toHaveBeenCalledWith(
      "cyc-1",
      "l1",
      expect.objectContaining({ quantity: 6, unit_price: "10000.00" }),
    );
  });
});

// ==============================|| FIELD 1 — THE DISCOUNT COLUMN ||============================== //

describe("product line table — discount column", () => {
  it("has a Discount column", () => {
    renderTab();

    expect(
      screen.getByRole("columnheader", { name: "Discount" }),
    ).toBeInTheDocument();
  });

  it("renders it between Unit Price and Line Total", () => {
    // Position is the point: the column exists to explain the gap between
    // Qty x Unit Price and the line total, which only reads if it sits between
    // them.
    renderTab();

    const headers = screen
      .getAllByRole("columnheader")
      .map((h) => h.textContent);

    expect(headers.indexOf("Discount")).toBe(headers.indexOf("Unit Price") + 1);
    expect(headers.indexOf("Line Total")).toBe(headers.indexOf("Discount") + 1);
  });

  it("shows the line's discount as a percentage", () => {
    renderTab();

    // "10.00" from a DRF DecimalField must read as 10%, not "10.00%".
    expect(screen.getByText("10%")).toBeInTheDocument();
  });

  it("shows a dash, not 0%, on an undiscounted line", () => {
    renderTab([{ ...DISCOUNTED_LINE, discount_percent: "0.00" }]);

    expect(screen.queryByText("0%")).not.toBeInTheDocument();
    // Scoped to the Discount cell by column position — the Notes cell renders
    // its own dash for an empty note.
    expect(discountCellText()).toBe("—");
  });

  it("makes the discounted total explainable on screen", () => {
    // The whole point of the column, in one assertion: 6 x 10,000 with 10% off
    // is 54,000, and all three numbers are now visible together.
    const { container } = renderTab();

    expect(container.textContent).toContain("6");
    expect(container.textContent).toContain("10,000.00 EUR");
    expect(container.textContent).toContain("10%");
    expect(container.textContent).toContain("54,000.00 EUR");
  });
});

// ==============================|| FIELD 2 — THE CLOSE-DATE CHIP ||============================== //

describe("workspace header — close date", () => {
  const OPEN_CYCLE = {
    id: "cyc-1",
    name: "Big Deal",
    outcome: null,
    cycle_status: "IN_PROGRESS",
    created_at: "2026-01-01T00:00:00Z",
    // The decoy. created_at + 90d = Apr 1, 2026 — the date the chip used to
    // show. It must appear nowhere below.
    estimated_timeline_days: 90,
  };

  it("shows the effective close date", () => {
    const text = headerInfoText({
      ...OPEN_CYCLE,
      effective_close_date: "2026-06-15",
    });

    expect(text).toContain("Est. close Jun 15, 2026");
  });

  it("does not derive the date from estimated_timeline_days", () => {
    // THE regression. Both fields present, deliberately disagreeing: only a
    // header reading effective_close_date can print June rather than April.
    const text = headerInfoText({
      ...OPEN_CYCLE,
      effective_close_date: "2026-06-15",
    });

    expect(text).not.toContain("Apr 1, 2026");
  });

  it("shows a neutral empty state when there is no close date", () => {
    const text = headerInfoText({ ...OPEN_CYCLE, effective_close_date: null });

    expect(text).toContain("No close date");
    // Not the legacy computed date, and not some other date standing in for one.
    expect(text).not.toContain("Apr 1, 2026");
    expect(text).not.toContain("Jan 1, 2026");
  });

  it("reads the date as a local calendar day, not UTC midnight", () => {
    // A DateField arrives as "YYYY-MM-DD". `new Date` reads that as UTC
    // midnight, which formats as the day BEFORE anywhere west of Greenwich —
    // a close date that silently shifts by one day depending on the viewer.
    const text = headerInfoText({
      ...OPEN_CYCLE,
      effective_close_date: "2026-03-01",
    });

    expect(text).toContain("Mar 1, 2026");
    expect(text).not.toContain("Feb 28, 2026");
  });

  it("still prefers the actual outcome date once the cycle is closed", () => {
    // Anti-over-correction: a settled cycle shows what happened, not a forecast.
    const text = headerInfoText({
      ...OPEN_CYCLE,
      outcome: "WON",
      outcome_date: "2026-05-20",
      effective_close_date: "2026-06-15",
    });

    expect(text).toContain("Closed May 20, 2026");
    expect(text).not.toContain("Est. close");
  });
});
