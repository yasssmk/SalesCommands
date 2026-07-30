// frontend/src/sections/campaigns/workspace/CampaignPlaylistTab.jsx
/**
 * Campaign Playlist Tab — Main playlist view with real API data.
 *
 * Displays: list of PlaylistActivityCard.
 * Accordion pattern: only one card expanded at a time.
 * Executor filter: optional dropdown to filter by a single team member.
 * Optimistic removal: completed activities are hidden immediately from the UI.
 *
 * Pattern: CampaignAccountsTab (tab structure, loading/empty states)
 * Data: useGetPlaylist (real API), completePlaylistActivity (real mutation)
 */

"use client";

import PropTypes from "prop-types";
import { useState, useCallback, useMemo, useEffect } from "react";

// material-ui
import Accordion from "@mui/material/Accordion";
import AccordionDetails from "@mui/material/AccordionDetails";
import AccordionSummary from "@mui/material/AccordionSummary";
import Alert from "@mui/material/Alert";
import Button from "@mui/material/Button";
import Box from "@mui/material/Box";
import Chip from "@mui/material/Chip";
import Skeleton from "@mui/material/Skeleton";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";

import DownOutlined from "@ant-design/icons/DownOutlined";

// project imports
import PlaylistActivityCard from "components/cards/PlaylistActivityCard";
import CampaignOutcomeModal from "../CampaignOutcomeModal";

