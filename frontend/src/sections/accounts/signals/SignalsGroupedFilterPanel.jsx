// frontend/src/sections/accounts/signals/SignalsGroupedFilterPanel.jsx
//
// Filter drawer for the GROUPED (cluster) Qualification view. Structured as
// themed MUI Accordion sections by family:
//   - "Qualification" (open by default) — the filters the cluster endpoint
//     honors: Perimeter (unified scope=BUSINESS OR department), Contact (source,
//     multi), Domain (`what`), Dimension, Status.
//   - "Tech Stack" / "Objection" — empty placeholders; their filters arrive with
//     those families in a later step.
//
// Reuses components/filters/MultiSelectFilter (Autocomplete multiple) for the
// controlled multi-selects and AsyncContactSelect (multiple) for the async
// contact search. The flat view keeps its own SignalsFilterPanel untouched.

import PropTypes from "prop-types";

// material-ui
import Accordion from "@mui/material/Accordion";
import AccordionDetails from "@mui/material/AccordionDetails";
import AccordionSummary from "@mui/material/AccordionSummary";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Drawer from "@mui/material/Drawer";
import IconButton from "@mui/material/IconButton";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";

// project imports
import MultiSelectFilter from "components/filters/MultiSelectFilter";
import AsyncContactSelect from "components/AsyncSelection/AsyncContactSelect";

// icons
import CloseOutlined from "@ant-design/icons/CloseOutlined";
import DownOutlined from "@ant-design/icons/DownOutlined";
import FilterOutlined from "@ant-design/icons/FilterOutlined";
import ClearOutlined from "@ant-design/icons/ClearOutlined";

// ==============================|| OPTION LISTS (controlled enums) ||============================== //

// Mirror SignalWhat / SignalDimension / SignalStatus on the backend.
const WHAT_OPTIONS = [
  { value: "OPS", label: "Operations / Process" },
  { value: "TECH", label: "Technology / System" },
  { value: "DATA", label: "Data / Visibility" },
  { value: "PEOPLE", label: "People / Org" },
  { value: "GROWTH", label: "Growth / Revenue" },
];

const DIMENSION_OPTIONS = [
  { value: "TIME", label: "Time / Speed" },
  { value: "COST", label: "Cost / Budget" },
  { value: "QUALITY", label: "Quality / Accuracy" },
  { value: "SCALE", label: "Scale / Capacity" },
  { value: "RISK", label: "Risk / Compliance" },
];

const STATUS_OPTIONS = [
  { value: "PENDING", label: "Pending" },
  { value: "VALIDATED", label: "Validated" },
  { value: "REJECTED", label: "Rejected" },
];

// Mirror ConstraintNature on the backend (and the CONSTRAINT_NATURES labels in
// QualificationGroupedView). The constraint clusters group on `nature`; this
// multi-select filters that family (OR within, AND across families).
const NATURE_OPTIONS = [
  { value: "FUNCTIONAL", label: "Functional" },
  { value: "TECHNICAL", label: "Technical" },
  { value: "FINANCIAL", label: "Financial" },
  { value: "CONTRACTUAL", label: "Contractual & Legal" },
  { value: "OPERATIONAL", label: "Operational" },
  { value: "SECURITY", label: "Security" },
];

// ==============================|| GROUPED FILTER PANEL ||============================== //

