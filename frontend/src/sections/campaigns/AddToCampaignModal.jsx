// frontend/src/sections/campaigns/AddToCampaignModal.jsx
/**
 * AddToCampaignModal — Enroll an account into the user's Targeted Campaign.
 *
 * 2 enrollment modes (ACCOUNT/whole-account removed — backend rejects it):
 *   - DEPARTMENT: all contacts of a specific department (resolved client-side
 *     to CONTACT ids on submit — a client filter, not a backend mode)
 *   - CONTACT: one or more specific contacts
 * An optional per-enroll Activity Objective is posted as `objective`.
 *
 * Data flow:
 *   1. useGetTargetedCampaign() — get/create the singleton
 *   2. useGetContacts(accountId) — load contacts, derive departments in-memory
 *   3. enrollTarget() — POST to bulk-add + toggle-contact
 *
 * Reusable from:
 *   - AccountHeader (account level)
 *   - AccountContactsTab (contact row)
 */

"use client";

import PropTypes from "prop-types";
import { useState, useMemo, useCallback, useEffect } from "react";

// material-ui
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Chip from "@mui/material/Chip";
import CircularProgress from "@mui/material/CircularProgress";
import Divider from "@mui/material/Divider";
import FormControlLabel from "@mui/material/FormControlLabel";
import List from "@mui/material/List";
import ListItem from "@mui/material/ListItem";
import ListItemButton from "@mui/material/ListItemButton";
import ListItemText from "@mui/material/ListItemText";
import Modal from "@mui/material/Modal";
import Radio from "@mui/material/Radio";
import RadioGroup from "@mui/material/RadioGroup";
import Skeleton from "@mui/material/Skeleton";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";
import Checkbox from "@mui/material/Checkbox";
import TextField from "@mui/material/TextField";

// project imports
import MainCard from "components/MainCard";

// api
import {
  useGetTargetedCampaign,
  enrollTarget,
  useGetCampaignContacts,
} from "api/campaigns/campaigns";
import { useGetContacts } from "api/businessData/contacts";
import { useGetDecisionCyclesByAccount } from "api/accounts/decisionCycles";

// utils
import { displayErrorSnackbar } from "utils/displayError";
import { notifyEnrollmentOutcome } from "utils/enrollmentFeedback";

// icons
import AimOutlined from "@ant-design/icons/AimOutlined";

// ==============================|| CONSTANTS ||============================== //

const MODES = {
  // ACCOUNT (whole-account) enroll mode removed — backend rejects it (S13
  // sub-step 4). Enrollment is contact-by-contact; DEPARTMENT stays a
  // client-side filter that resolves to CONTACT ids on submit.
  DEPARTMENT: "DEPARTMENT",
  CONTACT: "CONTACT",
};

const STEPS = {
  TARGET: "TARGET",
  ORIGIN: "ORIGIN",
};

// ==============================|| ADD TO CAMPAIGN MODAL ||============================== //

