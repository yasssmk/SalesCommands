// frontend/src/sections/activities/signals/SignalsFilterPanel.jsx
//
// Standard filter drawer for the flat "Signals" views — mirrors the app's
// other filter panels (e.g. CampaignFilterPanel): a right-anchored Drawer with
// pending → Apply semantics, opened by a FilterOutlined icon in the toolbar.
//
// Filters wired to the aggregated endpoint /module-signals/all/:
//   - type   → signal_type (repeatable, multi-select over the surface's types)
//   - status → default PENDING + VALIDATED; an "Include rejected" toggle adds
//              REJECTED (the endpoint's `status` param).
//
// department / contact / scope / date range are intentionally absent: the
// aggregated endpoint has no backend param for them yet (adding them here
// would be dead filters). See the Temps-A report.

import PropTypes from "prop-types";

// material-ui
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Checkbox from "@mui/material/Checkbox";
import Drawer from "@mui/material/Drawer";
import FormControlLabel from "@mui/material/FormControlLabel";
import FormGroup from "@mui/material/FormGroup";
import IconButton from "@mui/material/IconButton";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";

// icons
import CloseOutlined from "@ant-design/icons/CloseOutlined";
import FilterOutlined from "@ant-design/icons/FilterOutlined";
import ClearOutlined from "@ant-design/icons/ClearOutlined";

// The frontend type slugs + their display labels (matches SignalTypeChip).
export const SIGNAL_TYPE_OPTIONS = [
  { value: "pain", label: "Pain" },
  { value: "objective", label: "Objective" },
  { value: "impact", label: "Impact" },
  { value: "tech-stack", label: "Tech Stack" },
  { value: "blockers", label: "Blocker" },
  { value: "next-steps", label: "Next Step" },
  { value: "people", label: "People" },
  { value: "constraints", label: "Constraint" },
];

// ==============================|| SIGNALS FILTER PANEL ||============================== //

export default function SignalsFilterPanel({
  open,
  onClose,
  availableTypes,
  pendingFilters,
  onFilterChange,
  onApply,
  onClear,
  hasPendingChanges,
}) {
  const typeOptions = SIGNAL_TYPE_OPTIONS.filter((o) =>
    availableTypes.includes(o.value),
  );

  const selectedTypes = pendingFilters?.types ?? [];

  const toggleType = (value) => (e) => {
    const next = e.target.checked
      ? [...selectedTypes, value]
      : selectedTypes.filter((t) => t !== value);
    onFilterChange("types", next);
  };

  const handleApply = () => {
    onApply?.();
    onClose?.();
  };

  return (
    <Drawer
      anchor="right"
      open={open}
      onClose={onClose}
      PaperProps={{ sx: { width: { xs: "100%", sm: 360 } } }}
    >
      {/* Header */}
      <Stack
        direction="row"
        justifyContent="space-between"
        alignItems="center"
        sx={{ p: 2, borderBottom: 1, borderColor: "divider" }}
      >
        <Stack direction="row" spacing={1} alignItems="center">
          <FilterOutlined style={{ fontSize: 20 }} />
          <Typography variant="h5">Filters</Typography>
        </Stack>
        <IconButton onClick={onClose} size="small" aria-label="Close filters">
          <CloseOutlined />
        </IconButton>
      </Stack>

      {/* Body */}
      <Box sx={{ flexGrow: 1, overflow: "auto", p: 2.5 }}>
        {/* Type — multi */}
        <Typography variant="subtitle2" sx={{ mb: 1 }}>
          Type
        </Typography>
        <FormGroup sx={{ mb: 3 }}>
          {typeOptions.map((o) => (
            <FormControlLabel
              key={o.value}
              control={
                <Checkbox
                  size="small"
                  checked={selectedTypes.includes(o.value)}
                  onChange={toggleType(o.value)}
                />
              }
              label={o.label}
            />
          ))}
        </FormGroup>

        {/* Status */}
        <Typography variant="subtitle2" sx={{ mb: 1 }}>
          Status
        </Typography>
        <Typography variant="caption" color="text.secondary" sx={{ display: "block", mb: 1 }}>
          Pending and validated signals are shown by default.
        </Typography>
        <FormControlLabel
          control={
            <Checkbox
              size="small"
              checked={Boolean(pendingFilters?.includeRejected)}
              onChange={(e) => onFilterChange("includeRejected", e.target.checked)}
            />
          }
          label="Include rejected"
        />
      </Box>

      {/* Footer */}
      <Box sx={{ borderTop: 1, borderColor: "divider", p: 2 }}>
        <Stack direction="row" spacing={1}>
          <Button
            fullWidth
            variant="outlined"
            color="secondary"
            startIcon={<ClearOutlined />}
            onClick={onClear}
          >
            Clear all
          </Button>
          <Button
            fullWidth
            variant="contained"
            onClick={handleApply}
            disabled={!hasPendingChanges}
          >
            Apply
          </Button>
        </Stack>
      </Box>
    </Drawer>
  );
}

SignalsFilterPanel.propTypes = {
  open: PropTypes.bool.isRequired,
  onClose: PropTypes.func.isRequired,
  /** Frontend type slugs available on this surface (drives the type list). */
  availableTypes: PropTypes.arrayOf(PropTypes.string).isRequired,
  pendingFilters: PropTypes.shape({
    types: PropTypes.arrayOf(PropTypes.string),
    includeRejected: PropTypes.bool,
  }),
  onFilterChange: PropTypes.func.isRequired,
  onApply: PropTypes.func.isRequired,
  onClear: PropTypes.func.isRequired,
  hasPendingChanges: PropTypes.bool,
};
