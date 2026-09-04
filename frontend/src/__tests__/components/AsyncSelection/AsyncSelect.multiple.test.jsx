// frontend/src/__tests__/components/AsyncSelection/AsyncSelect.multiple.test.jsx
//
// S2c-1-fix #2 — AsyncSelect was written for a SINGLE value; its value→options
// fusion used value?.id, so in `multiple` mode (value = array) it prepended the
// whole array as one bogus option. The fusion now prepends each selected-but-
// missing item by id. Single mode (value = object|null) is unchanged.

import { render, screen, cleanup } from "@testing-library/react";
import { describe, it, expect, afterEach, vi } from "vitest";

afterEach(() => cleanup());

vi.mock("next/font/google", () => ({
  Public_Sans: () => ({ className: "mock", style: { fontFamily: "mock" } }),
}));
vi.mock("themes/emotionCache", () => ({
  NextAppDirEmotionCacheProvider: ({ children }) => children,
}));

import ThemeCustomization from "themes/index";
import AsyncSelect from "components/AsyncSelection/AsyncSelect";

// A stub data hook: two results {a,b}; the selected value {c} is NOT among them.
const useStub = () => ({ items: [{ id: "a" }, { id: "b" }], loading: false });

function renderSelect(extra) {
  return render(
    <ThemeCustomization>
      <AsyncSelect
        useDataHook={useStub}
        dataKey="items"
        loadingKey="loading"
        getOptionLabel={(o) => o?.id ?? ""}
        label="X"
        onChange={() => {}}
        open
        {...extra}
      />
    </ThemeCustomization>,
  );
}

describe("AsyncSelect — multiple value fusion", () => {
  it("multiple: the selected-but-missing item is a real option (labelled by id), not a bogus array", () => {
    renderSelect({ multiple: true, value: [{ id: "c" }] });
    // "c" (selected, not in results) is offered as a proper option
    expect(screen.getByRole("option", { name: "c" })).toBeInTheDocument();
    // the search results are still there
    expect(screen.getByRole("option", { name: "a" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "b" })).toBeInTheDocument();
  });

  it("single: value object still gets prepended as before (no regression)", () => {
    renderSelect({ value: { id: "c" } });
    expect(screen.getByRole("option", { name: "c" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "a" })).toBeInTheDocument();
  });
});
