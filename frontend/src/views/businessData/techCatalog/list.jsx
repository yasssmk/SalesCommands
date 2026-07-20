// src/views/businessData/techCatalog/list.jsx
"use client";

import { useMemo, useState, useCallback } from "react";

// material-ui
import Chip from "@mui/material/Chip";
import Stack from "@mui/material/Stack";
import Tooltip from "@mui/material/Tooltip";
import Typography from "@mui/material/Typography";
import Link from "@mui/material/Link";

// project imports
import IconButton from "components/@extended/IconButton";
import ReusableTable from "components/table/Table";
import TechCatalogModal from "sections/businessdata/techCatalog/TechCatalogModal";
import AlertTechCatalogDelete from "sections/businessdata/techCatalog/AlertTechCatalogDelete";

// hooks
import useLocalStorage from "hooks/useLocalStorage";
import { useAuth } from "hooks/useAuth";

// api
import { useGetTechCatalogEntries } from "api/businessData/techCatalog";
import { tenantKey } from "api/_swr";

// utils
import { formatDateTime } from "config/formatters";

// assets
import DeleteOutlined from "@ant-design/icons/DeleteOutlined";
import EditOutlined from "@ant-design/icons/EditOutlined";

// ==============================|| SORT FIELD MAPPING ||============================== //

/**
 * Map frontend column ids to backend ordering field names.
 * Critical for server-side sorting to work as expected.
 */
const COLUMN_TO_BACKEND_FIELD = {
  company_name: "company_name",
  product_name: "product_name",
  updated_at: "updated_at",
};

// ==============================|| TECH CATALOG LIST PAGE ||============================== //

/**
 * TechCatalog admin list page.
 *
 * Pure CRUD surface — no tabs, no advanced filters, no bulk operations.
 * The TechCatalog is a small reference list curated by tenant admins:
 * the simplest table that lets them keep it tidy is what's needed.
 *
 * Architecture:
 *   - Uses ReusableTable directly with a flat column set.
 *   - Server-side pagination + search + ordering via useGetTechCatalogEntries.
 *   - Single-row interactions only (click row → edit, click delete → confirm).
 *   - Add button opens the same modal in create mode.
 */
