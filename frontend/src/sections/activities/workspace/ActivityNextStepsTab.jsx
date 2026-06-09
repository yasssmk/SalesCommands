// frontend/src/sections/activities/workspace/ActivityNextStepsTab.jsx

"use client";

import PropTypes from "prop-types";
import { useState, useMemo, useCallback } from "react";
import { useRouter } from "next/navigation";

// MUI
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import CircularProgress from "@mui/material/CircularProgress";
import Divider from "@mui/material/Divider";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";

// Icons
import {
  PlusOutlined,
  InboxOutlined,
  RocketOutlined,
} from "@ant-design/icons";

// Project imports
import useActivityAllSignals from "hooks/useActivityAllSignals";
import { useGetSignalChoices } from "api/signals/signals";
import { rejectSignal } from "api/signals/signals";
import {
  displaySuccessSnackbar,
  displayErrorSnackbar,
} from "utils/displayError";

import AISuggestionCard from "components/cards/nextSteps/AISuggestionCard";
import NextStepsFilterBar from "sections/activities/nextSteps/NextStepsFilterBar";
import NextStepSuggestionDrawer from "sections/activities/nextSteps/NextStepSuggestionDrawer";
import UpcomingActivitiesSection from "sections/activities/nextSteps/UpcomingActivitiesSection";
import ActivityModal from "sections/accounts/activities/ActivityModal";
import SignalEditDialog from "sections/activities/signals/SignalEditDialog";

// ==============================|| SORT HELPERS ||============================== //

const STATUS_ORDER = { PENDING: 0, VALIDATED: 1, REJECTED: 2 };

function sortSignals(signals) {
  return [...signals].sort((a, b) => {
    const orderA = STATUS_ORDER[a.status] ?? 3;
    const orderB = STATUS_ORDER[b.status] ?? 3;
    if (orderA !== orderB) return orderA - orderB;
    const dateA = a.suggested_due_date || "";
    const dateB = b.suggested_due_date || "";
    return dateA.localeCompare(dateB);
  });
}

// ==============================|| ACTIVITY NEXT STEPS TAB ||============================== //

