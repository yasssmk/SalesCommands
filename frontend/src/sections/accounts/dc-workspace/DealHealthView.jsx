// frontend/src/sections/accounts/dc-workspace/DealHealthView.jsx

"use client";

import PropTypes from "prop-types";
import { useState, useCallback, useMemo } from "react";

// MUI
import Box from "@mui/material/Box";
import Chip from "@mui/material/Chip";
import Divider from "@mui/material/Divider";
import Stack from "@mui/material/Stack";
import Tooltip from "@mui/material/Tooltip";
import Typography from "@mui/material/Typography";

// Icons
import {
  BulbOutlined,
  ClockCircleOutlined,
  FileSearchOutlined,
  RightOutlined,
  ThunderboltOutlined,
} from "@ant-design/icons";

// Project imports
import { useGetDealHealthHistory } from "api/aiPipelines/dealHealth";
import DimensionDetailDrawer from "./DimensionDetailDrawer";

// ==============================|| CONSTANTS ||============================== //

const DIMENSION_LABELS = {
  problem_recognized: "Problem Recognized",
  felt_pain: "Felt Pain",
  impact_understood: "Impact Understood",
  desired_gain: "Desired Gain",
  urgency: "Urgency",
  willingness_to_act: "Willingness to Act",
  solution_trust: "Solution Trust",
};

const STATUS_CONFIG = {
  confirmed: { label: "Confirmed", color: "success" },
  suggested: { label: "Suggested by evidence", color: "info" },
  unclear: { label: "Unclear", color: "warning" },
  missing_evidence: { label: "Evidence missing", color: "default" },
  contradictory: { label: "Contradictory evidence", color: "error" },
};

const LEVER_LABELS = {
  desires: "Desires",
  value: "Value drivers",
  cost: "Cost factors",
  constraints: "Constraints",
};

const LEVER_ICONS = {
  desires: <BulbOutlined style={{ fontSize: 14 }} />,
  value: <ThunderboltOutlined style={{ fontSize: 14 }} />,
  cost: <FileSearchOutlined style={{ fontSize: 14 }} />,
  constraints: <FileSearchOutlined style={{ fontSize: 14 }} />,
};

const GAP_KIND_LABELS = {
  qualification: "Qualification",
  procedural: "Procedural",
};

// ==============================|| DEAL HEALTH VIEW ||============================== //

