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
//   - for CAMPAIGN activities, choosing CALLBACK_REQUESTED reveals a REQUIRED
//     callback DatePicker (a callback with no date is a backend no-op).
//
// No note at closure (« Source / Notes » 1.5, PO): the activity's notes are
// filled throughout its lifecycle in the Source band, never here.
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
import SectionHeader from "components/display/SectionHeader";
import OutcomeSelector from "components/outcomes/OutcomeSelector";
import { CALLBACK_OUTCOME as CALLBACK } from "utils/outcomes";


export default function OutcomeDrawerContent({ activity, onSaved }) {
  const aq = useTheme().aphoriQ;
  const { closeDrawer } = useWorkspaceDrawer();

  const isCampaign = Boolean(activity?.campaign_detail);

  const [outcome, setOutcome] = useState(null);
  const [callbackDate, setCallbackDate] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  // Callback UI is campaign-only; a chosen callback outcome needs a date.
  const showCallback = isCampaign && outcome === CALLBACK;
  const callbackMissing = showCallback && !callbackDate;
  const saveDisabled = !outcome || callbackMissing || submitting;

  const handleSave = async () => {
    if (saveDisabled) return;
    setSubmitting(true);
    const payload = { outcome };
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
      // 2.2 — a picked outcome / callback date is a modification (a save in
      // progress is not: the close that follows a success is not asked).
      dirty={(outcome != null || callbackDate != null) && !submitting}
      saveLabel="Complete"
    >
      <Stack spacing={2}>
        {/* ---- SECTION 1 — Outcome: the pills, then the callback date when it
            shows. Numbered sections (lot 3 / 13c, TD-239 — PO: every drawer). ---- */}
        <SectionHeader index={1} title="Outcome" subtitle="How did it go?" />
        <Box>
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
