// frontend/src/components/signals/SignalDetailContent.jsx
//
// The single-signal detail CONTENT — header row (leading/trailing action slots
// + type/status chips), body (summary, validated-by, per-type detail block via
// the shared B1.2 blocks, source quote, origin provenance) and the lifecycle
// actions (validate / reject / edit / reopen).
//
// This is the drawer body extracted from SignalQuickDrawer so it can be reused
// as the "replacement" content inside another themed MUI Drawer shell (the
// cluster drawer's signal view) WITHOUT stacking a second drawer. Both
// SignalQuickDrawer and SignalClusterDetailDrawer render this same content.

"use client";

import PropTypes from "prop-types";

// MUI
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Divider from "@mui/material/Divider";
import Stack from "@mui/material/Stack";
import Tooltip from "@mui/material/Tooltip";
import Typography from "@mui/material/Typography";

// Icons
import {
  CheckCircleOutlined,
  CloseCircleOutlined,
  EditOutlined,
  LinkOutlined,
  ReloadOutlined,
} from "@ant-design/icons";

// Project imports
import SignalTypeChip from "components/chips/SignalTypeChip";
import SignalStatusChip from "components/chips/SignalStatusChip";
import DrawerFieldRow from "components/display/DrawerFieldRow";
import DrawerSection from "components/display/DrawerSection";
import { getMissingFields } from "sections/activities/signals/signalValidationRules";
import SignalIncompleteAlert from "sections/activities/signals/SignalIncompleteAlert";
import {
  getTechSummary,
  getContact,
  formatContact,
  getNextStepSummary,
  formatSuggestedContacts,
} from "sections/activities/signals/utils/signalDisplay";

// Shared per-type detail blocks — the single rendering of each type's
// type-specific fields (B1.2).
import ImpactDetailBlock from "components/signals/detail/ImpactDetailBlock";
import ObjectiveDetailBlock from "components/signals/detail/ObjectiveDetailBlock";
import TechDetailBlock from "components/signals/detail/TechDetailBlock";
import PainDetailBlock from "components/signals/detail/PainDetailBlock";

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
      <Typography variant="body2" sx={{ fontStyle: "italic" }} color="text.secondary">
        &ldquo;{quote}&rdquo;
      </Typography>
    </Box>
  );
}

SourceQuoteBlock.propTypes = { quote: PropTypes.string };

// ==============================|| TYPE-SPECIFIC DETAIL SECTIONS ||============================== //

function PainDetails({ signal }) {
  const contactName = formatContact(getContact(signal));
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
      <PainDetailBlock signal={signal} />
      <DrawerSection title="CONTEXT">
        <DrawerFieldRow label="Contact" value={contactName} />
        <DrawerFieldRow label="Notes" value={signal.notes} />
      </DrawerSection>
    </>
  );
}
PainDetails.propTypes = { signal: PropTypes.object.isRequired };

function ObjectiveDetails({ signal }) {
  const contactName = formatContact(getContact(signal));
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
      <ObjectiveDetailBlock signal={signal} />
      <DrawerSection title="CONTEXT">
        <DrawerFieldRow label="Contact" value={contactName} />
        <DrawerFieldRow label="Notes" value={signal.notes} />
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
        <DrawerFieldRow label="Scope" value={signal.scope_level_display} />
      </DrawerSection>
      <ImpactDetailBlock signal={signal} />
      <DrawerSection title="CONTEXT">
        <DrawerFieldRow label="Contact" value={contactName} />
      </DrawerSection>
    </>
  );
}
ImpactDetails.propTypes = { signal: PropTypes.object.isRequired };

function TechStackDetails({ signal }) {
  const techInfo = getTechSummary(signal);
  const contactName = formatContact(getContact(signal));
  return (
    <>
      <DrawerSection title="IDENTITY">
        <DrawerFieldRow label="Tool">
          <Typography variant="body2">{techInfo.name}</Typography>
        </DrawerFieldRow>
        <DrawerFieldRow label="Mentioned by" value={contactName} />
      </DrawerSection>
      <TechDetailBlock signal={signal} />
      <DrawerSection title="CONTEXT">
        <DrawerFieldRow label="Notes" value={signal.notes} />
      </DrawerSection>
    </>
  );
}
TechStackDetails.propTypes = { signal: PropTypes.object.isRequired };

