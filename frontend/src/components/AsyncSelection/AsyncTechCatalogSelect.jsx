// frontend/src/components/AsyncSelection/AsyncTechCatalogSelect.jsx
/**
 * ASYNC TECH CATALOG SELECT — Wrapper for tech catalog entry selection.
 *
 * Uses AsyncSelect with pre-configured settings for the tenant-level
 * TechCatalog. The catalog is curated by tenant admins and consumed
 * read-only by sales-side modules — this selector is the canonical
 * entry point used by:
 *
 *   - InlineTechStackForm  (Section 1 — required catalog anchor)
 *   - InlinePainForm       (Section "Related tool" — optional cross-ref
 *                            when what === 'TECH')
 *
 * Features:
 *   - Server-side search on company_name + product_name (handled by
 *     TechCatalogViewSet.search_fields on the backend)
 *   - Automatic debounce (300ms, inherited from AsyncSelect)
 *   - Tenant-wide scope — NO account_id filter (the catalog is shared
 *     across the tenant, not per-account)
 *   - Display label: "{company_name} {product_name}"
 *   - Inline badges: is_competitor / is_integration_target — they read
 *     from the option object so the rep can spot strategic context
 *     (a competitor tool tells a different story than a partner tool)
 *   - Empty-state copy: directs the rep to ask their admin if the
 *     catalog has not been populated yet — there is no inline-create
 *     for MVP (admin-only via the dedicated TechCatalog tab)
 *
 * Note on filtering by status
 * ---------------------------
 * The sprint plan calls for filtering on `status=VALIDATED` so that
 * draft catalog entries do not surface in the picker. However, the
 * backend TechCatalog model in the current sprint does not expose a
 * `status` query filter (see TechCatalogViewSet — only search +
 * ordering). Adding the filter on the API hook would be a no-op until
 * the backend supports it.
 *
 * For now we pass a `status=VALIDATED` filter through the `filters`
 * prop of AsyncSelect — the URL builder in techCatalog.js currently
 * ignores unrecognized filter keys, so this is harmless and forward-
 * compatible: the day the backend adds the filter, it activates
 * automatically without a frontend change.
 *
 * @example
 * // In InlineTechStackForm Section 1 (required)
 * <AsyncTechCatalogSelect
 *   value={formik.values.tech_catalog_entry}
 *   onChange={(_e, entry) =>
 *     formik.setFieldValue('tech_catalog_entry', entry)
 *   }
 *   onBlur={() => formik.setFieldTouched('tech_catalog_entry', true)}
 *   error={touched && Boolean(error)}
 *   helperText={touched && error}
 *   label="Tool *"
 * />
 *
 * @example
 * // In InlinePainForm cross-reference (optional, when what=TECH)
 * <AsyncTechCatalogSelect
 *   value={formik.values.related_techstack}
 *   onChange={(_e, entry) =>
 *     formik.setFieldValue('related_techstack', entry)
 *   }
 *   label="Related tool"
 *   helperText="If the tool is in the catalog, select it."
 * />
 */

import PropTypes from "prop-types";

// material-ui
import Box from "@mui/material/Box";
import Chip from "@mui/material/Chip";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";

// project imports
import AsyncSelect from "./AsyncSelect";
import { useGetTechCatalogEntries } from "api/businessData/techCatalog";

// ==============================|| CONSTANTS ||============================== //

/**
 * Default filter applied to every fetch — only surface VALIDATED
 * entries. Forward-compatible: harmless when the backend doesn't
 * implement the filter yet, automatically active when it does.
 */
const DEFAULT_FILTERS = { status: "VALIDATED" };

// ==============================|| HELPERS ||============================== //

/**
 * Format a catalog entry's display label.
 *
 * Both company_name and product_name are populated for every entry
 * (the model auto-fills product_name from company_name on save when
 * left blank — see TechCatalog.clean()). When the two names are
 * identical (e.g. "Notion / Notion") we collapse to a single token
 * to avoid visual noise.
 *
 * Falls back to "Unknown tool" defensively — a malformed entry should
 * never crash the picker.
 */
function getCatalogLabel(entry) {
  if (!entry) return "";

  const company = entry.company_name?.trim() || "";
  const product = entry.product_name?.trim() || "";

  if (!company && !product) return "Unknown tool";
  if (!company) return product;
  if (!product || product === company) return company;
  return `${company} ${product}`;
}

// ==============================|| OPTION RENDERER ||============================== //

