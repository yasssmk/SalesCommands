// src/sections/accounts/contacts/AccountContactsTab.jsx

"use client";

import PropTypes from "prop-types";
import { useMemo, useState, useCallback } from "react";

// material-ui
import Box from "@mui/material/Box";
import Chip from "@mui/material/Chip";
import Stack from "@mui/material/Stack";
import Tooltip from "@mui/material/Tooltip";
import Typography from "@mui/material/Typography";

// project imports
import IconButton from "components/@extended/IconButton";
import ReusableTable from "components/table/Table";
import ContactModal from "sections/accounts/contacts/ContactModal";
import AlertContactDelete from "sections/accounts/contacts/AlertContactDelete";
import ExpandingContactDetail from "./ExpandingContactDetail";

// hooks
import useLocalStorage from "hooks/useLocalStorage";
import { useAuth } from "hooks/useAuth";

// api
import { useGetContacts } from "api/businessData/contacts";
import { tenantKey } from "api/_swr";

// assets
import DeleteOutlined from "@ant-design/icons/DeleteOutlined";
import EditOutlined from "@ant-design/icons/EditOutlined";
import EyeOutlined from "@ant-design/icons/EyeOutlined";
import PlusOutlined from "@ant-design/icons/PlusOutlined";
import AimOutlined from "@ant-design/icons/AimOutlined";
import AddToCampaignModal from "sections/campaigns/AddToCampaignModal";

// ==============================|| SORT FIELD MAPPING ||============================== //

/**
 * Map frontend column IDs to backend field names for sorting
 */
const COLUMN_TO_BACKEND_FIELD = {
  full_name: "last_name",
  department_name: "standard_department__name",
  email: "email",
  phone_number: "phone_number",
  influence_level: "influence_level",
  updated_at: "updated_at",
};

// ==============================|| INFLUENCE LEVEL COLORS ||============================== //

const INFLUENCE_COLORS = {
  DECISION_MAKER: "success",
  INFLUENCER: "info",
  CHAMPION: "primary",
  USER: "default",
  GATEKEEPER: "warning",
  BLOCKER: "error",
  UNKNOWN: "default",
};

// ==============================|| ACCOUNT CONTACTS TAB ||============================== //

/**
 * AccountContactsTab Component
 *
 * Displays contacts for a specific account with:
 * - ReusableTable with expanding rows
 * - Search bar
 * - Add Contact button
 * - View/Edit/Delete actions
 *
 * @param {Object} props
 * @param {string} props.accountId - UUID of the account
 * @param {Object} props.account - Account data (for prefilling create form)
 */
