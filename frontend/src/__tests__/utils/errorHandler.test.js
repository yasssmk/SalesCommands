// frontend/src/__tests__/utils/errorHandler.test.js
//
// Covers the DRF field-validation branch of handleApiError: field-level
// error dicts must keep their field name in the extracted message so the
// user sees WHICH field failed (e.g. an impact edit rejected on metric_text).

import { describe, it, expect } from "vitest";

import { handleApiError } from "utils/errorHandler";

// Build an axios-style error carrying a DRF field-validation dict.
const errorWith = (data, status = 400) => ({ response: { status, data } });

describe("handleApiError — field-level validation dicts", () => {
  it("prefixes a single field error with its field name", () => {
    const msg = handleApiError(
      errorWith({ metric_text: ["This field may not be null."] }),
    );
    expect(msg).toBe("metric_text: This field may not be null.");
  });

  it("prefixes each field when several fail", () => {
    const msg = handleApiError(
      errorWith({
        summary: ["This field is required."],
        scope_level: ["This field is required."],
      }),
    );
    expect(msg).toContain("summary: This field is required.");
    expect(msg).toContain("scope_level: This field is required.");
  });

  it("handles a bare string value (not wrapped in an array)", () => {
    const msg = handleApiError(errorWith({ metric_text: "Too long." }));
    expect(msg).toBe("metric_text: Too long.");
  });

  it("keeps non_field_errors raw (no field prefix)", () => {
    const msg = handleApiError(
      errorWith({ non_field_errors: ["Something went wrong."] }),
    );
    expect(msg).toBe("Something went wrong.");
  });

  it("still returns the message for the standard {error} shape", () => {
    const msg = handleApiError(errorWith({ error: "Plain error." }));
    expect(msg).toBe("Plain error.");
  });
});