/**
 * Custom renderer for each option in the dropdown.
 *
 * Surfaces the inline badges (is_competitor / is_integration_target)
 * directly in the picker so the rep gets strategic context at choice
 * time — not after the fact. Both flags can co-exist on a single
 * entry (rare but legitimate: a tool that is a competitor on some
 * accounts and an integration target on others, depending on context).
 *
 * Layout: [Label spans the line] [badges right-aligned, only when set]
 */
function renderCatalogOption(props, option) {
  // The `key` prop must be applied directly to the <li>, not spread —
  // React 18 emits a warning if it goes through ...props.
  const { key, ...rest } = props;

  const isCompetitor = Boolean(option?.is_competitor);
  const isIntegrationTarget = Boolean(option?.is_integration_target);

  return (
    <Box component="li" key={key} {...rest}>
      <Stack
        direction="row"
        spacing={1}
        alignItems="center"
        justifyContent="space-between"
        sx={{ width: "100%", minWidth: 0 }}
      >
        {/* Label */}
        <Typography
          variant="body2"
          sx={{
            flex: 1,
            minWidth: 0,
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
          }}
        >
          {getCatalogLabel(option)}
        </Typography>

        {/* Badges — only render when set, never empty placeholders */}
        {(isCompetitor || isIntegrationTarget) && (
          <Stack direction="row" spacing={0.5} flexShrink={0}>
            {isCompetitor && (
              <Chip
                label="Competitor"
                size="small"
                color="error"
                variant="outlined"
                sx={{ fontSize: "0.62rem", height: 18 }}
              />
            )}
            {isIntegrationTarget && (
              <Chip
                label="Integration"
                size="small"
                color="info"
                variant="outlined"
                sx={{ fontSize: "0.62rem", height: 18 }}
              />
            )}
          </Stack>
        )}
      </Stack>
    </Box>
  );
}

// ==============================|| ASYNC TECH CATALOG SELECT ||============================== //

function AsyncTechCatalogSelect({
  value,
  onChange,
  label = "Tool",
  placeholder = "Search the tech catalog…",
  disabled = false,
  error = false,
  helperText,
  filters = {},
  pageSize = 20,
  excludeIds = [],
  ...props
}) {
  /**
   * Merge default filters (status=VALIDATED) with caller-provided
   * ones. Caller filters win on conflict — leaves the door open for
   * a future "show all statuses" admin variant without code change.
   */
  const mergedFilters = { ...DEFAULT_FILTERS, ...filters };

  /**
   * UI-level dedup. The catalog is tenant-wide and small enough that
   * server-side dedup would be overkill — we just hide entries the
   * caller already used elsewhere (e.g. multi-select scenarios).
   */
  const filterOptions = (options) => {
    if (!excludeIds || excludeIds.length === 0) return options;
    return options.filter((opt) => !excludeIds.includes(opt.id));
  };

  return (
    <AsyncSelect
      useDataHook={useGetTechCatalogEntries}
      dataKey="entries"
      loadingKey="entriesLoading"
      getOptionLabel={getCatalogLabel}
      filterOptions={filterOptions}
      renderOption={renderCatalogOption}
      value={value}
      onChange={onChange}
      label={label}
      placeholder={placeholder}
      disabled={disabled}
      error={error}
      helperText={
        helperText ??
        // Default helper text — only shown when the caller doesn't
        // override (e.g. with a Yup error message). Steers the rep
        // toward the admin escalation path rather than letting them
        // wonder why the picker is empty.
        "Pick a tool from your tenant's tech catalog."
      }
      pageSize={pageSize}
      minSearchLength={0}
      filters={mergedFilters}
      noOptionsText="No tools in catalog yet — ask your admin to add one"
      {...props}
    />
  );
}

// ==============================|| PROP TYPES ||============================== //

AsyncTechCatalogSelect.propTypes = {
  /** Full TechCatalog entry ({ id, company_name, product_name, ... }) or null */
  value: PropTypes.object,
  /** MUI Autocomplete onChange — receives (event, value, reason, details) */
  onChange: PropTypes.func.isRequired,
  label: PropTypes.string,
  placeholder: PropTypes.string,
  disabled: PropTypes.bool,
  error: PropTypes.bool,
  helperText: PropTypes.string,
  /** Extra filters merged on top of the default {status: 'VALIDATED'} */
  filters: PropTypes.object,
  pageSize: PropTypes.number,
  /** UUIDs to hide from results */
  excludeIds: PropTypes.array,
};

export default AsyncTechCatalogSelect;
