// frontend/src/__tests__/utils/activityTypes.test.js
//
// P5 — the unified front source of truth for ACTIVITY TYPE presentation
// (the glyph), mirroring utils/signalTypes.js. One icon map + a resolver so a
// type's icon is defined ONCE and read by every activity surface.

import { describe, it, expect } from "vitest";
import {
  ACTIVITY_TYPE_ICON,
  ACTIVITY_TYPE_ICON_COLOR,
  getActivityTypeIcon,
} from "utils/activityTypes";

// The 7 canonical types (ACTIVITY_TYPES in api/accounts/activities.js).
import PhoneOutlined from "@ant-design/icons/PhoneOutlined";
import MailOutlined from "@ant-design/icons/MailOutlined";
import TeamOutlined from "@ant-design/icons/TeamOutlined";
import DesktopOutlined from "@ant-design/icons/DesktopOutlined";
import CheckSquareOutlined from "@ant-design/icons/CheckSquareOutlined";
import LinkedinOutlined from "@ant-design/icons/LinkedinOutlined";
import QuestionCircleOutlined from "@ant-design/icons/QuestionCircleOutlined";

describe("utils/activityTypes — the centralized activity-type glyphs", () => {
  it("maps the 7 canonical types to the CORRECT ant-design icons", () => {
    expect(ACTIVITY_TYPE_ICON.CALL).toBe(PhoneOutlined);
    expect(ACTIVITY_TYPE_ICON.EMAIL).toBe(MailOutlined);
    expect(ACTIVITY_TYPE_ICON.MEETING).toBe(TeamOutlined);
    // bug fix — DEMO is present (was missing / falling back in cards).
    expect(ACTIVITY_TYPE_ICON.DEMO).toBe(DesktopOutlined);
    expect(ACTIVITY_TYPE_ICON.TASK).toBe(CheckSquareOutlined);
    // bug fix — LinkedIn is the Linkedin glyph (was Mail in playlist/timeline).
    expect(ACTIVITY_TYPE_ICON.LINKEDIN).toBe(LinkedinOutlined);
    expect(ACTIVITY_TYPE_ICON.OTHER).toBe(QuestionCircleOutlined);
  });

  it("covers exactly the 7 canonical types", () => {
    expect(Object.keys(ACTIVITY_TYPE_ICON).sort()).toEqual(
      ["CALL", "DEMO", "EMAIL", "LINKEDIN", "MEETING", "OTHER", "TASK"].sort(),
    );
  });

  it("resolves a type to its icon, falling back to OTHER for unknowns", () => {
    expect(getActivityTypeIcon("DEMO")).toBe(DesktopOutlined);
    expect(getActivityTypeIcon("LINKEDIN")).toBe(LinkedinOutlined);
    expect(getActivityTypeIcon("NOPE")).toBe(QuestionCircleOutlined);
    expect(getActivityTypeIcon(undefined)).toBe(QuestionCircleOutlined);
  });

  it("exposes the uniform PRIMARY colour role for the glyph/tile (theme role, no hex)", () => {
    expect(ACTIVITY_TYPE_ICON_COLOR).toBe("primary.main");
  });
});
