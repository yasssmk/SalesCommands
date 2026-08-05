// frontend/src/__tests__/utils/enrollmentFeedback.test.js
//
// notifyEnrollmentOutcome maps an enroll_target response (E4/E5 fields) to the
// right snackbar: green (displaySuccessSnackbar) when at least one contact was
// enrolled, orange (displayWarningSnackbar) otherwise, with one of the eight
// fixed texts. Red is never used here (that stays for result.success === false).

import { describe, it, expect, vi, afterEach } from "vitest";

vi.mock("utils/displayError", () => ({
  displaySuccessSnackbar: vi.fn(),
  displayWarningSnackbar: vi.fn(),
}));

import { notifyEnrollmentOutcome } from "utils/enrollmentFeedback";
import { displaySuccessSnackbar, displayWarningSnackbar } from "utils/displayError";

const d = (over) => ({
  contacts_enrolled: 0,
  no_channel_count: 0,
  opted_out_count: 0,
  already_active_count: 0,
  account_empty: false,
  strict: false,
  considered_total: 0,
  ...over,
});

afterEach(() => vi.clearAllMocks());

describe("notifyEnrollmentOutcome — green (enrolled > 0)", () => {
  it("all enrolled, nothing skipped -> success 'Contact(s) enrolled'", () => {
    notifyEnrollmentOutcome(d({ contacts_enrolled: 2 }));
    expect(displaySuccessSnackbar).toHaveBeenCalledWith("Contact(s) enrolled");
    expect(displayWarningSnackbar).not.toHaveBeenCalled();
  });

  it("partial, singular -> 'Enrolled. 1 contact skipped'", () => {
    notifyEnrollmentOutcome(d({ contacts_enrolled: 2, no_channel_count: 1 }));
    expect(displaySuccessSnackbar).toHaveBeenCalledWith("Enrolled. 1 contact skipped");
  });

  it("partial, plural, N = sum of causes -> 'Enrolled. 3 contacts skipped'", () => {
    notifyEnrollmentOutcome(
      d({ contacts_enrolled: 2, no_channel_count: 2, opted_out_count: 1 }),
    );
    expect(displaySuccessSnackbar).toHaveBeenCalledWith("Enrolled. 3 contacts skipped");
  });
});

describe("notifyEnrollmentOutcome — orange (enrolled == 0)", () => {
  it("account_empty -> 'No contacts'", () => {
    notifyEnrollmentOutcome(d({ account_empty: true }));
    expect(displayWarningSnackbar).toHaveBeenCalledWith("No contacts");
    expect(displaySuccessSnackbar).not.toHaveBeenCalled();
  });

  it("phantom ids (all counters 0) -> 'No contacts'", () => {
    notifyEnrollmentOutcome(d({}));
    expect(displayWarningSnackbar).toHaveBeenCalledWith("No contacts");
  });

  it(">1 cause (mixed) -> generic 'No reachable contact in this account'", () => {
    notifyEnrollmentOutcome(d({ no_channel_count: 1, opted_out_count: 1 }));
    expect(displayWarningSnackbar).toHaveBeenCalledWith(
      "No reachable contact in this account",
    );
  });

  it("single cause, strict, no_channel -> 'This contact has no email, phone or LinkedIn'", () => {
    notifyEnrollmentOutcome(d({ no_channel_count: 1, strict: true }));
    expect(displayWarningSnackbar).toHaveBeenCalledWith(
      "This contact has no email, phone or LinkedIn",
    );
  });

  it("single cause, strict, opted_out -> 'This contact has opted out'", () => {
    notifyEnrollmentOutcome(d({ opted_out_count: 1, strict: true }));
    expect(displayWarningSnackbar).toHaveBeenCalledWith("This contact has opted out");
  });

  it("single cause, not strict, no_channel -> 'No reachable contact in this account'", () => {
    notifyEnrollmentOutcome(d({ no_channel_count: 3, strict: false }));
    expect(displayWarningSnackbar).toHaveBeenCalledWith(
      "No reachable contact in this account",
    );
  });

  it("single cause, not strict, opted_out -> 'All contacts have opted out'", () => {
    notifyEnrollmentOutcome(d({ opted_out_count: 2, strict: false }));
    expect(displayWarningSnackbar).toHaveBeenCalledWith("All contacts have opted out");
  });

  it("single cause already_active -> 'Already enrolled'", () => {
    notifyEnrollmentOutcome(d({ already_active_count: 1 }));
    expect(displayWarningSnackbar).toHaveBeenCalledWith("Already enrolled");
  });
});

describe("notifyEnrollmentOutcome — unwraps nested data", () => {
  it("accepts { data: {...} } shape", () => {
    notifyEnrollmentOutcome({ data: d({ contacts_enrolled: 1 }) });
    expect(displaySuccessSnackbar).toHaveBeenCalledWith("Contact(s) enrolled");
  });
});