export default function DealHealthView({ snapshot, cycleId }) {
  const diagnostic = snapshot?.diagnostic;

  const { snapshots: history } = useGetDealHealthHistory(cycleId);

  // Drawer state
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [selectedDim, setSelectedDim] = useState(null);
  const [relatedGaps, setRelatedGaps] = useState([]);

  const handleDimClick = useCallback(
    (dim) => {
      setSelectedDim(dim);
      const gaps = (diagnostic?.discovery_gaps || []).filter(
        (g) => g.dimension === dim.key,
      );
      setRelatedGaps(gaps);
      setDrawerOpen(true);
    },
    [diagnostic],
  );

  const handleCloseDrawer = useCallback(() => {
    setDrawerOpen(false);
    setSelectedDim(null);
    setRelatedGaps([]);
  }, []);

  // Fallback if diagnostic is missing
  if (!diagnostic) {
    return (
      <Typography color="text.secondary" sx={{ py: 3, textAlign: "center" }}>
        No diagnostic data available.
      </Typography>
    );
  }

  const dimensions = diagnostic.dimensions || [];
  const gaps = diagnostic.discovery_gaps || [];
  const levers = diagnostic.levers || {};
  const themes = diagnostic.themes || [];
  const evidenceScope = diagnostic.evidence_scope || {};

  const qualGaps = gaps.filter((g) => g.kind === "qualification");
  const procGaps = gaps.filter((g) => g.kind === "procedural");

  return (
    <Box>
      {/* Evidence scope badge */}
      <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 2 }}>
        <Chip
          label={`Based on ${evidenceScope.validated_signals_count ?? "—"} validated signals`}
          size="small"
          variant="outlined"
        />
        {snapshot?.snapshot_date && (
          <Typography variant="caption" color="text.secondary">
            <ClockCircleOutlined style={{ fontSize: 11, marginRight: 4 }} />
            {new Date(snapshot.snapshot_date).toLocaleDateString("en-US", {
              month: "short",
              day: "numeric",
              year: "numeric",
              hour: "2-digit",
              minute: "2-digit",
            })}
          </Typography>
        )}
      </Stack>

      {/* Global reading */}
      {diagnostic.global_reading && (
        <Box
          sx={{
            p: 2,
            mb: 3,
            borderRadius: 1.5,
            bgcolor: "action.hover",
          }}
        >
          <Typography variant="body2">{diagnostic.global_reading}</Typography>
        </Box>
      )}

      {/* 7 Dimensions */}
      <Typography variant="subtitle2" fontWeight={600} sx={{ mb: 1.5 }}>
        Deal maturity dimensions
      </Typography>
      <Stack spacing={1} sx={{ mb: 3 }}>
        {dimensions.map((dim) => {
          const label = DIMENSION_LABELS[dim.key] || dim.key;
          const cfg = STATUS_CONFIG[dim.status] || STATUS_CONFIG.missing_evidence;
          return (
            <Box
              key={dim.key}
              onClick={() => handleDimClick(dim)}
              sx={{
                p: 1.5,
                border: 1,
                borderColor: "divider",
                borderRadius: 1.5,
                cursor: "pointer",
                "&:hover": { bgcolor: "action.hover" },
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
              }}
            >
              <Stack direction="row" spacing={1.5} alignItems="center">
                <Typography variant="body2" fontWeight={500} sx={{ minWidth: 160 }}>
                  {label}
                </Typography>
                <Chip label={cfg.label} size="small" color={cfg.color} />
              </Stack>
              <RightOutlined style={{ fontSize: 12, color: "#8c8c8c" }} />
            </Box>
          );
        })}
      </Stack>

      {/* Discovery gaps */}
      {gaps.length > 0 && (
        <>
          <Divider sx={{ my: 2.5 }} />
          <Typography variant="subtitle2" fontWeight={600} sx={{ mb: 1.5 }}>
            Areas to clarify
          </Typography>
          {qualGaps.length > 0 && (
            <GapSection title="Qualification" gaps={qualGaps} />
          )}
          {procGaps.length > 0 && (
            <GapSection title="Procedural" gaps={procGaps} />
          )}
        </>
      )}

      {/* Strategic levers */}
      {Object.keys(levers).some((k) => (levers[k] || []).length > 0) && (
        <>
          <Divider sx={{ my: 2.5 }} />
          <Typography variant="subtitle2" fontWeight={600} sx={{ mb: 1.5 }}>
            Strategic levers
          </Typography>
          <Stack spacing={2}>
            {["desires", "value", "cost", "constraints"].map((group) => {
              const items = levers[group] || [];
              if (items.length === 0) return null;
              return (
                <Box key={group}>
                  <Stack direction="row" spacing={0.75} alignItems="center" sx={{ mb: 0.75 }}>
                    {LEVER_ICONS[group]}
                    <Typography variant="caption" fontWeight={600} sx={{ textTransform: "uppercase" }}>
                      {LEVER_LABELS[group]}
                    </Typography>
                  </Stack>
                  <Stack spacing={0.5} sx={{ pl: 2.5 }}>
                    {items.map((item, idx) => (
                      <Stack key={idx} direction="row" spacing={1} alignItems="baseline">
                        <Typography variant="body2" color="text.secondary">
                          •
                        </Typography>
                        <Box>
                          <Typography variant="body2">{item.summary}</Typography>
                          {item.theme && (
                            <Typography variant="caption" color="text.secondary">
                              Theme: {item.theme}
                            </Typography>
                          )}
                          {item.actor && (
                            <Typography variant="caption" color="text.secondary">
                              Actor: {item.actor}
                            </Typography>
                          )}
                          {item.rigidity && (
                            <Chip
                              label={item.rigidity}
                              size="small"
                              variant="outlined"
                              sx={{ ml: 0.5, height: 18, fontSize: "0.65rem" }}
                            />
                          )}
                        </Box>
                      </Stack>
                    ))}
                  </Stack>
                </Box>
              );
            })}
          </Stack>
        </>
      )}

      {/* Diagnostic themes (from LLM) */}
      {themes.length > 0 && (
        <>
          <Divider sx={{ my: 2.5 }} />
          <Typography variant="subtitle2" fontWeight={600} sx={{ mb: 1.5 }}>
            Diagnostic themes
          </Typography>
          <Stack spacing={1}>
            {themes.map((t, idx) => (
              <Box
                key={idx}
                sx={{ p: 1.5, border: 1, borderColor: "divider", borderRadius: 1.5 }}
              >
                <Typography variant="body2" fontWeight={500}>
                  {t.label}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  {t.summary}
                </Typography>
              </Box>
            ))}
          </Stack>
        </>
      )}

      {/* Snapshot history */}
      {history && history.length > 1 && (
        <>
          <Divider sx={{ my: 2.5 }} />
          <Typography variant="subtitle2" fontWeight={600} sx={{ mb: 1 }}>
            Previous diagnostics
          </Typography>
          <Stack spacing={0.5}>
            {history.slice(1, 6).map((s) => (
              <Stack key={s.id} direction="row" spacing={1} alignItems="center">
                <ClockCircleOutlined style={{ fontSize: 12, color: "#8c8c8c" }} />
                <Typography variant="caption" color="text.secondary">
                  {new Date(s.snapshot_date).toLocaleDateString("en-US", {
                    month: "short",
                    day: "numeric",
                    year: "numeric",
                    hour: "2-digit",
                    minute: "2-digit",
                  })}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  — {s.diagnostic?.evidence_scope?.validated_signals_count ?? "?"} signals
                </Typography>
              </Stack>
            ))}
          </Stack>
        </>
      )}

      {/* Dimension Detail Drawer */}
      <DimensionDetailDrawer
        open={drawerOpen}
        onClose={handleCloseDrawer}
        dimension={selectedDim}
        relatedGaps={relatedGaps}
      />
    </Box>
  );
}

