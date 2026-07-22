// frontend/src/__tests__/utils/ownerScope.realUserShape.test.js
//
// Started as the RED repro for the "owner_scope defaults to 'mine' for every
// tier" smoke bug. After the fix (the /me hand-built dict in UserCurrentView
// emits role_tier; resolveDefaultOwnerScope reads it) this pins the corrected
// behaviour against the REAL /me shape: `role` is the role NAME string and
// `role_tier` is the top-level tier. An absent/unknown role_tier resolves to
// the safe default 'mine'.

import { describe, it, expect } from "vitest";
import { resolveDefaultOwnerScope } from "utils/ownerScope";

describe("real /me shape (carries role_tier)", () => {
  const managerFromMe = {
    id: "u1",
    email: "manager@tenant.test",
    role: "Team Manager", // role NAME string
    role_name: "Team Manager",
    role_tier: "manager",
  };
  const adminFromMe = {
    id: "u2",
    role: "Admin",
    role_name: "Admin",
    role_tier: "admin",
  };
  const individualFromMe = {
    id: "u3",
    role: "Sales Rep",
    role_name: "Sales Rep",
    role_tier: "individual",
  };

  it("manager → team", () => {
    expect(resolveDefaultOwnerScope(managerFromMe)).toBe("team");
  });

  it("admin → all", () => {
    expect(resolveDefaultOwnerScope(adminFromMe)).toBe("all");
  });

  it("individual → mine", () => {
    expect(resolveDefaultOwnerScope(individualFromMe)).toBe("mine");
  });
});

describe("absent role_tier → safe default (flat flags not consulted)", () => {
  it("a payload with no role_tier resolves to mine, even with is_manager set", () => {
    expect(
      resolveDefaultOwnerScope({
        id: "u1",
        role: "Team Manager",
        role_name: "Team Manager",
        is_manager: true, // not present on the real /me dict; must not widen
      }),
    ).toBe("mine");
  });
});
