// frontend/src/sections/activities/signals/SignalQuickDrawer.jsx

"use client";

import PropTypes from "prop-types";

// MUI
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Chip from "@mui/material/Chip";
import Divider from "@mui/material/Divider";
import Drawer from "@mui/material/Drawer";
import IconButton from "@mui/material/IconButton";
import Stack from "@mui/material/Stack";
import Tooltip from "@mui/material/Tooltip";
import Typography from "@mui/material/Typography";

// Icons
import {
  CloseOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  EditOutlined,
  WarningOutlined,
} from "@ant-design/icons";

// Project imports
import SignalTypeChip from "components/chips/SignalTypeChip";
import SignalStatusChip from "components/chips/SignalStatusChip";
import DrawerFieldRow from "components/display/DrawerFieldRow";
import DrawerSection from "components/display/DrawerSection";
import { getMissingFields } from "./signalValidationRules";
import SignalIncompleteAlert from "./SignalIncompleteAlert";
import {
  getTechSummary,
  getContact,
  formatContact,
  getNextStepSummary,
  formatSuggestedContacts,
} from "./utils/signalDisplay";

const DRAWER_WIDTH = 400;

function formatDate(dateStr) {
  if (!dateStr) return null;
  try {
    return new Date(dateStr).toLocaleDateString("en-GB", {
      day: "numeric",
      month: "short",
      year: "numeric",
    });
  } catch {
    return dateStr;
  }
}

