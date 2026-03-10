// frontend/src/sections/campaigns/workspace/CampaignPlaylistTab.jsx
/**
 * Campaign Playlist Tab — Main playlist view with real API data.
 *
 * Displays: PlaylistProgressBar + list of PlaylistActivityCard.
 * Accordion pattern: only one card expanded at a time.
 * Executor filter: optional dropdown to filter by a single team member.
 * Optimistic removal: completed activities are hidden immediately from the UI.
 *
 * Pattern: CampaignAccountsTab (tab structure, loading/empty states)
 * Data: useGetPlaylist (real API), completePlaylistActivity (real mutation)
 */

"use client";

import PropTypes from "prop-types";
import { useState, useCallback, useMemo } from "react";

// material-ui
import Accordion from "@mui/material/Accordion";
import AccordionDetails from "@mui/material/AccordionDetails";
import AccordionSummary from "@mui/material/AccordionSummary";
import Button from "@mui/material/Button";
import Box from "@mui/material/Box";
import Chip from "@mui/material/Chip";
import Dialog from "@mui/material/Dialog";
import DialogActions from "@mui/material/DialogActions";
import DialogContent from "@mui/material/DialogContent";
import DialogContentText from "@mui/material/DialogContentText";
import DialogTitle from "@mui/material/DialogTitle";
import Radio from "@mui/material/Radio";
import RadioGroup from "@mui/material/RadioGroup";
import FormControlLabel from "@mui/material/FormControlLabel";
import FormControl from "@mui/material/FormControl";
import InputLabel from "@mui/material/InputLabel";
import MenuItem from "@mui/material/MenuItem";
import Select from "@mui/material/Select";
import Skeleton from "@mui/material/Skeleton";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";

import DownOutlined from "@ant-design/icons/DownOutlined";

// project imports
import PlaylistProgressBar from "./PlaylistProgressBar";
import PlaylistActivityCard from "components/cards/PlaylistActivityCard";

// api
import {
  useGetPlaylist,
  useGetCampaignMembers,
  useGetCompletedActivities,
  completePlaylistActivity,
  cancelPlannedActivities,
  recordCallNoAnswer,
} from "api/campaigns/campaigns";

// utils
import {
  displaySuccessSnackbar,
  displayErrorSnackbar,
} from "utils/displayError";

// ==============================|| LOADING SKELETON ||============================== //

function PlaylistSkeleton() {
  return (
    <Stack spacing={1.5}>
      {[1, 2, 3, 4].map((i) => (
        <Skeleton
          key={i}
          variant="rectangular"
          height={80}
          sx={{ borderRadius: 1.5 }}
        />
      ))}
    </Stack>
  );
}

// ==============================|| CAMPAIGN PLAYLIST TAB ||============================== //

