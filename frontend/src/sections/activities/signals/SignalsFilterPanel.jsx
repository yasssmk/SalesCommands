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
import FormControl from "@mui/material/FormControl";
import FormControlLabel from "@mui/material/FormControlLabel";
import FormGroup from "@mui/material/FormGroup";
import IconButton from "@mui/material/IconButton";
import InputLabel from "@mui/material/InputLabel";
import MenuItem from "@mui/material/MenuItem";
import Select from "@mui/material/Select";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";

// project imports
import AsyncContactSelect from "components/AsyncSelection/AsyncContactSelect";

// icons
import CloseOutlined from "@ant-design/icons/CloseOutlined";
import FilterOutlined from "@ant-design/icons/FilterOutlined";
import ClearOutlined from "@ant-design/icons/ClearOutlined";

const SCOPE_OPTIONS = [
  { value: "", label: "Any scope" },
  { value: "BUSINESS", label: "Business" },
  { value: "DEPARTMENT", label: "Department" },
];

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
  { value: "competitors", label: "Competitor" },
];

// ==============================|| SIGNALS FILTER PANEL ||============================== //

export default function SignalsFilterPanel({
  open,
  onClose,
  availableTypes,
  departmentOptions = [],
  contactFilters = {},
  pendingFilters,
  onFilterChange,
  onApply,
  onClear,
  hasPendingChanges,
  mode = "flat",
  groupedFilters = false,
}) {
  // Status / department / contact / scope are shown on the Flat view, and on
  // the Grouped view WHEN that grouped surface honors them (groupedFilters) —
  // true for the cluster-backed Qualification view (Account / DC), whose
  // endpoint now filters members by department/contact/scope/status. It stays
  // false for grouped surfaces that cannot honor them, so no dead controls are
  // ever rendered (the C6 no-dead-filter rule). Type always renders on both.
  const isGrouped = mode === "grouped";
  const showSecondaryFilters = !isGrouped || groupedFilters;

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

        {/* Status / Department / Contact / Scope — shown on Flat, and on
            Grouped when that surface honors them (groupedFilters). Type above
            applies to both views. */}
        {showSecondaryFilters && (
          <>
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

            {/* Department — only pain/objective/impact/people/constraints carry
                target_department; other types are excluded when this is set. */}
            <FormControl fullWidth size="small" sx={{ mt: 3 }}>
              <InputLabel id="signal-department-label">Department</InputLabel>
              <Select
                labelId="signal-department-label"
                label="Department"
                value={pendingFilters?.department ?? ""}
                onChange={(e) => onFilterChange("department", e.target.value)}
              >
                <MenuItem value="">Any department</MenuItem>
                {departmentOptions.map((o) => (
                  <MenuItem key={o.value} value={o.value}>
                    {o.label}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>

            {/* Contact — signals whose origin activity includes this contact. */}
            <Box sx={{ mt: 2.5 }}>
              <AsyncContactSelect
                value={pendingFilters?.contact ?? null}
                onChange={(_e, c) => onFilterChange("contact", c || null)}
                label="Contact"
                placeholder="Any contact"
                filters={contactFilters}
                size="small"
              />
            </Box>

            {/* Scope — only pain/objective/impact carry scope_level. */}
            <FormControl fullWidth size="small" sx={{ mt: 2.5 }}>
              <InputLabel id="signal-scope-label">Scope</InputLabel>
              <Select
                labelId="signal-scope-label"
                label="Scope"
                value={pendingFilters?.scope ?? ""}
                onChange={(e) => onFilterChange("scope", e.target.value)}
              >
                {SCOPE_OPTIONS.map((o) => (
                  <MenuItem key={o.value || "any"} value={o.value}>
                    {o.label}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          </>
        )}
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
  /** StandardDepartment options ({ value, label }) for the department filter. */
  departmentOptions: PropTypes.arrayOf(
    PropTypes.shape({ value: PropTypes.any, label: PropTypes.string }),
  ),
  /** Scope for the contact search (e.g. { account_id }). */
  contactFilters: PropTypes.object,
  pendingFilters: PropTypes.shape({
    types: PropTypes.arrayOf(PropTypes.string),
    includeRejected: PropTypes.bool,
    department: PropTypes.any,
    contact: PropTypes.object,
    scope: PropTypes.string,
  }),
  onFilterChange: PropTypes.func.isRequired,
  onApply: PropTypes.func.isRequired,
  onClear: PropTypes.func.isRequired,
  hasPendingChanges: PropTypes.bool,
  /** "flat" (default) shows all controls; "grouped" shows only Type. */
  mode: PropTypes.oneOf(["flat", "grouped"]),
  /** When true, the secondary filters (status/department/contact/scope) also
      render in Grouped mode — set by cluster-backed grouped surfaces that
      honor them (Account / DC). */
  groupedFilters: PropTypes.bool,
};