export default function AccountContactsTab({ accountId, account }) {
  const { tenantId } = useAuth();

  // ==============================|| STATE MANAGEMENT ||============================== //

  // Pagination state with localStorage persistence
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useLocalStorage(
    "accountContactsTablePageSize",
    10,
  );

  // Validate pageSize
  const validPageSize = useMemo(() => {
    const parsed = Number(pageSize);
    if (isNaN(parsed) || parsed <= 0) return 10;
    return Math.min(parsed, 100);
  }, [pageSize]);

  // Search state
  const [search, setSearch] = useState("");

  // Sorting state
  const [sorting, setSorting] = useState([]);

  // Modal states
  const [contactModal, setContactModal] = useState(false);
  const [selectedContact, setSelectedContact] = useState(null);
  const [deleteModal, setDeleteModal] = useState(false);
  const [contactToDelete, setContactToDelete] = useState(null);
  const [campaignModal, setCampaignModal] = useState(false);
  const [campaignContact, setCampaignContact] = useState(null);

  // ==============================|| COMPUTE ORDERING STRING ||============================== //

  const ordering = useMemo(() => {
    if (!sorting || !Array.isArray(sorting) || sorting.length === 0) {
      return "";
    }

    return sorting
      .map(({ id, desc }) => {
        const backendField = COLUMN_TO_BACKEND_FIELD[id] || id;
        return desc ? `-${backendField}` : backendField;
      })
      .join(",");
  }, [sorting]);

  // ==============================|| API DATA FETCHING ||============================== //

  const filters = useMemo(
    () => ({
      account_id: accountId,
    }),
    [accountId],
  );

  const {
    contacts = [],
    contactsCount = 0,
    contactsLoading = false,
    contactsError = null,
  } = useGetContacts({
    page,
    pageSize: validPageSize,
    search,
    ordering,
    filters,
  });

  // Build SWR key for cache revalidation
  const swrKey = useMemo(() => {
    const params = new URLSearchParams();
    params.append("page", page);
    params.append("page_size", validPageSize);
    params.append("account_id", accountId);
    if (search) params.append("search", search);
    if (ordering) params.append("ordering", ordering);
    return tenantKey(`/contacts/?${params.toString()}`, tenantId);
  }, [page, validPageSize, accountId, search, ordering, tenantId]);

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
    setSorting((prevSorting) => {
      return typeof updaterOrValue === "function"
        ? updaterOrValue(prevSorting)
        : updaterOrValue;
    });
  }, []);

  // Modal handlers
  const handleAddContact = useCallback(() => {
    setSelectedContact(null);
    setContactModal(true);
  }, []);

  const handleEditContact = useCallback((contact) => {
    setSelectedContact(contact);
    setContactModal(true);
  }, []);

  const handleDeleteContact = useCallback((contact) => {
    setContactToDelete(contact);
    setDeleteModal(true);
  }, []);

  const handleCloseDeleteDialog = useCallback(() => {
    setDeleteModal(false);
    setContactToDelete(null);
  }, []);

  // ==============================|| EXPANDED ROW CONTENT ||============================== //

  const renderExpandedContent = useCallback((row) => {
    return <ExpandingContactDetail data={row.original} />;
  }, []);

  // ==============================|| PREFILLED ACCOUNT FOR CREATE ||============================== //

  const prefilledAccount = useMemo(() => {
    if (!account) return null;
    return {
      id: account.id,
      company_name: account.company_name,
    };
  }, [account]);

  // ==============================|| COLUMNS DEFINITION ||============================== //

  const columns = useMemo(
    () => [
      // Name Column (with job title subtitle)
      {
        header: "Name",
        id: "full_name",
        accessorKey: "full_name",
        cell: ({ row }) => {
          const contact = row.original;
          const fullName =
            contact.full_name ||
            `${contact.first_name || ""} ${contact.last_name || ""}`.trim();

          return (
            <Stack spacing={0}>
              <Typography variant="subtitle2">
                {fullName || "Unknown"}
              </Typography>
              {contact.job_title && (
                <Typography variant="caption" color="text.secondary">
                  {contact.job_title}
                </Typography>
              )}
            </Stack>
          );
        },
      },
      // Department Column
      {
        header: "Department",
        id: "department_name",
        accessorKey: "department_name",
        cell: ({ getValue }) => {
          const value = getValue();
          return value ? (
            <Typography variant="body2">{value}</Typography>
          ) : (
            <Typography variant="body2" color="text.disabled">
              —
            </Typography>
          );
        },
      },
      // Email Column
      {
        header: "Email",
        id: "email",
        accessorKey: "email",
        cell: ({ getValue }) => {
          const value = getValue();
          return value ? (
            <Typography variant="body2" sx={{ wordBreak: "break-all" }}>
              {value}
            </Typography>
          ) : (
            <Typography variant="body2" color="text.disabled">
              —
            </Typography>
          );
        },
      },
      // Phone Column
      {
        header: "Phone",
        id: "phone_number",
        accessorKey: "phone_number",
        cell: ({ getValue }) => {
          const value = getValue();
          return value ? (
            <Typography variant="body2">{value}</Typography>
          ) : (
            <Typography variant="body2" color="text.disabled">
              —
            </Typography>
          );
        },
      },
      // Influence Level Column
      {
        header: "Influence",
        id: "influence_level",
        accessorKey: "influence_level",
        cell: ({ row }) => {
          const contact = row.original;
          if (
            !contact.influence_level ||
            contact.influence_level === "UNKNOWN"
          ) {
            return (
              <Typography variant="body2" color="text.disabled">
                —
              </Typography>
            );
          }
          return (
            <Chip
              label={contact.influence_level_display || contact.influence_level}
              size="small"
              color={INFLUENCE_COLORS[contact.influence_level] || "default"}
              variant="light"
            />
          );
        },
      },
      // Opt-out Column
      {
        header: "Opt-out",
        id: "opted_out",
        accessorKey: "opted_out",
        cell: ({ getValue }) => {
          return getValue() ? (
            <Chip
              label="Opted out"
              size="small"
              color="error"
              variant="light"
            />
          ) : (
            <Typography variant="body2" color="text.disabled">
              —
            </Typography>
          );
        },
      },
      // Actions Column
      {
        header: "Actions",
        id: "actions",
        meta: { className: "cell-center" },
        disableSortBy: true,
        enableSorting: false,
        cell: ({ row }) => {
          const isExpanded = row.getIsExpanded();

          return (
            <Stack
              direction="row"
              alignItems="center"
              justifyContent="center"
              spacing={0}
            >
              <Tooltip title={isExpanded ? "Collapse" : "View"}>
                <IconButton
                  color={isExpanded ? "primary" : "secondary"}
                  onClick={(e) => {
                    e.stopPropagation();
                    row.toggleExpanded();
                  }}
                >
                  {isExpanded ? (
                    <PlusOutlined style={{ transform: "rotate(45deg)" }} />
                  ) : (
                    <EyeOutlined />
                  )}
                </IconButton>
              </Tooltip>
              <Tooltip title="Add to Campaign">
                <IconButton
                  color="secondary"
                  onClick={(e) => {
                    e.stopPropagation();
                    setCampaignContact(row.original);
                    setCampaignModal(true);
                  }}
                >
                  <AimOutlined />
                </IconButton>
              </Tooltip>
              <Tooltip title="Edit">
                <IconButton
                  color="secondary"
                  onClick={(e) => {
                    e.stopPropagation();
                    handleEditContact(row.original);
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
                    handleDeleteContact(row.original);
                  }}
                >
                  <DeleteOutlined />
                </IconButton>
              </Tooltip>
            </Stack>
          );
        },
      },
    ],
    [handleEditContact, handleDeleteContact],
  );

  // ==============================|| RENDER ||============================== //

  return (
    <Box>
      <ReusableTable
        data={contacts}
        columns={columns}
        loading={contactsLoading}
        error={contactsError}
        swrKey={swrKey}
        modalToggler={handleAddContact}
        totalCount={contactsCount}
        currentPage={page}
        onPaginationChange={handlePaginationChange}
        onSearchChange={handleSearchChange}
        initialPageSize={validPageSize}
        sorting={sorting}
        onSortingChange={handleSortingChange}
        addButtonLabel="Add Contact"
        addButtonTooltip="Add new contact to this account"
        searchPlaceholder="Search contacts..."
        exportFilename={`contacts-${accountId}.csv`}
        emptyMessage="No contacts found"
        emptyDescription="Add contacts to this account to get started"
        enableExpanding={true}
        expandedRowContent={renderExpandedContent}
        enableImport={false}
      />

      {/* Contact Modal (Add/Edit) */}
      <ContactModal
        open={contactModal}
        modalToggler={setContactModal}
        contact={selectedContact}
        prefilledAccount={prefilledAccount}
      />

      {/* Delete Confirmation */}
      <AlertContactDelete
        contact={contactToDelete}
        open={deleteModal}
        handleClose={handleCloseDeleteDialog}
      />

      {/* Add to Campaign */}
      {campaignModal && campaignContact && (
        <AddToCampaignModal
          open={campaignModal}
          onClose={() => {
            setCampaignModal(false);
            setCampaignContact(null);
          }}
          accountId={accountId}
          accountName={account?.company_name}
          preselectedContactId={campaignContact.id}
        />
      )}
    </Box>
  );
}

AccountContactsTab.propTypes = {
  accountId: PropTypes.string.isRequired,
  account: PropTypes.shape({
    id: PropTypes.string,
    company_name: PropTypes.string,
  }),
};
