// frontend/src/sections/accounts/dc-workspace/StepDetailDrawer.jsx
/**
 * Quick-view drawer for a pipeline step's metadata.
 *
 * Shows goal, description, criterias, and metrics as read from the
 * timeline serializer payload — no extra API call.
 */

"use client";

import PropTypes from "prop-types";

// MUI
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Chip from "@mui/material/Chip";
import Divider from "@mui/material/Divider";
import Drawer from "@mui/material/Drawer";
import IconButton from "@mui/material/IconButton";
import List from "@mui/material/List";
import ListItem from "@mui/material/ListItem";
import ListItemIcon from "@mui/material/ListItemIcon";
import ListItemText from "@mui/material/ListItemText";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";

// Icons
import {
  AimOutlined,
  CheckSquareOutlined,
  CloseOutlined,
  DashboardOutlined,
  FileTextOutlined,
  LoginOutlined,
} from "@ant-design/icons";

// Project imports
import DrawerFieldRow from "components/display/DrawerFieldRow";
import DrawerSection from "components/display/DrawerSection";
import {
  PIPELINE_STEP_CONFIG,
  PIPELINE_STEP_LABELS,
} from "api/accounts/decisionCycles";

const DRAWER_WIDTH = 420;

// ==============================|| STEP DETAIL DRAWER ||============================== //

export default function StepDetailDrawer({ open, step, onClose, onGoToStep }) {
  if (!step) return null;

  const stageConfig = PIPELINE_STEP_CONFIG[step.stage] || {};
  const stageLabel = PIPELINE_STEP_LABELS[step.stage] || step.name;
  const criterias = Array.isArray(step.criterias) ? step.criterias : [];
  const metrics = Array.isArray(step.metrics) ? step.metrics : [];

  return (
    <Drawer
      anchor="right"
      open={open}
      onClose={onClose}
      PaperProps={{ sx: { width: DRAWER_WIDTH } }}
    >
      {/* Header */}
      <Stack
        direction="row"
        justifyContent="space-between"
        alignItems="center"
        sx={{ px: 2.5, py: 2 }}
      >
        <Stack spacing={0.25}>
          <Typography variant="h6" fontWeight={600}>
            {step.name}
          </Typography>
          {step.derived_status_display && (
            <Chip
              label={step.derived_status_display}
              size="small"
              variant="outlined"
              sx={
                step.derived_status_color
                  ? {
                      borderColor: step.derived_status_color,
                      color: step.derived_status_color,
                    }
                  : undefined
              }
            />
          )}
        </Stack>
        <IconButton size="small" onClick={onClose}>
          <CloseOutlined />
        </IconButton>
      </Stack>

      <Divider />

      {/* Body */}
      <Box sx={{ px: 2.5, py: 2, overflowY: "auto", flex: 1 }}>
        {/* Stage info */}
        <DrawerSection title="Stage">
          <DrawerFieldRow label="Stage" value={stageLabel} />
          <DrawerFieldRow label="Order" value={`${step.order ?? "—"} / 5`} />
          {stageConfig.description && (
            <DrawerFieldRow label="Purpose" value={stageConfig.description} />
          )}
        </DrawerSection>

        {/* Goal */}
        {step.goal && (
          <DrawerSection title="Goal">
            <Stack direction="row" spacing={1} alignItems="flex-start">
              <AimOutlined
                style={{ fontSize: 16, marginTop: 2, flexShrink: 0 }}
              />
              <Typography variant="body2">{step.goal}</Typography>
            </Stack>
          </DrawerSection>
        )}

        {/* Description */}
        {step.description && (
          <DrawerSection title="Description">
            <Stack direction="row" spacing={1} alignItems="flex-start">
              <FileTextOutlined
                style={{ fontSize: 16, marginTop: 2, flexShrink: 0 }}
              />
              <Typography variant="body2">{step.description}</Typography>
            </Stack>
          </DrawerSection>
        )}

        {/* Criterias */}
        {criterias.length > 0 && (
          <DrawerSection title="Criterias">
            <List dense disablePadding>
              {criterias.map((item, idx) => (
                <ListItem key={idx} disableGutters sx={{ py: 0.25 }}>
                  <ListItemIcon sx={{ minWidth: 28 }}>
                    <CheckSquareOutlined style={{ fontSize: 14 }} />
                  </ListItemIcon>
                  <ListItemText
                    primary={typeof item === "string" ? item : item.label || JSON.stringify(item)}
                    primaryTypographyProps={{ variant: "body2" }}
                  />
                </ListItem>
              ))}
            </List>
          </DrawerSection>
        )}

        {/* Metrics */}
        {metrics.length > 0 && (
          <DrawerSection title="Metrics">
            <List dense disablePadding>
              {metrics.map((item, idx) => (
                <ListItem key={idx} disableGutters sx={{ py: 0.25 }}>
                  <ListItemIcon sx={{ minWidth: 28 }}>
                    <DashboardOutlined style={{ fontSize: 14 }} />
                  </ListItemIcon>
                  <ListItemText
                    primary={typeof item === "string" ? item : item.label || JSON.stringify(item)}
                    primaryTypographyProps={{ variant: "body2" }}
                  />
                </ListItem>
              ))}
            </List>
          </DrawerSection>
        )}

        {/* Empty state when no metadata */}
        {!step.goal && !step.description && criterias.length === 0 && metrics.length === 0 && (
          <Box sx={{ textAlign: "center", py: 4 }}>
            <Typography color="text.secondary" variant="body2">
              No goal, criterias, or metrics defined for this step yet.
            </Typography>
          </Box>
        )}
      </Box>

      <Divider />

      {/* Footer */}
      <Box sx={{ px: 2.5, py: 1.5 }}>
        <Button
          fullWidth
          variant="outlined"
          startIcon={<LoginOutlined />}
          onClick={() => {
            onGoToStep?.(step);
            onClose();
          }}
        >
          Open Step Workspace
        </Button>
      </Box>
    </Drawer>
  );
}

StepDetailDrawer.propTypes = {
  open: PropTypes.bool.isRequired,
  step: PropTypes.object,
  onClose: PropTypes.func.isRequired,
  onGoToStep: PropTypes.func,
};