export default function AddToCampaignModal({
  open,
  onClose,
  onSuccess = null,
  accountId,
  accountName,
  preselectedContactId = null,
}) {
  // ==============================|| DATA ||============================== //

  const { targetedCampaign, targetedLoading } = useGetTargetedCampaign();

  // Load all contacts for this account (up to 200, enough for any account)
  const { contacts, contactsLoading } = useGetContacts({
    page: 1,
    pageSize: 200,
    filters: { account_id: accountId },
  });

  // Load existing campaign contacts to detect enrollment state
  const { campaignContacts } = useGetCampaignContacts(
    open ? targetedCampaign?.id : null,
  );

  // Contacts currently active in the campaign (block re-selection with warning)
  const activeContactIds = useMemo(() => {
    const ACTIVE = ["IN_PROGRESS", "PENDING", "ON_HOLD", "CALLBACK_PENDING"];
    return new Set(
      campaignContacts
        .filter((cc) => ACTIVE.includes(cc.status))
        .map((cc) => cc.contact?.id || cc.contact)
        .filter(Boolean),
    );
  }, [campaignContacts]);

  // Contacts in final state — will be reactivated by the backend
  const reactivatableContactIds = useMemo(() => {
    const FINAL = ["COMPLETED", "STOPPED"];
    return new Set(
      campaignContacts
        .filter((cc) => FINAL.includes(cc.status))
        .map((cc) => cc.contact?.id || cc.contact)
        .filter(Boolean),
    );
  }, [campaignContacts]);

  // ==============================|| STATE ||============================== //

  // Default to CONTACT (ACCOUNT mode removed). DEPARTMENT is opt-in via the radio.
  const initialMode = MODES.CONTACT;
  const [wizardStep, setWizardStep] = useState(STEPS.TARGET);
  const [mode, setMode] = useState(initialMode);
  const [selectedDepartment, setSelectedDepartment] = useState(null);
  const [selectedContactIds, setSelectedContactIds] = useState(
    preselectedContactId ? [preselectedContactId] : [],
  );
  const [submitting, setSubmitting] = useState(false);
  const [notes, setNotes] = useState("");
  const [objective, setObjective] = useState("");
  const [originDecisionCycleId, setOriginDecisionCycleId] = useState(null);
  // "No calls" per-enrollment override (Voie B): checked -> channel_override
  // NO_CALLS is posted for every contact enrolled by this action; unchecked ->
  // no key sent, the contacts follow the campaign.
  const [noCalls, setNoCalls] = useState(false);

  const { cycles: accountCycles, cyclesLoading } =
    useGetDecisionCyclesByAccount(open ? accountId : null);

  // Only show open cycles (no terminal outcome)
  const openCycles = accountCycles.filter((c) => !c.outcome);

  useEffect(() => {
    if (open) {
      setWizardStep(STEPS.TARGET);
      setMode(MODES.CONTACT);
      setSelectedDepartment(null);
      setSelectedContactIds(preselectedContactId ? [preselectedContactId] : []);
      setNotes("");
      setObjective("");
      setOriginDecisionCycleId(null);
      setNoCalls(false);
    }
  }, [open, preselectedContactId]);

  // ==============================|| DERIVED DATA ||============================== //

  // Group contacts by department in-memory
  const departments = useMemo(() => {
    const map = {};
    contacts.forEach((c) => {
      const deptName = c.department_name || "No Department";
      if (!map[deptName]) map[deptName] = [];
      map[deptName].push(c);
    });
    return Object.entries(map).map(([name, deptContacts]) => ({
      name,
      contacts: deptContacts,
      count: deptContacts.length,
    }));
  }, [contacts]);

  // ==============================|| HANDLERS ||============================== //

  const handleModeChange = useCallback((e) => {
    setMode(e.target.value);
    setSelectedDepartment(null);
    setSelectedContactIds([]);
  }, []);

  const handleContactToggle = useCallback((contactId) => {
    setSelectedContactIds((prev) =>
      prev.includes(contactId)
        ? prev.filter((id) => id !== contactId)
        : [...prev, contactId],
    );
  }, []);

  const handleSubmit = useCallback(async () => {
    if (!targetedCampaign?.id || !accountId) return;

    setSubmitting(true);
    try {
      let payload;

      if (mode === MODES.DEPARTMENT && selectedDepartment) {
        const deptContacts =
          departments.find((d) => d.name === selectedDepartment)?.contacts ||
          [];
        payload = {
          type: "CONTACT",
          account_id: accountId,
          contact_ids: deptContacts.map((c) => c.id),
        };
      } else if (mode === MODES.CONTACT && selectedContactIds.length > 0) {
        payload = {
          type: "CONTACT",
          account_id: accountId,
          contact_ids: selectedContactIds,
        };
      } else {
        displayErrorSnackbar({
          message: "Please make a selection",
          status: 400,
        });
        setSubmitting(false);
        return;
      }

      if (notes.trim()) payload.notes = notes.trim();
      if (objective.trim()) payload.objective = objective.trim();
      if (originDecisionCycleId)
        payload.origin_decision_cycle_id = originDecisionCycleId;
      if (noCalls) payload.channel_override = "NO_CALLS";

      const result = await enrollTarget(targetedCampaign.id, payload);

      if (result.success) {
        // Tone (green/orange) and text come from the cause counters in the
        // response — see utils/enrollmentFeedback.
        notifyEnrollmentOutcome(result.data);
        onSuccess?.();
        onClose();
      } else {
        displayErrorSnackbar(result);
      }
    } finally {
      setSubmitting(false);
    }
  }, [
    targetedCampaign,
    accountId,
    mode,
    selectedDepartment,
    selectedContactIds,
    departments,
    notes,
    objective,
    originDecisionCycleId,
    noCalls,
    onClose,
    onSuccess,
  ]);

  // ==============================|| VALIDATION ||============================== //

  const isValid = useMemo(() => {
    if (mode === MODES.DEPARTMENT) return Boolean(selectedDepartment);
    if (mode === MODES.CONTACT) return selectedContactIds.length > 0;
    return false;
  }, [mode, selectedDepartment, selectedContactIds]);

  // ==============================|| LOADING ||============================== //

  const isLoading = targetedLoading || contactsLoading;
  const isStep1 = wizardStep === STEPS.TARGET;

  // ==============================|| RENDER ||============================== //

  return (
    <Modal open={open} onClose={onClose}>
      <MainCard
        title={
          <Stack direction="row" spacing={1} alignItems="center">
            <AimOutlined />
            <span>Add to Targeted Campaign</span>
          </Stack>
        }
        sx={{
          position: "absolute",
          top: "50%",
          left: "50%",
          transform: "translate(-50%, -50%)",
          width: { xs: "calc(100% - 32px)", sm: 480 },
          maxHeight: "calc(100vh - 48px)",
          overflowY: "auto",
        }}
        modal
      >
        <Stack spacing={3}>
          {/* Account name */}
          <Stack direction="row" spacing={1} alignItems="center">
            <Typography variant="body2" color="text.secondary">
              Account:
            </Typography>
            <Typography variant="subtitle2">{accountName}</Typography>
          </Stack>

          {isLoading ? (
            <Stack spacing={1}>
              {[1, 2, 3].map((i) => (
                <Skeleton key={i} height={40} sx={{ borderRadius: 1 }} />
              ))}
            </Stack>
          ) : (
            <>
              {/* ── STEP 1: Target selection ── */}
              {isStep1 && (
                <>
                  {/* Mode selection */}
                  <Box>
                    <Typography variant="subtitle2" sx={{ mb: 1 }}>
                      What do you want to target?
                    </Typography>
                    <RadioGroup value={mode} onChange={handleModeChange}>
                      <FormControlLabel
                        value={MODES.DEPARTMENT}
                        control={<Radio size="small" />}
                        label={
                          <Typography variant="body2">
                            A specific department
                          </Typography>
                        }
                        disabled={departments.length === 0}
                      />
                      <FormControlLabel
                        value={MODES.CONTACT}
                        control={<Radio size="small" />}
                        label={
                          <Typography variant="body2">
                            Specific contacts
                          </Typography>
                        }
                        disabled={contacts.length === 0}
                      />
                    </RadioGroup>
                  </Box>

                  {/* Department picker */}
                  {mode === MODES.DEPARTMENT && (
                    <Box>
                      <Typography
                        variant="caption"
                        color="text.secondary"
                        sx={{ mb: 1, display: "block" }}
                      >
                        Select a department
                      </Typography>
                      <List dense disablePadding>
                        {departments.map((dept) => (
                          <ListItem key={dept.name} disablePadding>
                            <ListItemButton
                              selected={selectedDepartment === dept.name}
                              onClick={() => setSelectedDepartment(dept.name)}
                              sx={{ borderRadius: 1, mb: 0.5 }}
                            >
                              <ListItemText
                                primary={dept.name}
                                secondary={`${dept.count} contact${dept.count > 1 ? "s" : ""}`}
                              />
                              {selectedDepartment === dept.name && (
                                <Chip
                                  label="Selected"
                                  size="small"
                                  color="primary"
                                  variant="outlined"
                                />
                              )}
                            </ListItemButton>
                          </ListItem>
                        ))}
                      </List>
                    </Box>
                  )}

                  {/* Contact picker */}
                  {mode === MODES.CONTACT && (
                    <Box>
                      <Typography
                        variant="caption"
                        color="text.secondary"
                        sx={{ mb: 1, display: "block" }}
                      >
                        Select contacts ({selectedContactIds.length} selected)
                      </Typography>
                      <List
                        dense
                        disablePadding
                        sx={{ maxHeight: 240, overflowY: "auto" }}
                      >
                        {contacts.map((contact) => {
                          const fullName =
                            `${contact.first_name || ""} ${contact.last_name || ""}`.trim() ||
                            contact.email;
                          const isSelected = selectedContactIds.includes(
                            contact.id,
                          );
                          const isActive = activeContactIds.has(contact.id);
                          const isReactivatable = reactivatableContactIds.has(
                            contact.id,
                          );

                          return (
                            <ListItem key={contact.id} disablePadding>
                              <ListItemButton
                                onClick={() =>
                                  !isActive && handleContactToggle(contact.id)
                                }
                                disabled={isActive}
                                sx={{
                                  borderRadius: 1,
                                  mb: 0.25,
                                  opacity: isActive ? 0.6 : 1,
                                }}
                              >
                                <Checkbox
                                  size="small"
                                  checked={isSelected}
                                  disabled={isActive}
                                  disableRipple
                                  sx={{ p: 0, mr: 1 }}
                                />
                                <ListItemText
                                  primary={fullName}
                                  secondary={
                                    [contact.job_title, contact.department_name]
                                      .filter(Boolean)
                                      .join(" · ") || contact.email
                                  }
                                />
                                {isActive && (
                                  <Chip
                                    label="Already enrolled"
                                    size="small"
                                    color="warning"
                                    variant="outlined"
                                    sx={{ ml: 1 }}
                                  />
                                )}
                                {isReactivatable && !isActive && (
                                  <Chip
                                    label="Will reactivate"
                                    size="small"
                                    color="info"
                                    variant="outlined"
                                    sx={{ ml: 1 }}
                                  />
                                )}
                              </ListItemButton>
                            </ListItem>
                          );
                        })}
                      </List>
                    </Box>
                  )}
                </>
              )}

              {/* ── STEP 2: Origin Decision Cycle ── */}
              {!isStep1 && (
                <Box>
                  <Typography variant="subtitle2" sx={{ mb: 0.5 }}>
                    Linked to a Decision Cycle?{" "}
                    <Typography
                      component="span"
                      variant="caption"
                      color="text.secondary"
                    >
                      (optional)
                    </Typography>
                  </Typography>
                  <Typography
                    variant="caption"
                    color="text.secondary"
                    sx={{ mb: 1.5, display: "block" }}
                  >
                    Select the active decision cycle that motivates this
                    enrollment. Generated activities will reference it for full
                    traceability.
                  </Typography>

                  {cyclesLoading ? (
                    <Stack spacing={0.5}>
                      {[1, 2].map((i) => (
                        <Skeleton
                          key={i}
                          height={36}
                          sx={{ borderRadius: 1 }}
                        />
                      ))}
                    </Stack>
                  ) : openCycles.length === 0 ? (
                    <Typography variant="body2" color="text.secondary">
                      No open decision cycles found for this account.
                    </Typography>
                  ) : (
                    <List
                      dense
                      disablePadding
                      sx={{ maxHeight: 220, overflowY: "auto" }}
                    >
                      {openCycles.map((cycle) => {
                        const isSelected = originDecisionCycleId === cycle.id;
                        return (
                          <ListItem key={cycle.id} disablePadding>
                            <ListItemButton
                              selected={isSelected}
                              onClick={() =>
                                setOriginDecisionCycleId(
                                  isSelected ? null : cycle.id,
                                )
                              }
                              sx={{ borderRadius: 1, mb: 0.25 }}
                            >
                              <Checkbox
                                size="small"
                                checked={isSelected}
                                disableRipple
                                sx={{ p: 0, mr: 1 }}
                              />
                              <ListItemText
                                primary={cycle.name}
                                secondary={
                                  cycle.cycle_status ||
                                  cycle.derived_status ||
                                  ""
                                }
                              />
                            </ListItemButton>
                          </ListItem>
                        );
                      })}
                    </List>
                  )}

                  {/* No calls — per-enrollment channel override */}
                  <Box sx={{ mt: 2 }}>
                    <FormControlLabel
                      control={
                        <Checkbox
                          size="small"
                          checked={noCalls}
                          onChange={(e) => setNoCalls(e.target.checked)}
                        />
                      }
                      label="No calls"
                    />
                    <Typography variant="caption" color="text.secondary" display="block">
                      No call steps for the contacts added here; email or LinkedIn only.
                    </Typography>
                  </Box>

                  {/* Notes */}
                  <Box sx={{ mt: 2 }}>
                    <Typography variant="subtitle2" sx={{ mb: 0.5 }}>
                      Notes{" "}
                      <Typography
                        component="span"
                        variant="caption"
                        color="text.secondary"
                      >
                        (optional)
                      </Typography>
                    </Typography>
                    <TextField
                      fullWidth
                      size="small"
                      multiline
                      rows={2}
                      placeholder="e.g. Key account for Q3 push, opening from last call..."
                      value={notes}
                      onChange={(e) => setNotes(e.target.value)}
                    />
                  </Box>

                  {/* Activity Objective */}
                  <Box sx={{ mt: 2 }}>
                    <Typography variant="subtitle2" sx={{ mb: 0.5 }}>
                      Activity Objective{" "}
                      <Typography
                        component="span"
                        variant="caption"
                        color="text.secondary"
                      >
                        (optional)
                      </Typography>
                    </Typography>
                    <TextField
                      fullWidth
                      size="small"
                      multiline
                      rows={2}
                      inputProps={{ maxLength: 500 }}
                      placeholder="Describe the goal — the AI recommendations will be more accurate."
                      value={objective}
                      onChange={(e) => setObjective(e.target.value)}
                    />
                  </Box>
                </Box>
              )}
            </>
          )}

          <Divider />

          {/* Actions */}
          <Stack
            direction="row"
            justifyContent="space-between"
            alignItems="center"
          >
            <Typography variant="caption" color="text.secondary">
              Adds to your <strong>Targeted Campaign</strong>
            </Typography>
            <Stack direction="row" spacing={1}>
              {isStep1 ? (
                <>
                  <Button
                    variant="outlined"
                    color="secondary"
                    onClick={onClose}
                    disabled={submitting}
                  >
                    Cancel
                  </Button>
                  <Button
                    variant="contained"
                    onClick={() => setWizardStep(STEPS.ORIGIN)}
                    disabled={!isValid || isLoading}
                  >
                    Next
                  </Button>
                </>
              ) : (
                <>
                  <Button
                    variant="outlined"
                    color="secondary"
                    onClick={() => setWizardStep(STEPS.TARGET)}
                    disabled={submitting}
                  >
                    Back
                  </Button>
                  <Button
                    variant="contained"
                    onClick={handleSubmit}
                    disabled={submitting || isLoading}
                    startIcon={
                      submitting ? (
                        <CircularProgress size={14} color="inherit" />
                      ) : (
                        <AimOutlined />
                      )
                    }
                  >
                    {submitting ? "Adding..." : "Add to Campaign"}
                  </Button>
                </>
              )}
            </Stack>
          </Stack>
        </Stack>
      </MainCard>
    </Modal>
  );
}

AddToCampaignModal.propTypes = {
  open: PropTypes.bool.isRequired,
  onClose: PropTypes.func.isRequired,
  onSuccess: PropTypes.func,
  accountId: PropTypes.string.isRequired,
  accountName: PropTypes.string,
  preselectedContactId: PropTypes.string,
};
