// frontend/src/sections/accounts/dc-workspace/DimensionDetailDrawer.jsx

"use client";

import PropTypes from "prop-types";

// MUI
import Box from "@mui/material/Box";
import Chip from "@mui/material/Chip";
import Divider from "@mui/material/Divider";
import Drawer from "@mui/material/Drawer";
import IconButton from "@mui/material/IconButton";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";

// Icons
import { CloseOutlined, QuestionCircleOutlined } from "@ant-design/icons";

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

const GAP_KIND_LABELS = {
  qualification: "Qualification gap",
  procedural: "Procedural gap",
};

// ==============================|| DIMENSION DETAIL DRAWER ||============================== //

export default function DimensionDetailDrawer({
  open,
  onClose,
  dimension,
  relatedGaps,
}) {
  if (!dimension) return null;

  const dimLabel = DIMENSION_LABELS[dimension.key] || dimension.key;
  const statusCfg = STATUS_CONFIG[dimension.status] || STATUS_CONFIG.missing_evidence;

  return (
    <Drawer
      anchor="right"
      open={open}
      onClose={onClose}
      PaperProps={{
        sx: { width: { xs: "100%", sm: 480 }, p: 3 },
      }}
    >
      {/* Header */}
      <Stack
        direction="row"
        justifyContent="space-between"
        alignItems="flex-start"
        sx={{ mb: 2.5 }}
      >
        <Box>
          <Typography variant="h6" fontWeight={600}>
            {dimLabel}
          </Typography>
          <Chip
            label={statusCfg.label}
            size="small"
            color={statusCfg.color}
            sx={{ mt: 0.75 }}
          />
        </Box>
        <IconButton size="small" onClick={onClose}>
          <CloseOutlined style={{ fontSize: 16 }} />
        </IconButton>
      </Stack>

      {/* Evidence */}
      <Box sx={{ mb: 2.5 }}>
        <Typography variant="subtitle2" fontWeight={600} sx={{ mb: 0.75 }}>
          Captured evidence
        </Typography>
        <Typography variant="body2" color="text.secondary">
          {dimension.evidence || "No evidence captured yet for this dimension."}
        </Typography>
      </Box>

      {/* What is not yet captured */}
      {dimension.missing && (
        <Box sx={{ mb: 2.5 }}>
          <Typography variant="subtitle2" fontWeight={600} sx={{ mb: 0.75 }}>
            Areas to explore
          </Typography>
          <Typography variant="body2" color="text.secondary">
            {dimension.missing}
          </Typography>
        </Box>
      )}

      {/* Related discovery gaps */}
      {relatedGaps && relatedGaps.length > 0 && (
        <>
          <Divider sx={{ my: 2 }} />
          <Typography variant="subtitle2" fontWeight={600} sx={{ mb: 1.5 }}>
            Related discovery gaps
          </Typography>
          <Stack spacing={2}>
            {relatedGaps.map((gap, idx) => (
              <Box
                key={idx}
                sx={{
                  p: 1.5,
                  border: 1,
                  borderColor: "divider",
                  borderRadius: 1.5,
                }}
              >
                <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 0.75 }}>
                  <Chip
                    label={GAP_KIND_LABELS[gap.kind] || gap.kind}
                    size="small"
                    variant="outlined"
                  />
                  {gap.related_actor && (
                    <Typography variant="caption" color="text.secondary">
                      {gap.related_actor}
                    </Typography>
                  )}
                </Stack>
                <Typography variant="body2" sx={{ mb: 1 }}>
                  {gap.public_text}
                </Typography>
                {gap.suggested_questions && gap.suggested_questions.length > 0 && (
                  <Stack spacing={0.5}>
                    <Typography variant="caption" color="text.secondary" fontWeight={600}>
                      Suggested questions
                    </Typography>
                    {gap.suggested_questions.map((q, qi) => (
                      <Stack key={qi} direction="row" spacing={0.75} alignItems="flex-start">
                        <QuestionCircleOutlined
                          style={{ fontSize: 12, marginTop: 4, color: "#8c8c8c" }}
                        />
                        <Typography variant="caption">{q}</Typography>
                      </Stack>
                    ))}
                  </Stack>
                )}
              </Box>
            ))}
          </Stack>
        </>
      )}
    </Drawer>
  );
}

DimensionDetailDrawer.propTypes = {
  open: PropTypes.bool.isRequired,
  onClose: PropTypes.func.isRequired,
  dimension: PropTypes.shape({
    key: PropTypes.string.isRequired,
    status: PropTypes.string.isRequired,
    evidence: PropTypes.string,
    missing: PropTypes.string,
  }),
  relatedGaps: PropTypes.arrayOf(
    PropTypes.shape({
      kind: PropTypes.string,
      dimension: PropTypes.string,
      public_text: PropTypes.string,
      suggested_questions: PropTypes.arrayOf(PropTypes.string),
      related_theme: PropTypes.string,
      related_actor: PropTypes.string,
    }),
  ),
};