function BlockerDetails({ signal }) {
  const contactName = formatContact(getContact(signal));
  return (
    <DrawerSection title="CONTEXT">
      <DrawerFieldRow label="Raised by" value={contactName} />
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
    </>
  );
}
NextStepDetails.propTypes = { signal: PropTypes.object.isRequired };

function PeopleDetails({ signal }) {
  const targetContact = signal.target_contact ? formatContact(signal.target_contact) : null;
  const targetDept = signal.target_department?.name;
  return (
    <>
      <DrawerSection title="ROLE">
        <DrawerFieldRow label="Role" value={signal.role_display} />
        <DrawerFieldRow label="Influence" value={signal.influence_display} />
        <DrawerFieldRow label="Contact" value={targetContact} />
        <DrawerFieldRow label="Department" value={targetDept} />
      </DrawerSection>
      <DrawerSection title="CONTEXT">
        <DrawerFieldRow label="Notes" value={signal.notes} />
      </DrawerSection>
    </>
  );
}
PeopleDetails.propTypes = { signal: PropTypes.object.isRequired };

function ConstraintDetails({ signal }) {
  const contactName = formatContact(getContact(signal));
  return (
    <>
      <DrawerSection title="CLASSIFICATION">
        <DrawerFieldRow label="Theme" value={
          signal.what_display && signal.dimension_display
            ? `${signal.what_display} × ${signal.dimension_display}`
            : null
        } />
        <DrawerFieldRow label="Rigidity" value={signal.rigidity_display} />
        <DrawerFieldRow label="Department" value={signal.target_department?.name} />
      </DrawerSection>
      <DrawerSection title="CONTEXT">
        <DrawerFieldRow label="Raised by" value={contactName} />
        <DrawerFieldRow label="Notes" value={signal.notes} />
      </DrawerSection>
    </>
  );
}
ConstraintDetails.propTypes = { signal: PropTypes.object.isRequired };

function renderDetails(signal, signalType) {
  switch (signalType) {
    case "pain": return <PainDetails signal={signal} />;
    case "objective": return <ObjectiveDetails signal={signal} />;
    case "impact": return <ImpactDetails signal={signal} />;
    case "tech-stack": return <TechStackDetails signal={signal} />;
    case "blockers": return <BlockerDetails signal={signal} />;
    case "next-steps": return <NextStepDetails signal={signal} />;
    case "people": return <PeopleDetails signal={signal} />;
    case "constraints": return <ConstraintDetails signal={signal} />;
    default: return null;
  }
}

// ==============================|| PROVENANCE ||============================== //

function formatDrawerContact(contact) {
  const name = `${contact.first_name ?? ""} ${contact.last_name ?? ""}`.trim();
  const parts = [
    name || null,
    contact.job_title || null,
    contact.department?.name || null,
  ].filter(Boolean);
  return parts.join(" · ") || null;
}

function ProvenanceSection({ signal, onOpenActivity }) {
  const contacts = signal.source_context?.contacts ?? [];
  const activityId = signal.source_context?.activity?.id ?? null;
  if (contacts.length === 0 && !activityId) return null;

  return (
    <DrawerSection title="ORIGIN">
      {contacts.length > 0 && (
        <DrawerFieldRow label={contacts.length > 1 ? "Contacts" : "Contact"}>
          <Stack spacing={0.25}>
            {contacts.map((c) => (
              <Typography key={c.id} variant="body2">
                {formatDrawerContact(c)}
              </Typography>
            ))}
          </Stack>
        </DrawerFieldRow>
      )}
      {activityId && onOpenActivity && (
        <Button
          size="small"
          variant="text"
          startIcon={<LinkOutlined style={{ fontSize: 13 }} />}
          onClick={() => onOpenActivity(activityId)}
          sx={{ mt: 0.5, px: 0 }}
        >
          View origin activity
        </Button>
      )}
    </DrawerSection>
  );
}
ProvenanceSection.propTypes = {
  signal: PropTypes.object.isRequired,
  onOpenActivity: PropTypes.func,
};