export default function ActivityNextStepsTab({
  activity,
  isLocked,
  mutateCounts,
}) {
  const router = useRouter();
  const activityId = activity?.id;
  const accountId = activity?.account;

  // Data
  const { nextStepSignals, loading, error, mutateAll } =
    useActivityAllSignals(activityId);
  const { choices, choicesLoading } = useGetSignalChoices();

  // Filter state
  const [activeFilter, setActiveFilter] = useState("all-active");
  const [includeRejected, setIncludeRejected] = useState(false);

  // Drawer state
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [drawerSignal, setDrawerSignal] = useState(null);

  // Activity modal state (convert from signal OR manual add)
  const [activityModalOpen, setActivityModalOpen] = useState(false);
  const [convertSignal, setConvertSignal] = useState(null);

  // Edit dialog state
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [editSignal, setEditSignal] = useState(null);

  // ==============================|| FILTERED + SORTED SIGNALS ||============================== //

  const filteredSignals = useMemo(() => {
    if (!nextStepSignals) return [];

    const filtered = nextStepSignals.filter((s) => {
      if (s.status === "REJECTED") return includeRejected;

      if (activeFilter === "all-active") {
        return s.status === "PENDING" || s.status === "VALIDATED";
      }
      return s.status === activeFilter;
    });

    return sortSignals(filtered);
  }, [nextStepSignals, activeFilter, includeRejected]);

  const pendingCount = useMemo(
    () => (nextStepSignals || []).filter((s) => s.status === "PENDING").length,
    [nextStepSignals],
  );

  const convertedCount = useMemo(
    () =>
      (nextStepSignals || []).filter(
        (s) => s.status === "VALIDATED" && s.linked_activity,
      ).length,
    [nextStepSignals],
  );

  // ==============================|| HANDLERS ||============================== //

  const handleSelect = useCallback((signal) => {
    setDrawerSignal(signal);
    setDrawerOpen(true);
  }, []);

  const handleCloseDrawer = useCallback(() => {
    setDrawerOpen(false);
    setDrawerSignal(null);
  }, []);

  const handleConvert = useCallback((signal) => {
    setConvertSignal(signal);
    setActivityModalOpen(true);
  }, []);

  const handleAddManually = useCallback(() => {
    setConvertSignal(null);
    setActivityModalOpen(true);
  }, []);

  const handleEdit = useCallback((signal) => {
    setEditSignal(signal);
    setEditDialogOpen(true);
  }, []);

  const handleReject = useCallback(
    async (signal) => {
      const result = await rejectSignal("next-steps", signal.id);
      if (result.success) {
        displaySuccessSnackbar("Suggestion rejected");
        mutateAll();
        mutateCounts?.();
        handleCloseDrawer();
      } else {
        displayErrorSnackbar(result);
      }
    },
    [mutateAll, mutateCounts, handleCloseDrawer],
  );

  const handleViewActivity = useCallback(
    (linkedActivity) => {
      if (linkedActivity?.id) {
        router.push(`/activities/${linkedActivity.id}/workspace?tab=overview`);
      }
    },
    [router],
  );

  const handleConvertSuccess = useCallback(() => {
    mutateAll();
    mutateCounts?.();
  }, [mutateAll, mutateCounts]);

  const handleEditSuccess = useCallback(() => {
    mutateAll();
    mutateCounts?.();
  }, [mutateAll, mutateCounts]);

  const handleCreateActivity = useCallback(
    (activityType) => {
      setConvertSignal(null);
      setActivityModalOpen(true);
    },
    [],
  );

  // ==============================|| LOADING / ERROR ||============================== //

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" py={6}>
        <CircularProgress size={28} />
      </Box>
    );
  }

  if (error) {
    return (
      <Box display="flex" justifyContent="center" py={6}>
        <Typography color="error">Failed to load next steps</Typography>
      </Box>
    );
  }

  const hasAnySignals = nextStepSignals && nextStepSignals.length > 0;

  // ==============================|| EMPTY STATE ||============================== //

  if (!hasAnySignals) {
    return (
      <Box py={6}>
        <Stack spacing={2} alignItems="center" textAlign="center">
          <InboxOutlined style={{ fontSize: 48, color: "#8c8c8c" }} />
          <Typography variant="h6" color="text.secondary">
            No next-step suggestions yet
          </Typography>
          <Typography
            variant="body2"
            color="text.secondary"
            maxWidth={400}
          >
            Run an AI analysis from the Notes tab to extract next-step
            suggestions, or add an activity manually.
          </Typography>
          {!isLocked && (
            <Button
              variant="outlined"
              startIcon={<PlusOutlined style={{ fontSize: 14 }} />}
              onClick={handleAddManually}
            >
              Add manually
            </Button>
          )}
        </Stack>

        {/* Upcoming Activities section (always shown when in sequence) */}
        {activity?.sequence_context && (
          <Box mt={4}>
            <Typography variant="h6" sx={{ mb: 1.5 }}>
              <RocketOutlined style={{ fontSize: 18, marginRight: 8 }} />
              Upcoming Activities
            </Typography>
            <UpcomingActivitiesSection
              activity={activity}
              onCreateActivity={handleCreateActivity}
              isLocked={isLocked}
            />
          </Box>
        )}

        {/* Add activity modal */}
        {accountId && (
          <ActivityModal
            open={activityModalOpen}
            onClose={() => {
              setActivityModalOpen(false);
              setConvertSignal(null);
            }}
            activity={null}
            accountId={accountId}
            decisionStepId={activity?.decision_step || null}
            decisionCycleId={activity?.decision_cycle || null}
            defaultActivityType={convertSignal?.suggested_activity_type || "MEETING"}
            previousActivityId={activity?.id}
            nextStepSignal={convertSignal}
            onSuccess={handleConvertSuccess}
          />
        )}
      </Box>
    );
  }

  // ==============================|| MAIN RENDER ||============================== //

  return (
    <Box>
      {/* Header row — title + add button */}
      <Stack
        direction="row"
        justifyContent="space-between"
        alignItems="center"
        mb={2}
      >
        <Typography variant="h6">Next Steps</Typography>
        {!isLocked && (
          <Button
            size="small"
            variant="outlined"
            startIcon={<PlusOutlined style={{ fontSize: 14 }} />}
            onClick={handleAddManually}
          >
            Add manually
          </Button>
        )}
      </Stack>

      {/* Summary line */}
      <Typography variant="body2" color="text.secondary" mb={1.5}>
        {pendingCount > 0 &&
          `${pendingCount} AI suggestion${pendingCount > 1 ? "s" : ""} to handle`}
        {pendingCount > 0 && convertedCount > 0 && " · "}
        {convertedCount > 0 &&
          `${convertedCount} activit${convertedCount > 1 ? "ies" : "y"} created`}
      </Typography>

      {/* Filter bar */}
      <NextStepsFilterBar
        activeFilter={activeFilter}
        onChange={setActiveFilter}
        includeRejected={includeRejected}
        onToggleRejected={setIncludeRejected}
        signals={nextStepSignals}
      />

      {/* AI Suggestions */}
      <Box mt={2}>
        {filteredSignals.length > 0 ? (
          <Box mb={3}>
            <Typography
              variant="subtitle2"
              color="text.secondary"
              mb={1}
              fontWeight={600}
            >
              AI Suggestions
            </Typography>
            <Stack spacing={1.5}>
              {filteredSignals.map((signal) => (
                <AISuggestionCard
                  key={signal.id}
                  signal={signal}
                  onConvert={handleConvert}
                  onEdit={handleEdit}
                  onReject={handleReject}
                  onViewActivity={handleViewActivity}
                  onSelect={handleSelect}
                  isLocked={isLocked}
                />
              ))}
            </Stack>
          </Box>
        ) : (
          <Box py={4} textAlign="center">
            <Typography variant="body2" color="text.secondary">
              No suggestions match the current filter.
            </Typography>
          </Box>
        )}
      </Box>

      {/* Upcoming Activities section */}
      <Divider sx={{ my: 2 }} />
      <Typography variant="h6" sx={{ mb: 1.5 }}>
        <RocketOutlined style={{ fontSize: 18, marginRight: 8 }} />
        Upcoming Activities
      </Typography>
      <UpcomingActivitiesSection
        activity={activity}
        onCreateActivity={handleCreateActivity}
        isLocked={isLocked}
      />

      {/* Suggestion Drawer */}
      <NextStepSuggestionDrawer
        open={drawerOpen}
        signal={drawerSignal}
        onClose={handleCloseDrawer}
        onConvert={handleConvert}
        onReject={handleReject}
        onEdit={handleEdit}
        onViewActivity={handleViewActivity}
        isLocked={isLocked}
      />

      {/* Activity modal (convert from signal or manual add) */}
      {accountId && (
        <ActivityModal
          open={activityModalOpen}
          onClose={() => {
            setActivityModalOpen(false);
            setConvertSignal(null);
          }}
          activity={null}
          accountId={accountId}
          decisionStepId={activity?.decision_step || null}
          decisionCycleId={activity?.decision_cycle || null}
          defaultActivityType={convertSignal?.suggested_activity_type || "MEETING"}
          previousActivityId={activity?.id}
          nextStepSignal={convertSignal}
          onSuccess={handleConvertSuccess}
        />
      )}

      {/* Signal edit dialog */}
      <SignalEditDialog
        open={editDialogOpen}
        onClose={() => {
          setEditDialogOpen(false);
          setEditSignal(null);
        }}
        onSuccess={handleEditSuccess}
        signal={editSignal}
        signalType="next-steps"
        accountId={accountId || ""}
        choices={choices}
        choicesLoading={choicesLoading}
      />
    </Box>
  );
}

// ==============================|| PROP TYPES ||============================== //

ActivityNextStepsTab.propTypes = {
  activity: PropTypes.shape({
    id: PropTypes.string,
    account: PropTypes.string,
    status: PropTypes.string,
    decision_step: PropTypes.string,
    decision_cycle: PropTypes.string,
    sequence_context: PropTypes.object,
    campaign_detail: PropTypes.object,
  }),
  isLocked: PropTypes.bool,
  mutateCounts: PropTypes.func,
};