// ==============================|| GAP SECTION ||============================== //

function GapSection({ title, gaps }) {
  return (
    <Box sx={{ mb: 2 }}>
      <Typography
        variant="caption"
        color="text.secondary"
        fontWeight={600}
        sx={{ mb: 0.75, display: "block", textTransform: "uppercase" }}
      >
        {title}
      </Typography>
      <Stack spacing={1}>
        {gaps.map((gap, idx) => (
          <Box
            key={idx}
            sx={{
              p: 1.5,
              border: 1,
              borderColor: "divider",
              borderRadius: 1.5,
              borderStyle: "dashed",
            }}
          >
            <Typography variant="body2">{gap.public_text}</Typography>
            {gap.related_actor && (
              <Typography variant="caption" color="text.secondary" sx={{ mt: 0.5, display: "block" }}>
                {gap.related_actor}
              </Typography>
            )}
          </Box>
        ))}
      </Stack>
    </Box>
  );
}

GapSection.propTypes = {
  title: PropTypes.string.isRequired,
  gaps: PropTypes.array.isRequired,
};

DealHealthView.propTypes = {
  snapshot: PropTypes.shape({
    id: PropTypes.string,
    diagnostic: PropTypes.shape({
      global_reading: PropTypes.string,
      dimensions: PropTypes.arrayOf(
        PropTypes.shape({
          key: PropTypes.string,
          status: PropTypes.string,
          evidence: PropTypes.string,
          missing: PropTypes.string,
        }),
      ),
      discovery_gaps: PropTypes.arrayOf(PropTypes.object),
      levers: PropTypes.shape({
        desires: PropTypes.array,
        value: PropTypes.array,
        cost: PropTypes.array,
        constraints: PropTypes.array,
      }),
      themes: PropTypes.arrayOf(
        PropTypes.shape({
          label: PropTypes.string,
          summary: PropTypes.string,
        }),
      ),
      evidence_scope: PropTypes.shape({
        validated_signals_count: PropTypes.number,
        note: PropTypes.string,
      }),
    }),
    snapshot_date: PropTypes.string,
  }),
  cycleId: PropTypes.string.isRequired,
};