function formatDateTime(dateStr) {
  if (!dateStr) return null;
  try {
    return new Date(dateStr).toLocaleDateString("en-GB", {
      day: "numeric",
      month: "short",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return dateStr;
  }
}

function getSummary(signal, signalType) {
  if (signalType === "tech-stack") return getTechSummary(signal).name;
  if (signalType === "next-steps") return getNextStepSummary(signal);
  return signal.summary || "—";
}

// ==============================|| SOURCE QUOTE BLOCK ||============================== //

function SourceQuoteBlock({ quote }) {
  if (!quote) return null;
  return (
    <Box
      sx={{
        p: 1.5,
        bgcolor: "grey.50",
        borderRadius: 1,
        borderLeft: 3,
        borderColor: "primary.main",
      }}
    >
      <Typography
        variant="body2"
        sx={{ fontStyle: "italic" }}
        color="text.secondary"
      >
        &ldquo;{quote}&rdquo;
      </Typography>
    </Box>
  );
}

SourceQuoteBlock.propTypes = { quote: PropTypes.string };

// ==============================|| TYPE-SPECIFIC DETAIL SECTIONS ||============================== //

function PainDetails({ signal }) {
  const contactName = formatContact(getContact(signal));
  const techRef = signal.related_techstack;
  return (
    <>
      <DrawerSection title="CLASSIFICATION">
        <DrawerFieldRow label="Theme" value={
          signal.what_display && signal.dimension_display
            ? `${signal.what_display} × ${signal.dimension_display}`
            : null
        } />
        <DrawerFieldRow label="Scope" value={signal.scope_level_display} />
        <DrawerFieldRow label="Category" value={signal.signal_category_display} />
      </DrawerSection>
      {techRef && (
        <DrawerSection title="RELATED TOOL">
          <DrawerFieldRow label="Tool" value={techRef.product_name} />
          <DrawerFieldRow label="Company" value={techRef.company_name} />
        </DrawerSection>
      )}
      {signal.related_techstack_mention && !techRef && (
        <DrawerSection title="RELATED TOOL">
          <DrawerFieldRow label="Mention" value={signal.related_techstack_mention} />
        </DrawerSection>
      )}
      <DrawerSection title="CONTEXT">
        <DrawerFieldRow label="Contact" value={contactName} />
        <DrawerFieldRow label="Notes" value={signal.notes} />
        <DrawerFieldRow label="Source quote">
          <SourceQuoteBlock quote={signal.source_quote} />
        </DrawerFieldRow>
      </DrawerSection>
    </>
  );
}
PainDetails.propTypes = { signal: PropTypes.object.isRequired };

function ObjectiveDetails({ signal }) {
  const contactName = formatContact(getContact(signal));
  const targetContact = signal.target_contact
    ? formatContact(signal.target_contact)
    : null;
  const targetDept = signal.target_department?.name;
  return (
    <>
      <DrawerSection title="CLASSIFICATION">
        <DrawerFieldRow label="Theme" value={
          signal.what_display && signal.dimension_display
            ? `${signal.what_display} × ${signal.dimension_display}`
            : null
        } />
        <DrawerFieldRow label="Scope" value={signal.scope_level_display} />
      </DrawerSection>
      <DrawerSection title="DETAILS">
        <DrawerFieldRow label="Success criteria" value={signal.success_criteria} />
        <DrawerFieldRow label="Target date" value={formatDate(signal.target_date)} />
        <DrawerFieldRow label="Target contact" value={targetContact} />
        <DrawerFieldRow label="Target department" value={targetDept} />
        <DrawerFieldRow label="Notes" value={signal.notes} />
      </DrawerSection>
      <DrawerSection title="CONTEXT">
        <DrawerFieldRow label="Contact" value={contactName} />
        <DrawerFieldRow label="Source quote">
          <SourceQuoteBlock quote={signal.source_quote} />
        </DrawerFieldRow>
      </DrawerSection>
    </>
  );
}
ObjectiveDetails.propTypes = { signal: PropTypes.object.isRequired };

function ImpactDetails({ signal }) {
  const contactName = formatContact(getContact(signal));
  return (
    <>
      <DrawerSection title="CLASSIFICATION">
        <DrawerFieldRow label="Theme" value={
          signal.what_display && signal.dimension_display
            ? `${signal.what_display} × ${signal.dimension_display}`
            : null
        } />
        <DrawerFieldRow label="Impact type" value={signal.impact_type_display} />
        <DrawerFieldRow label="Scope" value={signal.scope_level_display} />
      </DrawerSection>
      <DrawerSection title="DETAILS">
        <DrawerFieldRow label="Metric" value={signal.metric_text} />
        <DrawerFieldRow label="Human impact" value={signal.human_impact_display} />
      </DrawerSection>
      <DrawerSection title="CONTEXT">
        <DrawerFieldRow label="Contact" value={contactName} />
        <DrawerFieldRow label="Source quote">
          <SourceQuoteBlock quote={signal.source_quote} />
        </DrawerFieldRow>
      </DrawerSection>
    </>
  );
}
ImpactDetails.propTypes = { signal: PropTypes.object.isRequired };

function TechStackDetails({ signal, onEdit }) {
  const techInfo = getTechSummary(signal);
  const contactName = formatContact(getContact(signal));
  const catalogEntry = signal.tech_catalog_entry;
  return (
    <>
      <DrawerSection title="IDENTITY">
        <DrawerFieldRow label="Tool">
          <Stack direction="row" spacing={1} alignItems="center">
            <Typography variant="body2">{techInfo.name}</Typography>
            {techInfo.pending && (
              <Tooltip
                title={
                  onEdit
                    ? "Attach a catalog entry to validate this tool"
                    : "Not in your tech catalog"
                }
              >
                <Chip
                  icon={<WarningOutlined style={{ fontSize: 10 }} />}
                  label="Not in catalog"
                  size="small"
                  color="warning"
                  variant="outlined"
                  onClick={onEdit ? () => onEdit(signal, "tech-stack") : undefined}
                  sx={{
                    height: 20,
                    fontSize: "0.7rem",
                    ...(onEdit ? { cursor: "pointer" } : {}),
                  }}
                />
              </Tooltip>
            )}
          </Stack>
        </DrawerFieldRow>
        {catalogEntry?.company_name && (
          <DrawerFieldRow label="Company" value={catalogEntry.company_name} />
        )}
        {catalogEntry?.is_competitor && (
          <DrawerFieldRow label="Competitor">
            <Chip label="Competitor" size="small" color="error" variant="outlined" sx={{ height: 20, fontSize: "0.7rem" }} />
          </DrawerFieldRow>
        )}
        <DrawerFieldRow label="Mentioned by" value={contactName} />
      </DrawerSection>
      <DrawerSection title="USAGE">
        <DrawerFieldRow label="Scope" value={signal.usage_scope_display} />
        {signal.usage_department?.name && (
          <DrawerFieldRow label="Department" value={signal.usage_department.name} />
        )}
        {signal.usage_start_year && (
          <DrawerFieldRow label="Used since" value={String(signal.usage_start_year)} />
        )}
        <DrawerFieldRow label="Renewal date" value={formatDate(signal.renewal_date)} />
      </DrawerSection>
      <DrawerSection title="COST & STATUS">
        <DrawerFieldRow label="Cost description" value={signal.cost_description} />
        {signal.is_discontinued && (
          <DrawerFieldRow label="Status">
            <Typography variant="body2" color="error.main">
              Discontinued{signal.discontinued_date ? ` (${formatDate(signal.discontinued_date)})` : ""}
            </Typography>
          </DrawerFieldRow>
        )}
      </DrawerSection>
      <DrawerSection title="CONTEXT">
        <DrawerFieldRow label="Notes" value={signal.notes} />
        <DrawerFieldRow label="Source quote">
          <SourceQuoteBlock quote={signal.source_quote} />
        </DrawerFieldRow>
      </DrawerSection>
    </>
  );
}
TechStackDetails.propTypes = {
  signal: PropTypes.object.isRequired,
  onEdit: PropTypes.func,
};

function BlockerDetails({ signal }) {
  const contactName = formatContact(getContact(signal));
  return (
    <DrawerSection title="CONTEXT">
      <DrawerFieldRow label="Raised by" value={contactName} />
      <DrawerFieldRow label="Source quote">
        <SourceQuoteBlock quote={signal.source_quote} />
      </DrawerFieldRow>
    </DrawerSection>
  );
}
BlockerDetails.propTypes = { signal: PropTypes.object.isRequired };

function NextStepDetails({ signal }) {
  const suggestedContacts = formatSuggestedContacts(signal.suggested_contacts);
  const linked = signal.linked_activity;
  return (
    <>
      <DrawerSection title="SUGGESTION">
        <DrawerFieldRow label="Type" value={signal.suggested_activity_type_display} />
        <DrawerFieldRow label="Due date" value={formatDate(signal.suggested_due_date)} />
        {suggestedContacts && (
          <DrawerFieldRow label="Contacts" value={suggestedContacts} />
        )}
      </DrawerSection>
      {linked && (
        <DrawerSection title="LINKED ACTIVITY">
          <DrawerFieldRow label="Title" value={linked.title} />
          <DrawerFieldRow label="Type" value={linked.activity_type_display} />
          <DrawerFieldRow label="Status" value={linked.status_display} />
          <DrawerFieldRow label="Date" value={formatDate(linked.scheduled_date)} />
        </DrawerSection>
      )}
      <DrawerSection title="CONTEXT">
        <DrawerFieldRow label="Source quote">
          <SourceQuoteBlock quote={signal.source_quote} />
        </DrawerFieldRow>
      </DrawerSection>
    </>
  );
}
NextStepDetails.propTypes = { signal: PropTypes.object.isRequired };

function renderDetails(signal, signalType, onEdit) {
  switch (signalType) {
    case "pain": return <PainDetails signal={signal} />;
    case "objective": return <ObjectiveDetails signal={signal} />;
    case "impact": return <ImpactDetails signal={signal} />;
    case "tech-stack": return <TechStackDetails signal={signal} onEdit={onEdit} />;
    case "blockers": return <BlockerDetails signal={signal} />;
    case "next-steps": return <NextStepDetails signal={signal} />;
    default: return null;
  }
}

// ==============================|| SIGNAL QUICK DRAWER ||============================== //

export default function SignalQuickDrawer({
  open,
  signal,
  signalType,
  onClose,
  onValidate,
  onReject,
  onEdit,
  isLocked,
}) {
  if (!signal) return null;

  const isPending = signal.status === "PENDING";
  const missingFields = isPending
    ? getMissingFields(signal, signalType)
    : [];
  const validateDisabled = missingFields.length > 0;

  return (
    <Drawer
      anchor="right"
      open={open}
      onClose={onClose}
      PaperProps={{
        sx: { width: DRAWER_WIDTH, p: 0 },
      }}
    >
      {/* Header */}
      <Box
        sx={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          px: 2.5,
          py: 2,
        }}
      >
        <Stack direction="row" spacing={1} alignItems="center">
          <SignalTypeChip signalType={signalType} size="small" />
          <SignalStatusChip status={signal.status} size="small" />
        </Stack>
        <IconButton size="small" onClick={onClose} aria-label="Close drawer">
          <CloseOutlined style={{ fontSize: 14 }} />
        </IconButton>
      </Box>

      <Divider />

      {/* Body */}
      <Box sx={{ px: 2.5, py: 2, flex: 1, overflow: "auto" }}>
        {/* Incomplete alert */}
        <SignalIncompleteAlert missingFields={missingFields} />

        {/* Summary */}
        <Typography variant="subtitle1" fontWeight={600} sx={{ mb: 2 }}>
          {getSummary(signal, signalType)}
        </Typography>

        {/* Validated by / at */}
        {signal.validated_by && (
          <DrawerFieldRow
            label="Validated by"
            value={`${signal.validated_by.first_name || ""} ${signal.validated_by.last_name || ""}`.trim()}
          />
        )}
        {signal.validated_at && (
          <DrawerFieldRow
            label="Validated at"
            value={formatDateTime(signal.validated_at)}
          />
        )}

        {(signal.validated_by || signal.validated_at) && <Box sx={{ mb: 1.5 }} />}

        {/* Type-specific detail sections */}
        {renderDetails(signal, signalType, onEdit)}
      </Box>

      <Divider />

      {/* Actions */}
      <Box sx={{ px: 2.5, py: 2 }}>
        <Stack direction="row" spacing={1} justifyContent="flex-end">
          {!isLocked && (
            <Button
              variant="outlined"
              size="small"
              startIcon={<EditOutlined style={{ fontSize: 14 }} />}
              onClick={() => onEdit?.(signal, signalType)}
            >
              Edit
            </Button>
          )}
          {isPending && !isLocked && (
            <>
              <Button
                variant="outlined"
                size="small"
                color="error"
                startIcon={<CloseCircleOutlined style={{ fontSize: 14 }} />}
                onClick={() => onReject?.(signal, signalType)}
              >
                Reject
              </Button>
              <Tooltip
                title={
                  validateDisabled
                    ? "Complete missing fields before validating"
                    : ""
                }
              >
                <span>
                  <Button
                    variant="contained"
                    size="small"
                    color="success"
                    disabled={validateDisabled}
                    startIcon={
                      <CheckCircleOutlined style={{ fontSize: 14 }} />
                    }
                    onClick={() => onValidate?.(signal, signalType)}
                  >
                    Validate
                  </Button>
                </span>
              </Tooltip>
            </>
          )}
        </Stack>
      </Box>
    </Drawer>
  );
}

SignalQuickDrawer.propTypes = {
  open: PropTypes.bool.isRequired,
  signal: PropTypes.shape({
    id: PropTypes.string,
    status: PropTypes.string,
    summary: PropTypes.string,
    source_quote: PropTypes.string,
    what_display: PropTypes.string,
    dimension_display: PropTypes.string,
    created_at: PropTypes.string,
    source: PropTypes.string,
    contact: PropTypes.object,
    source_context: PropTypes.shape({
      contacts: PropTypes.arrayOf(PropTypes.object),
    }),
    tech_catalog_entry: PropTypes.object,
    validated_by: PropTypes.object,
    validated_at: PropTypes.string,
  }),
  signalType: PropTypes.string,
  onClose: PropTypes.func.isRequired,
  onValidate: PropTypes.func,
  onReject: PropTypes.func,
  onEdit: PropTypes.func,
  isLocked: PropTypes.bool,
};