export default function CampaignPlaylistTab({ campaignId, campaign }) {
  // ==============================|| STATE ||============================== //

  const [expandedCardId, setExpandedCardId] = useState(null);
  const [completingId, setCompletingId] = useState(null);
  const [completedToday, setCompletedToday] = useState(0);
  // Scope dialog — shown after a terminal outcome when account has multiple contacts
  const [scopeDialog, setScopeDialog] = useState(null);
  // { activityId, accountId, contactId, contacts: [] }
  const [scopeChoice, setScopeChoice] = useState("contact");
  const [executorId, setExecutorId] = useState("");

  // Track optimistically removed activity IDs
  const [removedIds, setRemovedIds] = useState(new Set());

  // ==============================|| DATA ||============================== //

  const {
    activities: rawActivities,
    totalCount,
    playlistLoading,
    playlistError,
    mutatePlaylist,
  } = useGetPlaylist(campaignId, {
    executorId: executorId || undefined,
  });

  const { members } = useGetCampaignMembers(campaignId);

  // Executors = members with role EXECUTOR or RECEIVER
  const executors = useMemo(
    () => members.filter((m) => m.role === "EXECUTOR" || m.role === "RECEIVER"),
    [members],
  );

  // Filter out optimistically removed activities
  const activities = useMemo(
    () => rawActivities.filter((a) => !removedIds.has(a.id)),
    [rawActivities, removedIds],
  );

  // ==============================|| HANDLERS ||============================== //

  const handleExpand = useCallback((activityId) => {
    setExpandedCardId((prev) => (prev === activityId ? null : activityId));
  }, []);

  const handleExecutorChange = useCallback((event) => {
    setExecutorId(event.target.value);
    setRemovedIds(new Set());
  }, []);

  // Outcome category map — mirrors ACTIVITY_OUTCOME_CONFIG in PlaylistActivityCard
  const OUTCOME_CATEGORIES = {
    SUCCESSFUL: "positive",
    MEETING_SCHEDULED: "positive",
    NO_ANSWER: "neutral",
    CALLBACK_REQUESTED: "neutral",
    FOLLOW_UP_NEEDED: "neutral",
    OTHER: "neutral",
    NOT_INTERESTED: "negative",
    WRONG_CONTACT: "negative",
  };

  // Outcomes that require cancelling remaining planned activities
  const TERMINAL_OUTCOMES = [
    "SUCCESSFUL",
    "MEETING_SCHEDULED",
    "NOT_INTERESTED",
    "WRONG_CONTACT",
  ];

  const handleComplete = useCallback(
    async (activityId, payload) => {
      setCompletingId(activityId);

      // CALL + NO_ANSWER below threshold — intercept BEFORE calling complete.
      // Activity must stay PLANNED; dedicated endpoint handles the attempt counter.
      if (payload._is_no_answer_retry) {
        try {
          const result = await recordCallNoAnswer(
            activityId,
            payload.outcome_notes,
          );
          if (result.success) {
            mutatePlaylist();
            displaySuccessSnackbar("Attempt recorded");
          } else {
            displayErrorSnackbar(result);
          }
        } catch (err) {
          displayErrorSnackbar(err);
        } finally {
          setCompletingId(null);
        }
        return;
      }

      try {
        const result = await completePlaylistActivity(
          activityId,
          campaignId,
          payload,
        );

        if (result.success) {
          setExpandedCardId(null);

          // Standard completion — remove optimistically from playlist.
          setRemovedIds((prev) => new Set([...prev, activityId]));
          setCompletedToday((prev) => prev + 1);

          const category = OUTCOME_CATEGORIES[payload.outcome] || "neutral";
          if (category === "negative") {
            displaySuccessSnackbar("Activity completed — sequence cancelled");
          } else if (category === "positive") {
            displaySuccessSnackbar("Activity completed successfully");
          } else {
            displaySuccessSnackbar("Activity completed");
          }

          mutatePlaylist();

          // After terminal outcome — cancel remaining PLANNED activities
          if (TERMINAL_OUTCOMES.includes(payload.outcome)) {
            const activity = rawActivities.find((a) => a.id === activityId);
            const accountId = activity?.account?.id;
            const contacts = activity?.contacts || [];

            if (accountId) {
              if (contacts.length > 1) {
                // Multiple contacts — ask scope
                setScopeChoice("contact");
                setScopeDialog({
                  activityId,
                  accountId,
                  contactId: contacts[0]?.id,
                  contacts,
                });
              } else {
                // Single contact or no contact — cancel entire account
                await cancelPlannedActivities(campaignId, {
                  scope: "account",
                  account_id: accountId,
                });
              }
            }
          }
        } else {
          displayErrorSnackbar(result);
        }
      } catch (err) {
        displayErrorSnackbar(err);
      } finally {
        setCompletingId(null);
      }
    },
    [campaignId, mutatePlaylist, rawActivities],
  );

  const handleScopeConfirm = useCallback(async () => {
    if (!scopeDialog) return;
    const { accountId, contactId } = scopeDialog;

    const payload =
      scopeChoice === "contact"
        ? { scope: "contact", account_id: accountId, contact_id: contactId }
        : { scope: "account", account_id: accountId };

    try {
      const result = await cancelPlannedActivities(campaignId, payload);
      if (!result.success) displayErrorSnackbar(result);
    } catch (err) {
      displayErrorSnackbar(err);
    } finally {
      setScopeDialog(null);
    }
  }, [campaignId, scopeDialog, scopeChoice]);

  // ==============================|| DERIVED VALUES ||============================== //

  // ── Completed activities (separate fetch, collapsed by default) ──
  const { activities: completedActivities, completedActivitiesLoading } =
    useGetCompletedActivities(campaignId);

  // ── Split PLANNED into Today vs Upcoming ──
  const todayStr = new Date().toLocaleDateString("en-CA"); // YYYY-MM-DD, timezone-safe

  const { todayActivities, upcomingActivities } = useMemo(() => {
    const today = [];
    const upcoming = [];
    activities.forEach((a) => {
      const d = a.scheduled_date || a.due_date;
      if (!d || d <= todayStr) {
        today.push(a);
      } else {
        upcoming.push(a);
      }
    });
    return { todayActivities: today, upcomingActivities: upcoming };
  }, [activities, todayStr]);

  const completedCount =
    totalCount > 0 ? Math.max(0, totalCount - rawActivities.length) : 0;

  // ==============================|| EMPTY STATE — Campaign not active ||============================== //

  const BLOCKED_STATUSES = {
    DRAFT: {
      title: "Campaign not started",
      body: "Start the campaign to activate the activity playlist.",
    },
    COMPLETED: {
      title: "Campaign completed",
      body: "This campaign has ended. The playlist is now read-only.",
    },
    CANCELLED: {
      title: "Campaign cancelled",
      body: "This campaign was cancelled. No activities are available.",
    },
  };

  if (!playlistLoading && campaign && BLOCKED_STATUSES[campaign.status]) {
    const { title, body } = BLOCKED_STATUSES[campaign.status];
    return (
      <Box sx={{ py: 6, textAlign: "center" }}>
        <Typography variant="h5" color="text.secondary">
          {title}
        </Typography>
        <Typography variant="body2" color="text.disabled" sx={{ mt: 1 }}>
          {body}
        </Typography>
      </Box>
    );
  }

  // ==============================|| PAUSED BANNER ||============================== //

  const isPaused = campaign?.status === "PAUSED";

  // ==============================|| LOADING STATE ||============================== //

  if (playlistLoading) {
    return (
      <Stack spacing={2}>
        <PlaylistProgressBar loading />
        <PlaylistSkeleton />
      </Stack>
    );
  }

  // ==============================|| ERROR STATE ||============================== //

  if (playlistError) {
    return (
      <Box sx={{ py: 6, textAlign: "center" }}>
        <Typography variant="h5" color="error">
          Failed to load playlist
        </Typography>
        <Typography variant="body2" color="text.disabled" sx={{ mt: 1 }}>
          Please try refreshing the page.
        </Typography>
      </Box>
    );
  }

  // ==============================|| EMPTY STATE — No activities ||============================== //

  if (!activities.length && totalCount === 0) {
    return (
      <Stack spacing={2}>
        <PlaylistProgressBar
          total={0}
          completed={0}
          completedToday={completedToday}
        />
        <Box sx={{ py: 6, textAlign: "center" }}>
          <Typography variant="h5" color="text.secondary">
            No activities in playlist
          </Typography>
          <Typography variant="body2" color="text.disabled" sx={{ mt: 1 }}>
            All activities have been completed, or none have been generated yet.
          </Typography>
        </Box>
      </Stack>
    );
  }

  // ==============================|| RENDER ||============================== //

  return (
    <Stack spacing={2}>
      {/* ==================== SCOPE DIALOG ==================== */}
      {scopeDialog && (
        <Dialog
          open={Boolean(scopeDialog)}
          onClose={() => setScopeDialog(null)}
          maxWidth="xs"
          fullWidth
        >
          <DialogTitle>Cancel remaining activities</DialogTitle>
          <DialogContent>
            <DialogContentText sx={{ mb: 2 }}>
              This account has multiple contacts. Which activities should be
              cancelled?
            </DialogContentText>
            <RadioGroup
              value={scopeChoice}
              onChange={(e) => setScopeChoice(e.target.value)}
            >
              <FormControlLabel
                value="contact"
                control={<Radio size="small" />}
                label={
                  <Typography variant="body2">
                    This contact only —{" "}
                    <Typography
                      component="span"
                      variant="body2"
                      color="text.secondary"
                    >
                      {scopeDialog.contacts.find(
                        (c) => c.id === scopeDialog.contactId,
                      )?.first_name || "selected contact"}
                    </Typography>
                  </Typography>
                }
              />
              <FormControlLabel
                value="account"
                control={<Radio size="small" />}
                label={
                  <Typography variant="body2">
                    Entire account — cancel all remaining activities
                  </Typography>
                }
              />
            </RadioGroup>
          </DialogContent>
          <DialogActions sx={{ px: 3, pb: 2 }}>
            <Button
              onClick={() => setScopeDialog(null)}
              color="inherit"
              size="small"
            >
              Skip
            </Button>
            <Button
              onClick={handleScopeConfirm}
              variant="contained"
              color="error"
              size="small"
            >
              Confirm
            </Button>
          </DialogActions>
        </Dialog>
      )}

      {/* Progress bar */}
      <PlaylistProgressBar
        total={totalCount}
        completed={completedCount + completedToday}
        completedToday={completedToday}
      />

      {/* ── Section: To Do Today ── */}
      <Box>
        <Stack direction="row" alignItems="center" spacing={1} sx={{ mb: 1.5 }}>
          <Typography variant="subtitle2" fontWeight={600}>
            To do today
          </Typography>
          <Chip
            label={todayActivities.length}
            size="small"
            color="primary"
            variant="filled"
          />
        </Stack>

        {todayActivities.length === 0 ? (
          <Box sx={{ py: 3, textAlign: "center" }}>
            <Typography variant="body2" color="text.secondary">
              Nothing to do today. Great job!
            </Typography>
          </Box>
        ) : (
          <Stack spacing={1.5}>
            {todayActivities.map((activity) => (
              <PlaylistActivityCard
                key={activity.id}
                activity={activity}
                expanded={expandedCardId === activity.id}
                onExpand={handleExpand}
                onComplete={handleComplete}
                completing={completingId === activity.id}
              />
            ))}
          </Stack>
        )}
      </Box>

      {/* ── Section: Upcoming (collapsible) ── */}
      {upcomingActivities.length > 0 && (
        <Accordion
          disableGutters
          elevation={0}
          sx={{
            border: "1px solid",
            borderColor: "divider",
            borderRadius: 1.5,
            "&:before": { display: "none" },
            "&.Mui-expanded": { borderColor: "divider" },
          }}
        >
          <AccordionSummary
            expandIcon={<DownOutlined style={{ fontSize: 12 }} />}
            sx={{
              minHeight: 48,
              "& .MuiAccordionSummary-content": {
                alignItems: "center",
                gap: 1,
              },
            }}
          >
            <Typography variant="subtitle2" fontWeight={600}>
              Upcoming
            </Typography>
            <Chip
              label={upcomingActivities.length}
              size="small"
              variant="outlined"
            />
          </AccordionSummary>
          <AccordionDetails sx={{ pt: 0, pb: 1.5 }}>
            <Stack spacing={1.5}>
              {upcomingActivities.map((activity) => (
                <PlaylistActivityCard
                  key={activity.id}
                  activity={activity}
                  expanded={false}
                  onExpand={() => {}}
                  onComplete={handleComplete}
                  completing={completingId === activity.id}
                  isGreyedOut
                />
              ))}
            </Stack>
          </AccordionDetails>
        </Accordion>
      )}

      {/* ── Section: Completed (collapsible) ── */}
      <Accordion
        disableGutters
        elevation={0}
        sx={{
          border: "1px solid",
          borderColor: "divider",
          borderRadius: 1.5,
          "&:before": { display: "none" },
        }}
      >
        <AccordionSummary
          expandIcon={<DownOutlined style={{ fontSize: 12 }} />}
          sx={{
            minHeight: 48,
            "& .MuiAccordionSummary-content": { alignItems: "center", gap: 1 },
          }}
        >
          <Typography variant="subtitle2" fontWeight={600}>
            Completed
          </Typography>
          <Chip
            label={
              completedActivities.filter((a) => a.status === "COMPLETED")
                .length || completedCount
            }
            size="small"
            variant="outlined"
            color="success"
          />
        </AccordionSummary>
        <AccordionDetails sx={{ pt: 0, pb: 1.5 }}>
          {completedActivitiesLoading ? (
            <Stack spacing={1}>
              {[1, 2].map((i) => (
                <Skeleton key={i} height={60} sx={{ borderRadius: 1 }} />
              ))}
            </Stack>
          ) : completedActivities.length === 0 ? (
            <Typography
              variant="body2"
              color="text.secondary"
              sx={{ py: 2, textAlign: "center" }}
            >
              No completed activities yet
            </Typography>
          ) : (
            <Stack spacing={1.5}>
              {completedActivities
                .filter((a) => a.status === "COMPLETED")
                .map((activity) => (
                  <PlaylistActivityCard
                    key={activity.id}
                    activity={activity}
                    expanded={false}
                    onExpand={() => {}}
                    onComplete={() => {}}
                    completing={false}
                    isGreyedOut
                  />
                ))}
            </Stack>
          )}
        </AccordionDetails>
      </Accordion>
    </Stack>
  );
}

CampaignPlaylistTab.propTypes = {
  /** Campaign UUID */
  campaignId: PropTypes.string.isRequired,
  /** Campaign object (for status check) */
  campaign: PropTypes.object,
};