// ==============================|| SIGNAL DETAIL CONTENT ||============================== //

/**
 * @param {node} leadingAction   Rendered before the chips (e.g. a Back button).
 * @param {node} trailingAction  Rendered at the far right (e.g. a Close button).
 */
export default function SignalDetailContent({
  signal,
  signalType,
  onValidate,
  onReject,
  onEdit,
  onReopen,
  onOpenActivity,
  isLocked,
  leadingAction,
  trailingAction,
}) {
  if (!signal) return null;

  const isPending = signal.status === "PENDING";
  const isRejected = signal.status === "REJECTED";
  const missingFields = isPending ? getMissingFields(signal, signalType) : [];
  const validateDisabled = missingFields.length > 0;

  return (
    <>
      {/* Header — leading action (back) · chips · trailing action (close) */}
      <Box
        sx={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          px: 2.5,
          py: 2,
        }}
      >
        <Stack direction="row" spacing={1} alignItems="center" sx={{ minWidth: 0 }}>
          {leadingAction}
          <SignalTypeChip signalType={signalType} size="small" />
          <SignalStatusChip status={signal.status} size="small" />
        </Stack>
        {trailingAction}
      </Box>

      <Divider />

      {/* Body */}
      <Box sx={{ px: 2.5, py: 2, flex: 1, overflow: "auto" }}>
        <SignalIncompleteAlert missingFields={missingFields} />

        <Typography variant="subtitle1" fontWeight={600} sx={{ mb: 2 }}>
          {getSummary(signal, signalType)}
        </Typography>

        {signal.validated_by && (
          <DrawerFieldRow
            label="Validated by"
            value={`${signal.validated_by.first_name || ""} ${signal.validated_by.last_name || ""}`.trim()}
          />
        )}
        {signal.validated_at && (
          <DrawerFieldRow label="Validated at" value={formatDateTime(signal.validated_at)} />
        )}
        {(signal.validated_by || signal.validated_at) && <Box sx={{ mb: 1.5 }} />}

        {renderDetails(signal, signalType)}

        {signal.source_quote && (
          <DrawerSection title="SOURCE QUOTE">
            <SourceQuoteBlock quote={signal.source_quote} />
          </DrawerSection>
        )}

        <ProvenanceSection signal={signal} onOpenActivity={onOpenActivity} />
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
              <Tooltip title={validateDisabled ? "Complete missing fields before validating" : ""}>
                <span>
                  <Button
                    variant="contained"
                    size="small"
                    color="success"
                    disabled={validateDisabled}
                    startIcon={<CheckCircleOutlined style={{ fontSize: 14 }} />}
                    onClick={() => onValidate?.(signal, signalType)}
                  >
                    Validate
                  </Button>
                </span>
              </Tooltip>
            </>
          )}
          {isRejected && !isLocked && (
            <Button
              variant="outlined"
              size="small"
              startIcon={<ReloadOutlined style={{ fontSize: 14 }} />}
              onClick={() => onReopen?.(signal, signalType)}
            >
              Reopen
            </Button>
          )}
        </Stack>
      </Box>
    </>
  );
}

SignalDetailContent.propTypes = {
  signal: PropTypes.object,
  signalType: PropTypes.string,
  onValidate: PropTypes.func,
  onReject: PropTypes.func,
  onEdit: PropTypes.func,
  onReopen: PropTypes.func,
  onOpenActivity: PropTypes.func,
  isLocked: PropTypes.bool,
  leadingAction: PropTypes.node,
  trailingAction: PropTypes.node,
};
