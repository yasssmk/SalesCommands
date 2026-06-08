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
import LinkedActivityCard from "components/cards/nextSteps/LinkedActivityCard";
import NextStepsFilterBar from "sections/activities/nextSteps/NextStepsFilterBar";
import ActivityModal from "sections/accounts/activities/ActivityModal";
import SignalEditDialog from "sections/activities/signals/SignalEditDialog";

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

  // Activity modal state (convert from signal OR manual add)
  const [activityModalOpen, setActivityModalOpen] = useState(false);
  const [convertSignal, setConvertSignal] = useState(null);

  // Edit dialog state
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [editSignal, setEditSignal] = useState(null);

  // ==============================|| FILTERED SIGNALS ||============================== //

  const filteredSignals = useMemo(() => {
    if (!nextStepSignals) return [];

    return nextStepSignals.filter((s) => {
      if (s.status === "REJECTED") return includeRejected;

      if (activeFilter === "all-active") {
        return s.status === "PENDING" || s.status === "VALIDATED";
      }
      return s.status === activeFilter;
    });
  }, [nextStepSignals, activeFilter, includeRejected]);

  // Separate PENDING (AI Suggestions) from VALIDATED (with linked activity)
  const pendingSignals = useMemo(
    () => filteredSignals.filter((s) => s.status === "PENDING"),
    [filteredSignals],
  );

  const convertedSignals = useMemo(
    () => filteredSignals.filter((s) => s.status === "VALIDATED"),
    [filteredSignals],
  );

  const rejectedSignals = useMemo(
    () => filteredSignals.filter((s) => s.status === "REJECTED"),
    [filteredSignals],
  );

  // Linked activities from converted signals
  const linkedActivities = useMemo(
    () =>
      convertedSignals
        .map((s) => s.linked_activity)
        .filter(Boolean),
    [convertedSignals],
  );

  // ==============================|| HANDLERS ||============================== //

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
      } else {
        displayErrorSnackbar(result);
      }
    },
    [mutateAll, mutateCounts],
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
        {pendingSignals.length > 0 &&
          `${pendingSignals.length} AI suggestion${pendingSignals.length > 1 ? "s" : ""} to handle`}
        {pendingSignals.length > 0 && linkedActivities.length > 0 && " · "}
        {linkedActivities.length > 0 &&
          `${linkedActivities.length} activit${linkedActivities.length > 1 ? "ies" : "y"} created`}
      </Typography>

      {/* Filter bar */}
      <NextStepsFilterBar
        activeFilter={activeFilter}
        onChange={setActiveFilter}
        includeRejected={includeRejected}
        onToggleRejected={setIncludeRejected}
        signals={nextStepSignals}
      />

      <Box mt={2}>
        {/* Section — AI Suggestions (PENDING) */}
        {pendingSignals.length > 0 && (
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
              {pendingSignals.map((signal) => (
                <AISuggestionCard
                  key={signal.id}
                  signal={signal}
                  onConvert={handleConvert}
                  onEdit={handleEdit}
                  onReject={handleReject}
                  isLocked={isLocked}
                />
              ))}
            </Stack>
          </Box>
        )}

        {/* Section — Converted (VALIDATED with linked activity) */}
        {convertedSignals.length > 0 && (
          <Box mb={3}>
            {pendingSignals.length > 0 && <Divider sx={{ mb: 2 }} />}
            <Typography
              variant="subtitle2"
              color="text.secondary"
              mb={1}
              fontWeight={600}
            >
              Linked Activities
            </Typography>
            <Stack spacing={1.5}>
              {convertedSignals.map((signal) =>
                signal.linked_activity ? (
                  <LinkedActivityCard
                    key={signal.id}
                    activity={signal.linked_activity}
                    onOpen={handleViewActivity}
                  />
                ) : (
                  <AISuggestionCard
                    key={signal.id}
                    signal={signal}
                    onEdit={handleEdit}
                    onViewActivity={handleViewActivity}
                    isLocked={isLocked}
                  />
                ),
              )}
            </Stack>
          </Box>
        )}

        {/* Section — Rejected (only if includeRejected) */}
        {rejectedSignals.length > 0 && (
          <Box mb={3}>
            {(pendingSignals.length > 0 || convertedSignals.length > 0) && (
              <Divider sx={{ mb: 2 }} />
            )}
            <Typography
              variant="subtitle2"
              color="text.secondary"
              mb={1}
              fontWeight={600}
            >
              Rejected
            </Typography>
            <Stack spacing={1.5}>
              {rejectedSignals.map((signal) => (
                <AISuggestionCard
                  key={signal.id}
                  signal={signal}
                  onEdit={handleEdit}
                  isLocked={isLocked}
                />
              ))}
            </Stack>
          </Box>
        )}

        {/* Empty filtered state */}
        {filteredSignals.length === 0 && (
          <Box py={4} textAlign="center">
            <Typography variant="body2" color="text.secondary">
              No suggestions match the current filter.
            </Typography>
          </Box>
        )}
      </Box>

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
  }),
  isLocked: PropTypes.bool,
  mutateCounts: PropTypes.func,
};
