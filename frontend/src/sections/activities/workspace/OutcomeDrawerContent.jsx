// frontend/src/sections/activities/workspace/OutcomeDrawerContent.jsx
//
// O-2a — the OUTCOME drawer content: complete an activity with an outcome. A
// shell-less node injected into the WorkspaceDrawer coque (title "Complete
// activity" comes from openDrawer). Built on the shared DrawerContentLayout +
// OutcomeSelector (O-1):
//
//   - outcome pills filtered by activity type (OutcomeSelector). On a DEAL
//     activity, CALLBACK_REQUESTED is hidden (callback is a campaign mechanic and
//     the standalone complete ignores callback_date backend-side).
//   - an optional note (outcome_notes).
//   - for CAMPAIGN activities, choosing CALLBACK_REQUESTED reveals a REQUIRED
//     callback DatePicker (a callback with no date is a backend no-op).
//
// Save "Complete" posts /complete/ via completeActivity (the backend branches on
// campaign_id); a campaign completion also revalidates the playlist. Draft-only
// until Save. Theme tokens, no hardcoded hex/px.

"use client";

import PropTypes from "prop-types";
import { useState } from "react";
import dayjs from "dayjs";

// MUI
import Box from "@mui/material/Box";
import Stack from "@mui/material/Stack";
import TextField from "@mui/material/TextField";
import Typography from "@mui/material/Typography";
import { useTheme } from "@mui/material/styles";
import { DatePicker } from "@mui/x-date-pickers/DatePicker";
import { LocalizationProvider } from "@mui/x-date-pickers/LocalizationProvider";
import { AdapterDayjs } from "@mui/x-date-pickers/AdapterDayjs";

// Project
import { useWorkspaceDrawer } from "contexts/WorkspaceDrawerContext";
import { completeActivity } from "api/accounts/activities";
import { revalidateCampaignPlaylist } from "api/campaigns/campaigns";
import { displaySuccessSnackbar, displayErrorSnackbar } from "utils/displayError";
import DrawerContentLayout from "components/drawer/DrawerContentLayout";
import OutcomeSelector from "components/outcomes/OutcomeSelector";

const CALLBACK = "CALLBACK_REQUESTED";

export default function OutcomeDrawerContent({ activity, onSaved }) {
  const aq = useTheme().aphoriQ;
  const { closeDrawer } = useWorkspaceDrawer();

  const isCampaign = Boolean(activity?.campaign_detail);

  const [outcome, setOutcome] = useState(null);
  const [notes, setNotes] = useState("");
  const [callbackDate, setCallbackDate] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  // Callback UI is campaign-only; a chosen callback outcome needs a date.
  const showCallback = isCampaign && outcome === CALLBACK;
  const callbackMissing = showCallback && !callbackDate;
  const saveDisabled = !outcome || callbackMissing || submitting;

  const handleSave = async () => {
    if (saveDisabled) return;
    setSubmitting(true);
    const payload = { outcome, outcome_notes: notes?.trim() || undefined };
    if (isCampaign && callbackDate) {
      payload.callback_date = dayjs(callbackDate).format("YYYY-MM-DD");
    }
    try {
      const result = await completeActivity(activity.id, payload);
      if (result?.success) {
        // A campaign completion affects the playlist too — keep both fresh
        // (completeActivity already revalidated the workspace/DC/account surfaces).
        if (isCampaign) revalidateCampaignPlaylist(activity.campaign_detail.id);
        displaySuccessSnackbar("Activity completed");
        onSaved?.();
        closeDrawer();
      } else {
        displayErrorSnackbar(result);
      }
    } catch (err) {
      displayErrorSnackbar(err);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <DrawerContentLayout
      onSave={handleSave}
      onCancel={() => closeDrawer()}
      saveDisabled={saveDisabled}
      saveLabel="Complete"
    >
      <Stack spacing={2}>
        <Box>
          <Typography variant="caption" sx={{ color: aq.text.muted, display: "block", mb: 0.5 }}>
            Outcome
          </Typography>
          <OutcomeSelector
            activityType={activity?.activity_type}
            value={outcome}
            onChange={(o) => {
              setOutcome(o);
              if (o !== CALLBACK) setCallbackDate(null);
            }}
            exclude={isCampaign ? [] : [CALLBACK]}
          />
        </Box>

        {showCallback && (
          <Box>
            <Typography variant="caption" sx={{ color: aq.text.muted, display: "block", mb: 0.5 }}>
              Callback date
            </Typography>
            <LocalizationProvider dateAdapter={AdapterDayjs}>
              <DatePicker
                label="Callback date"
                value={callbackDate}
                onChange={(v) => setCallbackDate(v)}
                slotProps={{ textField: { fullWidth: true, size: "small" } }}
              />
            </LocalizationProvider>
          </Box>
        )}

        <Box>
          <Typography variant="caption" sx={{ color: aq.text.muted, display: "block", mb: 0.5 }}>
            Note
          </Typography>
          <TextField
            fullWidth
            multiline
            minRows={2}
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="Optional note…"
            inputProps={{ "data-testid": "outcome-note" }}
          />
        </Box>
      </Stack>
    </DrawerContentLayout>
  );
}

OutcomeDrawerContent.propTypes = {
  /** The activity to complete (campaign_detail decides the campaign branch). */
  activity: PropTypes.object.isRequired,
  /** Optional callback fired after a successful completion (before the coque closes). */
  onSaved: PropTypes.func,
};
