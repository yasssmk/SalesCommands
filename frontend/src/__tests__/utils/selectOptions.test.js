// frontend/src/__tests__/utils/selectOptions.test.js
// Lot 3 / 4 (TD-244) — THE empty option of an optional, clearable select.

import { describe, it, expect } from "vitest";
import { EMPTY_OPTION, withEmptyOption } from "utils/selectOptions";

describe("withEmptyOption", () => {
  it("prefixes the empty option { value: '', label: '—' }", () => {
    expect(withEmptyOption([{ value: "A", label: "A" }])).toEqual([
      { value: "", label: "—" },
      { value: "A", label: "A" },
    ]);
    expect(EMPTY_OPTION).toEqual({ value: "", label: "—" });
  });

  it("tolerates missing choices (still loading)", () => {
    expect(withEmptyOption(undefined)).toEqual([{ value: "", label: "—" }]);
    expect(withEmptyOption(null)).toEqual([{ value: "", label: "—" }]);
  });
});