import {
  useGetPlaylist,
  useGetCampaignMembers,
  useGetCompletedActivities,
  completePlaylistActivity,
  completeCampaign,
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

export default function CampaignPlaylistTab({
  campaignId,
  campaign,
  completionEligible,
  onCampaignUpdate,
}) {
  // ==============================|| STATE ||============================== //

  const [completingId, setCompletingId] = useState(null);
  const [dismissedCompletion, setDismissedCompletion] = useState(false);
  const [completing, setCompleting] = useState(false);
  // { open: bool, activity: object|null }
  const [outcomeModal, setOutcomeModal] = useState({
    open: false,
    activity: null,
  });
  const [executorId, setExecutorId] = useState("");

  // Track optimistically removed activity IDs
  const [removedIds, setRemovedIds] = useState(new Set());
  const [showCompleted, setShowCompleted] = useState(false);
  const [completedPage, setCompletedPage] = useState(1);
  const [accumulatedCompleted, setAccumulatedCompleted] = useState([]);

  // Auto-expand completed accordion when campaign is already COMPLETED
  useEffect(() => {
    if (campaign?.status === "COMPLETED") {
      setShowCompleted(true);
    }
  }, [campaign?.status]);

  // ==============================|| DATA ||============================== //

  const BLOCKED_STATUSES = {
    DRAFT: {
      title: "Campaign not started",
      body: "Start the campaign to activate the activity playlist.",
    },
    PAUSED: {
      title: "Campaign paused",
      body: "Activities are on hold. Resume the campaign to continue.",
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

  const isBlocked = campaign && BLOCKED_STATUSES[campaign?.status];

  // COMPLETED skips playlist fetch — only the completed accordion is shown,
  // which uses useGetCompletedActivities (separate endpoint). No need to hit
  // the playlist endpoint for 0 PLANNED activities.
  const shouldFetchPlaylist =
    campaign && !["DRAFT", "CANCELLED", "COMPLETED"].includes(campaign?.status);

  const {
    activities: rawActivities,
    totalCount,
    playlistLoading,
    playlistError,
    mutatePlaylist,
  } = useGetPlaylist(shouldFetchPlaylist ? campaignId : null, {
    executorId: executorId || undefined,
  });

  // Executors — derived from campaign object (owner + executor if set)
  const executors = useMemo(() => {
    const result = [];
    if (campaign?.owner) result.push({ ...campaign.owner, role: "OWNER" });
    if (campaign?.executor)
      result.push({ ...campaign.executor, role: "EXECUTOR" });
    return result;
  }, [campaign]);

  // Filter out optimistically removed activities
  const activities = useMemo(
    () => rawActivities.filter((a) => !removedIds.has(a.id)),
    [rawActivities, removedIds],
  );

  // ==============================|| HANDLERS ||============================== //

  const handleExecutorChange = useCallback((event) => {
    setExecutorId(event.target.value);
    setRemovedIds(new Set());
  }, []);

  // 1-click complete for EMAIL / LINKEDIN
  const handleOneClickComplete = useCallback(
    async (activityId, payload) => {
      setCompletingId(activityId);
      const snapshotRemovedIds = removedIds;
      try {
        const result = await completePlaylistActivity(
          activityId,
          campaignId,
          payload,
        );
        if (result.success) {
          setRemovedIds((prev) => new Set([...prev, activityId]));
          mutatePlaylist();
          if (onCampaignUpdate) onCampaignUpdate();
          displaySuccessSnackbar("Activity completed");
        } else {
          setRemovedIds(snapshotRemovedIds);
          displayErrorSnackbar(result);
        }
      } catch (err) {
        setRemovedIds(snapshotRemovedIds);
        displayErrorSnackbar(err);
      } finally {
        setCompletingId(null);
      }
    },
    [campaignId, mutatePlaylist, onCampaignUpdate, removedIds],
  );

  // Opens outcome modal for CALL / MEETING / TASK
  const handleLogOutcome = useCallback((activity) => {
    setOutcomeModal({ open: true, activity });
  }, []);

  // Called by CampaignOutcomeModal on successful completion
  const handleOutcomeComplete = useCallback(
    (activityId) => {
      setRemovedIds((prev) => new Set([...prev, activityId]));
      mutatePlaylist();
      if (onCampaignUpdate) onCampaignUpdate();
    },
    [mutatePlaylist, onCampaignUpdate],
  );

  // Complete campaign from playlist banner
  const handleCompleteCampaign = useCallback(async () => {
    setCompleting(true);
    try {
      const result = await completeCampaign(campaignId);
      if (result.success) {
        displaySuccessSnackbar("Campaign completed");
        if (onCampaignUpdate) onCampaignUpdate();
      } else {
        displayErrorSnackbar(result);
      }
    } finally {
      setCompleting(false);
    }
  }, [campaignId, onCampaignUpdate]);

  // ==============================|| DERIVED VALUES ||============================== //

  const {
    activities: completedActivities,
    completedActivitiesTotalCount,
    completedActivitiesLoading,
  } = useGetCompletedActivities(
    showCompleted ? campaignId : null,
    completedPage,
    // Product rule (TD-126): only TARGETED hides completed activities of
    // finished sequences. OUTBOUND keeps ALL completed activities visible.
    campaign?.campaign_type === "TARGETED",
  );

  // Accumulate pages — append new results when page increments
  useEffect(() => {
    if (!completedActivitiesLoading && completedActivities.length > 0) {
      setAccumulatedCompleted((prev) => {
        const existingIds = new Set(prev.map((a) => a.id));
        const newItems = completedActivities.filter(
          (a) => !existingIds.has(a.id),
        );
        return [...prev, ...newItems];
      });
    }
  }, [completedActivities, completedActivitiesLoading]);

  // Reset accumulated list when accordion is closed/reopened
  useEffect(() => {
    if (!showCompleted) {
      setAccumulatedCompleted([]);
      setCompletedPage(1);
    }
  }, [showCompleted]);

  const hasMoreCompleted =
    accumulatedCompleted.length < completedActivitiesTotalCount;

  // ── Split PLANNED into Today vs Upcoming ──
  const todayStr = new Date().toLocaleDateString("en-CA"); // YYYY-MM-DD, timezone-safe

  const { todayActivities, upcomingActivities, onHoldActivities } =
    useMemo(() => {
      const today = [];
      const upcoming = [];
      const onHold = [];

      // Build a map of min PLANNED sequence_position per campaign_contact_id.
      // An activity is only eligible for "today" if it has the lowest PLANNED
      // position for its contact — its predecessor must be completed first.
      const minPosMap = {};
      activities.forEach((a) => {
        if (
          a.status === "PLANNED" &&
          a.campaign_contact_id &&
          a.sequence_position != null &&
          !a.is_callback_followup
        ) {
          const current = minPosMap[a.campaign_contact_id];
          if (current == null || a.sequence_position < current) {
            minPosMap[a.campaign_contact_id] = a.sequence_position;
          }
        }
      });

      activities.forEach((a) => {
        if (a.status === "ON_HOLD") {
          onHold.push(a);
          return;
        }

        const sd = a.scheduled_date;
        const d = sd && typeof sd === "object" ? sd.date : sd || null;
        const isDateEligible = !d || d <= todayStr;

        // Campaign sequence guard: if this activity has a predecessor that
        // is not yet completed, it must stay in Upcoming regardless of date.
        const isFirstPlanned =
          !a.campaign_contact_id ||
          a.is_callback_followup ||
          a.sequence_position == null ||
          minPosMap[a.campaign_contact_id] === a.sequence_position;

        if (isDateEligible && isFirstPlanned) {
          today.push(a);
        } else {
          upcoming.push(a);
        }
      });

      return {
        todayActivities: today,
        upcomingActivities: upcoming,
        onHoldActivities: onHold,
      };
    }, [activities, todayStr]);

  // ==============================|| EMPTY STATE — Campaign not active ||============================== //

  // COMPLETED and PAUSED fall through to the main render.
  // COMPLETED shows the completed accordion.
  // PAUSED shows ON_HOLD activities in Upcoming with a warning banner.
  if (
    !playlistLoading &&
    campaign &&
    BLOCKED_STATUSES[campaign.status] &&
    campaign.status !== "COMPLETED" &&
    campaign.status !== "PAUSED"
  ) {
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

  // ==============================|| LOADING STATE ||============================== //

  if (playlistLoading) {
    return (
      <Stack spacing={2}>
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

  // For COMPLETED campaigns: skip the empty state so the completed accordion renders below
  if (
    !activities.length &&
    totalCount === 0 &&
    campaign?.status !== "COMPLETED" &&
    campaign?.status !== "ACTIVE"
  ) {
    return (
      <Stack spacing={2}>
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
      <CampaignOutcomeModal
        open={outcomeModal.open}
        onClose={() => setOutcomeModal({ open: false, activity: null })}
        activity={outcomeModal.activity}
        campaignId={campaignId}
        onComplete={handleOutcomeComplete}
        onUpdate={mutatePlaylist}
      />

      {/* Read-only banner for COMPLETED campaigns */}
      {campaign?.status === "COMPLETED" && (
        <Alert severity="info" variant="outlined">
          This campaign has ended. The playlist is now read-only.
        </Alert>
      )}

      {/* Paused banner — activities on hold, resume to continue */}
      {campaign?.status === "PAUSED" && (
        <Alert severity="warning" variant="outlined">
          This campaign is paused. Resume it to continue activity execution.
          On-hold activities are visible in the Upcoming section below.
        </Alert>
      )}

      {/* Completion proposal — all accounts done, no planned activities remain */}
      {completionEligible && !dismissedCompletion && (
        <Alert
          severity="success"
          variant="outlined"
          onClose={() => setDismissedCompletion(true)}
          action={
            <Stack direction="row" spacing={1} alignItems="center">
              <Button
                size="small"
                variant="contained"
                color="success"
                disabled={completing}
                onClick={handleCompleteCampaign}
              >
                {completing ? "Completing..." : "Complete Campaign"}
              </Button>
              <Button
                size="small"
                color="inherit"
                onClick={() => setDismissedCompletion(true)}
              >
                Dismiss
              </Button>
            </Stack>
          }
        >
          All accounts have been processed — no activities remaining. Ready to
          mark this campaign as completed?
        </Alert>
      )}

      {/* ── Inactivity warning ── */}
      {campaign?.is_inactive && (
        <Alert severity="warning" variant="outlined">
          No activity completed in the last {30} days — this campaign may need
          attention.
        </Alert>
      )}

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
              Nothing to do today 🎉
            </Typography>
          </Box>
        ) : (
          <Stack spacing={1.5}>
            {todayActivities.map((activity) => (
              <PlaylistActivityCard
                key={activity.id}
                activity={activity}
                onComplete={handleOneClickComplete}
                onLogOutcome={handleLogOutcome}
                completing={completingId === activity.id}
              />
            ))}
          </Stack>
        )}
      </Box>

      {/* ── Section: Upcoming (collapsible) ── */}
      {(upcomingActivities.length > 0 || onHoldActivities.length > 0) && (
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
          </AccordionSummary>
          <AccordionDetails sx={{ pt: 0, pb: 1.5 }}>
            <Stack spacing={1.5}>
              {upcomingActivities.map((activity) => (
                <PlaylistActivityCard
                  key={activity.id}
                  activity={activity}
                  onComplete={handleOneClickComplete}
                  onLogOutcome={handleLogOutcome}
                  completing={completingId === activity.id}
                  isGreyedOut
                />
              ))}

              {/* ON_HOLD activities — end of list, warning background */}
              {onHoldActivities.map((activity) => (
                <Box
                  key={activity.id}
                  sx={{
                    borderRadius: 1.5,
                    bgcolor: "warning.lighter",
                    border: "1px solid",
                    borderColor: "warning.light",
                  }}
                >
                  <PlaylistActivityCard activity={activity} isGreyedOut />
                </Box>
              ))}
            </Stack>
          </AccordionDetails>
        </Accordion>
      )}

      {/* ── Section: Completed (collapsible, lazy-load) ── */}
      <Accordion
        disableGutters
        elevation={0}
        onChange={(_e, expanded) => {
          if (expanded) setShowCompleted(true);
        }}
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
          <Stack direction="row" alignItems="center" spacing={1}>
            <Typography variant="subtitle2" fontWeight={600}>
              Completed
            </Typography>
            {completedActivitiesTotalCount > 0 && (
              <Chip
                label={completedActivitiesTotalCount}
                size="small"
                variant="outlined"
              />
            )}
          </Stack>
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
              {accumulatedCompleted.map((activity) => (
                <PlaylistActivityCard
                  key={activity.id}
                  activity={activity}
                  isGreyedOut
                />
              ))}

              {hasMoreCompleted && (
                <Button
                  variant="outlined"
                  color="secondary"
                  size="small"
                  disabled={completedActivitiesLoading}
                  onClick={() => setCompletedPage((prev) => prev + 1)}
                  sx={{ alignSelf: "center", mt: 0.5 }}
                >
                  {completedActivitiesLoading ? "Loading..." : "Load more"}
                </Button>
              )}
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
  /** True when all accounts are terminal and no planned activities remain */
  completionEligible: PropTypes.bool,
  /** Callback to revalidate campaign after completion */
  onCampaignUpdate: PropTypes.func,
};
