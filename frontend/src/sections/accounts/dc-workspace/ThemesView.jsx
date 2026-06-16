// frontend/src/sections/accounts/dc-workspace/ThemesView.jsx

"use client";

import PropTypes from "prop-types";
import { useState, useCallback, useMemo } from "react";

// MUI
import Box from "@mui/material/Box";
import Chip from "@mui/material/Chip";
import CircularProgress from "@mui/material/CircularProgress";
import Stack from "@mui/material/Stack";
import Switch from "@mui/material/Switch";
import FormControlLabel from "@mui/material/FormControlLabel";
import ToggleButton from "@mui/material/ToggleButton";
import ToggleButtonGroup from "@mui/material/ToggleButtonGroup";
import Typography from "@mui/material/Typography";

// Icons
import { InboxOutlined } from "@ant-design/icons";

// Project imports
import {
  useGetClustersByAccount,
  archiveCluster,
  unarchiveCluster,
} from "api/signals/signalClusters";
import { useGetSignalChoices } from "api/signals/signals";
import SignalClusterCard from "components/cards/signals/SignalClusterCard";
import SignalClusterDetailDrawer from "sections/accounts/signals/SignalClusterDetailDrawer";
import {
  displaySuccessSnackbar,
  displayErrorSnackbar,
} from "utils/displayError";

// ==============================|| CONSTANTS ||============================== //

const TYPE_FILTER_OPTIONS = [
  { value: "all", label: "All", signalTypePayload: ["pain", "objective", "tech_stack"] },
  { value: "pain", label: "Pain", signalTypePayload: "pain" },
  { value: "objective", label: "Objective", signalTypePayload: "objective" },
  { value: "tech_stack", label: "Tech Stack", signalTypePayload: "tech_stack" },
];

const TYPE_FILTER_BY_VALUE = Object.fromEntries(
  TYPE_FILTER_OPTIONS.map((o) => [o.value, o]),
);

// ==============================|| THEMES VIEW ||============================== //

export default function ThemesView({ cycleId, accountId }) {
  // Filters
  const [typeFilter, setTypeFilter] = useState("all");
  const [includeArchived, setIncludeArchived] = useState(false);

  const signalTypePayload = useMemo(
    () => TYPE_FILTER_BY_VALUE[typeFilter].signalTypePayload,
    [typeFilter],
  );

  const { clusters, clustersLoading, clustersError, mutateClusters } =
    useGetClustersByAccount(accountId, {
      signalType: signalTypePayload,
      decisionCycleId: cycleId,
      includeArchived,
    });

  const { choices, choicesLoading } = useGetSignalChoices();

  // Drawer state
  const [drawerState, setDrawerState] = useState({
    open: false,
    clusterSummary: null,
  });

  const handleClusterClick = useCallback((cluster) => {
    setDrawerState({ open: true, clusterSummary: cluster });
  }, []);

  const handleDrawerClose = useCallback(() => {
    setDrawerState({ open: false, clusterSummary: null });
  }, []);

  const handleArchive = useCallback(
    async (cluster) => {
      const result = await archiveCluster(
        cluster.signal_type,
        cluster.canonical_key,
        accountId,
      );
      if (result.success) {
        displaySuccessSnackbar("Cluster archived");
        mutateClusters();
      } else {
        displayErrorSnackbar(result);
      }
    },
    [accountId, mutateClusters],
  );

  const handleUnarchive = useCallback(
    async (cluster) => {
      const result = await unarchiveCluster(
        cluster.signal_type,
        cluster.canonical_key,
        accountId,
      );
      if (result.success) {
        displaySuccessSnackbar("Cluster unarchived");
        mutateClusters();
      } else {
        displayErrorSnackbar(result);
      }
    },
    [accountId, mutateClusters],
  );

  // Loading
  if (clustersLoading) {
    return (
      <Box
        display="flex"
        justifyContent="center"
        alignItems="center"
        minHeight="200px"
      >
        <CircularProgress />
      </Box>
    );
  }

  // Error
  if (clustersError) {
    return (
      <Box
        display="flex"
        justifyContent="center"
        alignItems="center"
        minHeight="200px"
      >
        <Typography color="error">Failed to load themes</Typography>
      </Box>
    );
  }

  return (
    <Box>
      {/* Toolbar */}
      <Stack
        direction="row"
        justifyContent="space-between"
        alignItems="center"
        flexWrap="wrap"
        gap={1}
        sx={{ mb: 2 }}
      >
        <ToggleButtonGroup
          value={typeFilter}
          exclusive
          onChange={(_, v) => v && setTypeFilter(v)}
          size="small"
        >
          {TYPE_FILTER_OPTIONS.map((o) => (
            <ToggleButton key={o.value} value={o.value}>
              {o.label}
            </ToggleButton>
          ))}
        </ToggleButtonGroup>
        <FormControlLabel
          control={
            <Switch
              size="small"
              checked={includeArchived}
              onChange={(e) => setIncludeArchived(e.target.checked)}
            />
          }
          label={
            <Typography variant="caption" color="text.secondary">
              Show archived
            </Typography>
          }
        />
      </Stack>

      {/* Empty state */}
      {clusters.length === 0 ? (
        <Box
          display="flex"
          flexDirection="column"
          justifyContent="center"
          alignItems="center"
          minHeight="200px"
          gap={1}
        >
          <InboxOutlined style={{ fontSize: 36, color: "#8c8c8c" }} />
          <Typography color="text.secondary">
            No signal clusters for this cycle yet.
          </Typography>
          <Typography variant="caption" color="text.secondary">
            Clusters are formed from validated signals extracted in activities.
          </Typography>
        </Box>
      ) : (
        <>
          <Stack spacing={1.5}>
            {clusters.map((cluster) => (
              <SignalClusterCard
                key={`${cluster.signal_type}:${cluster.canonical_key}`}
                cluster={cluster}
                onClick={handleClusterClick}
                onArchive={handleArchive}
                onUnarchive={handleUnarchive}
              />
            ))}
          </Stack>
          <Chip
            label={`${clusters.length} cluster${clusters.length !== 1 ? "s" : ""}`}
            size="small"
            variant="outlined"
            sx={{ mt: 2 }}
          />
        </>
      )}

      {/* Cluster detail drawer */}
      <SignalClusterDetailDrawer
        open={drawerState.open}
        onClose={handleDrawerClose}
        clusterSummary={drawerState.clusterSummary}
        accountId={accountId}
        choices={choices}
        choicesLoading={choicesLoading}
        onClusterChange={mutateClusters}
      />
    </Box>
  );
}

ThemesView.propTypes = {
  cycleId: PropTypes.string.isRequired,
  accountId: PropTypes.string.isRequired,
};
