// src/views/businessData/products/list.jsx
"use client";

import { useMemo, useState, useCallback } from "react";

// material-ui
import Stack from "@mui/material/Stack";
import Tooltip from "@mui/material/Tooltip";
import Typography from "@mui/material/Typography";

// project imports
import IconButton from "components/@extended/IconButton";
import ReusableTable from "components/table/Table";
import ProductCatalogModal from "sections/businessData/products/ProductCatalogModal";
import AlertProductCatalogDelete from "sections/businessData/products/AlertProductCatalogDelete";

// hooks
import useLocalStorage from "hooks/useLocalStorage";
import { useAuth } from "hooks/useAuth";

// api
import { useGetProductCatalogEntries } from "api/businessData/productCatalog";
import { tenantKey } from "api/_swr";

// utils
import { formatDateTime } from "config/formatters";

// assets
import DeleteOutlined from "@ant-design/icons/DeleteOutlined";
import EditOutlined from "@ant-design/icons/EditOutlined";

// ==============================|| SORT FIELD MAPPING ||============================== //

/**
 * Map frontend column ids to backend ordering field names.
 * Only the columns the backend can order on are listed
 * (ProductCatalogViewSet.ordering_fields).
 */
const COLUMN_TO_BACKEND_FIELD = {
  name: "name",
  default_unit_price: "default_unit_price",
  updated_at: "updated_at",
};

// ==============================|| PRICE FORMAT ||============================== //

/**
 * Format the default unit price for table display.
 * The model carries no currency code, so the raw decimal is shown with
 * grouped thousands and two fraction digits; null renders as a dash.
 */
function formatPrice(value) {
  if (value === null || value === undefined || value === "") return "-";
  const n = Number(value);
  if (Number.isNaN(n)) return "-";
  return n.toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

// ==============================|| PRODUCT CATALOG LIST PAGE ||============================== //

/**
 * Product catalog admin list page.
 *
 * Pure CRUD surface calqued on the TechCatalog table — no tabs, no
 * advanced filters, no bulk operations, no import. The product catalog is
 * a tenant-level reference list curated by admins.
 *
 * Writes are admin-only, enforced server-side by ScopedPermission (a
 * non-admin action returns 403, handled like everywhere else). The UI
 * shows the same controls to everyone — no front-side gating, matching
 * the TechCatalog pattern.
 *
 * Server-side pagination + search + ordering via useGetProductCatalogEntries.
 */
export default function ProductCatalogListPage() {
  const { tenantId } = useAuth();
  const MAX_PAGE_SIZE = 100;

  // ==============================|| STATE ||============================== //

  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useLocalStorage(
    "productCatalogTablePageSize",
    20,
  );

  const validPageSize = useMemo(() => {
    const parsed = Number(pageSize);
    if (isNaN(parsed) || parsed <= 0) return 20;
    return Math.min(parsed, MAX_PAGE_SIZE);
  }, [pageSize]);

  const [search, setSearch] = useState("");
  const [sorting, setSorting] = useState([]);

  const [modalOpen, setModalOpen] = useState(false);
  const [selectedEntry, setSelectedEntry] = useState(null);

  const [deleteOpen, setDeleteOpen] = useState(false);
  const [entryToDelete, setEntryToDelete] = useState(null);

  // ==============================|| ORDERING ||============================== //

  /**
   * Convert TanStack sorting state to a Django-compatible ordering string.
   * Example: [{ id: 'name', desc: true }] → '-name'
   */
  const ordering = useMemo(() => {
    if (!Array.isArray(sorting) || sorting.length === 0) {
      return "name";
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
  } = useGetProductCatalogEntries({
    page,
    pageSize: validPageSize,
    search,
    ordering,
  });

  // SWR key for ReusableTable cache hooks (same shape as techCatalog list)
  const swrKey = useMemo(() => {
    const params = new URLSearchParams();
    params.append("page", page);
    params.append("page_size", validPageSize);
    if (search) params.append("search", search);
    if (ordering) params.append("ordering", ordering);
    const url = `/product-catalog/${
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
      // Product name — clickable, opens edit modal
      {
        header: "Product",
        accessorKey: "name",
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

      // Default unit price
      {
        header: "Default Unit Price",
        accessorKey: "default_unit_price",
        meta: { className: "cell-right" },
        cell: ({ getValue }) => (
          <Typography variant="body2">{formatPrice(getValue())}</Typography>
        ),
      },

      // Description — truncated to keep the row readable
      {
        header: "Description",
        accessorKey: "description",
        enableSorting: false,
        cell: ({ getValue }) => {
          const v = getValue();
          if (!v) {
            return (
              <Typography variant="body2" color="text.secondary">
                -
              </Typography>
            );
          }
          return (
            <Tooltip title={v}>
              <Typography
                variant="body2"
                color="text.secondary"
                sx={{
                  maxWidth: 320,
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  whiteSpace: "nowrap",
                }}
              >
                {v}
              </Typography>
            </Tooltip>
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
        addButtonLabel="Add product"
        addButtonTooltip="Add product"
        searchPlaceholder={`Search ${entriesCount} products...`}
        exportFilename="product-catalog.csv"
        emptyMessage="No products found"
        emptyDescription="Start by adding your first product"
      />

      {/* Add / Edit Modal */}
      <ProductCatalogModal
        open={modalOpen}
        modalToggler={setModalOpen}
        entry={selectedEntry}
      />

      {/* Single Delete Confirmation */}
      <AlertProductCatalogDelete
        entry={entryToDelete}
        open={deleteOpen}
        handleClose={handleDeleteClose}
      />
    </>
  );
}
