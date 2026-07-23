// frontend/src/__tests__/components/table/Table.toolbarActions.test.jsx
//
// ReusableTable exposes an optional `toolbarActions` slot so a caller can place
// an extra control (e.g. the Target tab's status toggle) inside the table
// toolbar, left of the Add button — instead of floating it in a separate row.
//
// The assertion that matters is NON-REGRESSION: the prop is opt-in
// (PropTypes.node, default null), so a table that omits it renders exactly as
// before. This protects the 13 other ReusableTable callers, which pass nothing.
//
// Real render of ReusableTable. next/navigation + useAuth are globally mocked
// (vitest.setup.js); next/font is stubbed per project convention; the project
// theme is assembled so MainCard / @extended/IconButton resolve their tokens.

import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import { ThemeProvider, createTheme } from "@mui/material/styles";

import Palette from "themes/palette";
import CustomShadows from "themes/shadows";
import componentsOverride from "themes/overrides";

// next/font is not executable outside a Next build — stub it (project convention).
vi.mock("next/font/google", () => ({
  Public_Sans: () => ({ className: "mock-public-sans", style: { fontFamily: "mock" } }),
}));

import ReusableTable from "components/table/Table";

afterEach(cleanup);

const base = Palette("light", "default");
const theme = createTheme({
  palette: base.palette,
  customShadows: CustomShadows(base),
});
theme.components = componentsOverride(theme);

const COLUMNS = [{ header: "Name", accessorKey: "name" }];
const DATA = [{ id: "1", name: "Alpha" }];

function renderTable(extraProps = {}) {
  return render(
    <ThemeProvider theme={theme}>
      <ReusableTable
        data={DATA}
        columns={COLUMNS}
        searchPlaceholder="Search records..."
        addButtonLabel="Add item"
        modalToggler={() => {}}
        {...extraProps}
      />
    </ThemeProvider>,
  );
}

describe("ReusableTable — toolbarActions slot", () => {
  it("renders the provided control in the toolbar, left of the Add button", () => {
    renderTable({
      toolbarActions: <button data-testid="slot-control">Toggle</button>,
    });

    const slot = screen.getByTestId("slot-control");
    expect(slot).toBeInTheDocument();

    // The slot sits before the Add button in document order (start of the
    // action cluster).
    const addBtn = screen.getByRole("button", { name: /Add item/ });
    expect(
      slot.compareDocumentPosition(addBtn) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
  });

  it("injects nothing when the prop is omitted, leaving the toolbar unchanged", () => {
    renderTable(); // no toolbarActions — the default for all other callers

    // Nothing from the slot is rendered.
    expect(screen.queryByTestId("slot-control")).toBeNull();

    // The standard toolbar controls are all still present and unchanged.
    expect(
      screen.getByPlaceholderText("Search records..."),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /Add item/ }),
    ).toBeInTheDocument();
  });
});