export default function SignalsGroupedFilterPanel({
  open,
  onClose,
  perimeterOptions = [],
  contactFilters = {},
  value,
  onChange,
  onClear,
  activeCount = 0,
  showConstraint = false,
}) {
  const set = (field) => (newValue) => onChange?.(field, newValue);

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

      {/* Body — accordion sections by family */}
      <Box sx={{ flexGrow: 1, overflow: "auto" }}>
        {/* ==================== QUALIFICATION ==================== */}
        <Accordion defaultExpanded disableGutters>
          <AccordionSummary expandIcon={<DownOutlined />}>
            <Typography variant="subtitle1">Qualification</Typography>
          </AccordionSummary>
          <AccordionDetails>
            <Stack spacing={2.5}>
              {/* Perimeter — Business + departments, one merged multi list. */}
              <MultiSelectFilter
                label="Perimeter"
                placeholder="Any perimeter"
                options={perimeterOptions}
                value={value?.perimeter ?? []}
                onChange={set("perimeter")}
                size="small"
                allLabel="All perimeters"
              />

              {/* Contact — async multi (who reported it). */}
              <AsyncContactSelect
                multiple
                value={value?.contacts ?? []}
                onChange={(_e, contacts) => onChange?.("contacts", contacts)}
                label="Contact"
                placeholder="Any contact"
                filters={contactFilters}
                size="small"
              />

              {/* Domain (`what`). */}
              <MultiSelectFilter
                label="Domain"
                placeholder="Any domain"
                options={WHAT_OPTIONS}
                value={value?.whats ?? []}
                onChange={set("whats")}
                size="small"
                allLabel="All domains"
              />

              {/* Dimension. */}
              <MultiSelectFilter
                label="Dimension"
                placeholder="Any dimension"
                options={DIMENSION_OPTIONS}
                value={value?.dimensions ?? []}
                onChange={set("dimensions")}
                size="small"
                allLabel="All dimensions"
              />

              {/* Status — default pending + validated. */}
              <MultiSelectFilter
                label="Status"
                placeholder="Any status"
                options={STATUS_OPTIONS}
                value={value?.statuses ?? []}
                onChange={set("statuses")}
                size="small"
                allLabel="All statuses"
              />
            </Stack>
          </AccordionDetails>
        </Accordion>

        {/* ==================== TECH STACK (placeholder) ==================== */}
        <Accordion disableGutters>
          <AccordionSummary expandIcon={<DownOutlined />}>
            <Typography variant="subtitle1">Tech Stack</Typography>
          </AccordionSummary>
          <AccordionDetails>
            <Typography variant="body2" color="text.secondary">
              Filters for the Tech Stack family come with the Tech step.
            </Typography>
          </AccordionDetails>
        </Accordion>

        {/* ==================== OBJECTION (placeholder) ==================== */}
        <Accordion disableGutters>
          <AccordionSummary expandIcon={<DownOutlined />}>
            <Typography variant="subtitle1">Objection</Typography>
          </AccordionSummary>
          <AccordionDetails>
            <Typography variant="body2" color="text.secondary">
              Filters for the Objection family come with the Objection step.
            </Typography>
          </AccordionDetails>
        </Accordion>

        {/* ==================== CONSTRAINT ==================== */}
        {/* Constraints cluster on `nature` and are DC-SCOPED, so the section is
            shown only where constraints render (the DC surface). This
            multi-select is the constraint-family analogue of Domain/Dimension:
            it narrows the constraint clusters only. */}
        {showConstraint && (
          <Accordion disableGutters>
            <AccordionSummary expandIcon={<DownOutlined />}>
              <Typography variant="subtitle1">Constraint</Typography>
            </AccordionSummary>
            <AccordionDetails>
              <MultiSelectFilter
                label="Nature"
                placeholder="Any nature"
                options={NATURE_OPTIONS}
                value={value?.natures ?? []}
                onChange={set("natures")}
                size="small"
                allLabel="All natures"
              />
            </AccordionDetails>
          </Accordion>
        )}
      </Box>

      {/* Footer */}
      <Box sx={{ borderTop: 1, borderColor: "divider", p: 2 }}>
        <Button
          fullWidth
          variant="outlined"
          color="inherit"
          startIcon={<ClearOutlined />}
          onClick={onClear}
          disabled={activeCount === 0}
        >
          Clear all
        </Button>
      </Box>
    </Drawer>
  );
}

// ==============================|| PROP TYPES ||============================== //

SignalsGroupedFilterPanel.propTypes = {
  open: PropTypes.bool.isRequired,
  onClose: PropTypes.func.isRequired,
  /** Perimeter options: [{ value:'BUSINESS', label:'Business' }, ...departments]. */
  perimeterOptions: PropTypes.arrayOf(
    PropTypes.shape({ value: PropTypes.any, label: PropTypes.string }),
  ),
  /** Scope for the contact search (e.g. { account_id }). */
  contactFilters: PropTypes.object,
  /** { perimeter:[], contacts:[objects], whats:[], dimensions:[], natures:[], statuses:[] }. */
  value: PropTypes.object.isRequired,
  /** (field, newValue) => void. */
  onChange: PropTypes.func.isRequired,
  onClear: PropTypes.func.isRequired,
  activeCount: PropTypes.number,
  /** Show the Constraint (Nature) section — DC surface only (constraints are
   *  DC-scoped). Off elsewhere so the Account/Activity panels are unchanged. */
  showConstraint: PropTypes.bool,
};
