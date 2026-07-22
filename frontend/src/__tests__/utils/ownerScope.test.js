// frontend/src/__tests__/utils/ownerScope.test.js
//
// Pure resolver: user tier → default owner_scope. Uses the REAL /me shape — the
// current-user payload is a hand-built dict (UserCurrentView) where `role` is
// the role NAME string and the tier is the top-level `role_tier`. (NOT the
// fabricated `{ role: { is_manager: true } }` shape, which masked the original
// bug.) An unknown/absent tier resolves to the safe default 'mine'.

import { describe, it, expect } from "vitest";
import { resolveDefaultOwnerScope, OWNER_SCOPES } from "utils/ownerScope";

const me = (over = {}) => ({
  id: "u1",
  email: "u@tenant.test",
  role: "Sales Rep", // role NAME string, as the /me dict emits
  role_name: "Sales Rep",
  ...over,
});

describe("resolveDefaultOwnerScope — role_tier (real /me shape)", () => {
  it("role_tier 'admin' → all", () => {
    expect(resolveDefaultOwnerScope(me({ role_tier: "admin" }))).toBe("all");
  });

  it("role_tier 'manager' → team", () => {
    expect(resolveDefaultOwnerScope(me({ role_tier: "manager" }))).toBe("team");
  });

  it("role_tier 'individual' → mine", () => {
    expect(resolveDefaultOwnerScope(me({ role_tier: "individual" }))).toBe("mine");
  });

  it("non-superuser admin → all (role_tier is the sole signal)", () => {
    // The front has no is_admin flag; only role_tier can surface an admin tier.
    expect(
      resolveDefaultOwnerScope(me({ role_tier: "admin", is_superuser: false })),
    ).toBe("all");
  });
});

describe("resolveDefaultOwnerScope — unknown/absent tier → safe default 'mine'", () => {
  it("no role_tier → mine (flat is_manager/is_superuser are NOT consulted)", () => {
    // These flags aren't even present on the /me dict; role_tier is the only
    // signal, so their absence must not widen the default.
    expect(resolveDefaultOwnerScope(me({ is_manager: true }))).toBe("mine");
    expect(resolveDefaultOwnerScope(me({ is_superuser: true }))).toBe("mine");
    expect(resolveDefaultOwnerScope(me())).toBe("mine");
  });

  it("unrecognised role_tier value → mine", () => {
    expect(resolveDefaultOwnerScope(me({ role_tier: "wat" }))).toBe("mine");
  });

  it("null / undefined user → mine", () => {
    expect(resolveDefaultOwnerScope(null)).toBe("mine");
    expect(resolveDefaultOwnerScope(undefined)).toBe("mine");
  });
});

describe("resolveDefaultOwnerScope — constant", () => {
  it("exposes the shared OWNER_SCOPES", () => {
    expect(OWNER_SCOPES).toEqual({ MINE: "mine", TEAM: "team", ALL: "all" });
  });
});
