// frontend/src/__tests__/components/AsyncSelection/AsyncUserSelect.excludeIds.test.jsx
//
// DUP-FIX — AsyncUserSelect gains an `excludeIds` prop (mirror of
// AsyncContactSelect): options whose id is in excludeIds are filtered out of the
// dropdown. Default [] → no filtering (existing callers unchanged).

import { render, screen, cleanup } from "@testing-library/react";
import { describe, it, expect, afterEach, vi } from "vitest";

afterEach(() => cleanup());

vi.mock("next/font/google", () => ({
  Public_Sans: () => ({ className: "mock", style: { fontFamily: "mock" } }),
}));
vi.mock("themes/emotionCache", () => ({
  NextAppDirEmotionCacheProvider: ({ children }) => children,
}));

// Stub the users data hook: two users A (id "a") and B (id "b").
vi.mock("api/admin/users", () => ({
  useGetUsers: () => ({
    users: [
      { id: "a", first_name: "A", last_name: "One" },
      { id: "b", first_name: "B", last_name: "Two" },
    ],
    usersLoading: false,
  }),
}));

import ThemeCustomization from "themes/index";
import AsyncUserSelect from "components/AsyncSelection/AsyncUserSelect";

function renderSelect(extra) {
  return render(
    <ThemeCustomization>
      <AsyncUserSelect value={null} onChange={() => {}} label="X" open {...extra} />
    </ThemeCustomization>,
  );
}

describe("AsyncUserSelect — excludeIds", () => {
  it("removes excluded ids from the options", () => {
    renderSelect({ excludeIds: ["a"] });
    expect(screen.queryByRole("option", { name: /A One/ })).not.toBeInTheDocument();
    expect(screen.getByRole("option", { name: /B Two/ })).toBeInTheDocument();
  });

  it("default (no excludeIds) keeps every option — existing callers unchanged", () => {
    renderSelect({});
    expect(screen.getByRole("option", { name: /A One/ })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: /B Two/ })).toBeInTheDocument();
  });
});