export default function TechCatalogListPage() {
  const { tenantId } = useAuth();
  const MAX_PAGE_SIZE = 100;

  // ==============================|| STATE ||============================== //

  // Pagination state with localStorage persistence
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useLocalStorage(
    "techCatalogTablePageSize",
    20,
  );

  const validPageSize = useMemo(() => {
    const parsed = Number(pageSize);
    if (isNaN(parsed) || parsed <= 0) return 20;
    return Math.min(parsed, MAX_PAGE_SIZE);
  }, [pageSize]);

  // Search and sorting
  const [search, setSearch] = useState("");
  const [sorting, setSorting] = useState([]);

  // Modal state
  const [modalOpen, setModalOpen] = useState(false);
  const [selectedEntry, setSelectedEntry] = useState(null);

  // Delete confirmation state
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [entryToDelete, setEntryToDelete] = useState(null);

  // ==============================|| ORDERING ||============================== //

  /**
   * Convert TanStack sorting state to a Django-compatible ordering string.
   * Example: [{ id: 'company_name', desc: true }] → '-company_name'
   */
  const ordering = useMemo(() => {
    if (!Array.isArray(sorting) || sorting.length === 0) {
      return "company_name";
    }
    return sorting
      .map(({ id, desc }) => {
        const backendField = COLUMN_TO_BACKEND_FIELD[id] || id;
        return desc ? `-${backendField}` : backendField;
      })
      .join(",");
  }, [sorting]);

  // ==============================|| API DATA ||============================== //

  const {
    entries = [],
    entriesCount = 0,
    entriesLoading = false,
    entriesError = null,
  } = useGetTechCatalogEntries({
    page,
    pageSize: validPageSize,
    search,
    ordering,
  });

  // SWR key for ReusableTable cache hooks (same shape as accounts list)
  const swrKey = useMemo(() => {
    const params = new URLSearchParams();
    params.append("page", page);
    params.append("page_size", validPageSize);
    if (search) params.append("search", search);
    if (ordering) params.append("ordering", ordering);
    const url = `/tech-catalog/${
      params.toString() ? `?${params.toString()}` : ""
    }`;
    return tenantKey(url, tenantId);
  }, [page, validPageSize, search, ordering, tenantId]);

  // ==============================|| HANDLERS ||============================== //

  const handlePaginationChange = useCallback(
    ({ page: newPage, pageSize: newPageSize }) => {
      setPage(newPage);
      const size = Number(newPageSize);
      if (!isNaN(size) && size > 0 && size !== validPageSize) {
        setPageSize(size);
      }
    },
    [setPageSize, validPageSize],
  );

  const handleSearchChange = useCallback((searchTerm) => {
    setSearch(searchTerm);
    setPage(1);
  }, []);

  const handleSortingChange = useCallback((updaterOrValue) => {
    setSorting((prev) => {
      const next =
        typeof updaterOrValue === "function"
          ? updaterOrValue(prev)
          : updaterOrValue;
      if (JSON.stringify(next) !== JSON.stringify(prev)) {
        setPage(1);
      }
      return next;
    });
  }, []);

  const handleAdd = useCallback(() => {
    setSelectedEntry(null);
    setModalOpen(true);
  }, []);

  const handleEdit = useCallback((entry) => {
    setSelectedEntry(entry);
    setModalOpen(true);
  }, []);

  const handleDeleteOpen = useCallback((entry) => {
    setEntryToDelete(entry);
    setDeleteOpen(true);
  }, []);

  const handleDeleteClose = useCallback(() => {
    setDeleteOpen(false);
    setEntryToDelete(null);
  }, []);

  // ==============================|| COLUMNS ||============================== //

  const columns = useMemo(
    () => [
      // Company name — clickable, opens edit modal
      {
        header: "Company",
        accessorKey: "company_name",
        cell: ({ row, getValue }) => (
          <Typography
            variant="subtitle2"
            sx={{
              cursor: "pointer",
              "&:hover": {
                color: "primary.main",
                textDecoration: "underline",
              },
            }}
            onClick={(e) => {
              e.stopPropagation();
              handleEdit(row.original);
            }}
          >
            {getValue() || "N/A"}
          </Typography>
        ),
      },

      // Product name
      {
        header: "Product",
        accessorKey: "product_name",
        cell: ({ getValue }) => (
          <Typography variant="body2">{getValue() || "-"}</Typography>
        ),
      },

      // Competitor flag
      {
        header: "Competitor",
        accessorKey: "is_competitor",
        cell: ({ getValue }) =>
          getValue() ? (
            <Chip
              label="Competitor"
              color="error"
              size="small"
              variant="light"
            />
          ) : (
            <Typography variant="body2" color="text.secondary">
              -
            </Typography>
          ),
      },

      // Integration target flag
      {
        header: "Integration",
        accessorKey: "is_integration_target",
        cell: ({ getValue }) =>
          getValue() ? (
            <Chip
              label="Integration"
              color="success"
              size="small"
              variant="light"
            />
          ) : (
            <Typography variant="body2" color="text.secondary">
              -
            </Typography>
          ),
      },

      // Vendor URL
      {
        header: "Vendor URL",
        accessorKey: "vendor_url",
        enableSorting: false,
        cell: ({ getValue }) => {
          const url = getValue();
          if (!url) {
            return (
              <Typography variant="body2" color="text.secondary">
                -
              </Typography>
            );
          }
          return (
            <Link
              href={url}
              target="_blank"
              rel="noopener noreferrer"
              underline="hover"
              variant="body2"
              onClick={(e) => e.stopPropagation()}
              sx={{
                display: "inline-block",
                maxWidth: 240,
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
              }}
            >
              {url}
            </Link>
          );
        },
      },

      // Last update
      {
        header: "Last Update",
        accessorKey: "updated_at",
        cell: ({ getValue }) => {
          const v = getValue();
          return (
            <Typography variant="body2" color="text.secondary">
              {v ? formatDateTime(v) : "Never"}
            </Typography>
          );
        },
      },

      // Actions
      {
        header: "Actions",
        id: "actions",
        meta: { className: "cell-center" },
        enableSorting: false,
        cell: ({ row }) => (
          <Stack
            direction="row"
            alignItems="center"
            justifyContent="center"
            spacing={0}
          >
            <Tooltip title="Edit">
              <IconButton
                color="secondary"
                onClick={(e) => {
                  e.stopPropagation();
                  handleEdit(row.original);
                }}
              >
                <EditOutlined />
              </IconButton>
            </Tooltip>
            <Tooltip title="Delete">
              <IconButton
                color="secondary"
                onClick={(e) => {
                  e.stopPropagation();
                  handleDeleteOpen(row.original);
                }}
              >
                <DeleteOutlined />
              </IconButton>
            </Tooltip>
          </Stack>
        ),
      },
    ],
    [handleEdit, handleDeleteOpen],
  );

  // ==============================|| RENDER ||============================== //

  return (
    <>
      <ReusableTable
        data={entries}
        columns={columns}
        loading={entriesLoading}
        error={entriesError}
        swrKey={swrKey}
        modalToggler={handleAdd}
        totalCount={entriesCount}
        currentPage={page}
        onPaginationChange={handlePaginationChange}
        onSearchChange={handleSearchChange}
        sorting={sorting}
        onSortingChange={handleSortingChange}
        initialPageSize={validPageSize}
        // Customization
        enableImport={false}
        addButtonLabel="Add tech"
        addButtonTooltip="Add tech"
        searchPlaceholder={`Search ${entriesCount} entries...`}
        exportFilename="tech-catalog.csv"
        emptyMessage="No catalog entries found"
        emptyDescription="Start by adding your first technology"
      />

      {/* Add / Edit Modal */}
      <TechCatalogModal
        open={modalOpen}
        modalToggler={setModalOpen}
        entry={selectedEntry}
      />

      {/* Single Delete Confirmation */}
      <AlertTechCatalogDelete
        entry={entryToDelete}
        open={deleteOpen}
        handleClose={handleDeleteClose}
      />
    </>
  );
}
