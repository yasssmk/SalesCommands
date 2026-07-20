// frontend/src/sections/businessData/products/ProductCatalogModal.jsx
"use client";

import PropTypes from "prop-types";
import { useMemo } from "react";

// material-ui
import Box from "@mui/material/Box";
import Modal from "@mui/material/Modal";
import Stack from "@mui/material/Stack";

// project imports
import FormProductCatalogAdd from "./FormProductCatalogAdd";
import FormProductCatalogEdit from "./FormProductCatalogEdit";
import MainCard from "components/MainCard";
import CircularWithPath from "components/@extended/progress/CircularWithPath";

// api
import { useGetProductCatalogEntries } from "api/businessData/productCatalog";

// ==============================|| PRODUCT CATALOG MODAL ||============================== //

/**
 * Wrapper modal that displays either FormProductCatalogAdd or
 * FormProductCatalogEdit based on whether an entry is provided.
 *
 * Mirrors TechCatalogModal — the loading state is keyed off the entries
 * list query so the modal won't open while the underlying collection is
 * still loading, preventing flashes of stale data on mid-fetch mount.
 *
 * The edit form is seeded from the row object passed in `entry`; there is
 * no per-entry detail fetch (the list serializer carries every editable
 * field).
 *
 * @param {boolean}  open         - Modal open state
 * @param {Function} modalToggler - Setter for the modal open state
 * @param {Object}   entry        - Entry object for edit mode (null for create)
 */
export default function ProductCatalogModal({ open, modalToggler, entry }) {
  const { entriesLoading: loading } = useGetProductCatalogEntries();

  const closeModal = () => modalToggler(false);

  const form = useMemo(() => {
    if (loading) return null;
    return entry && entry.id ? (
      <FormProductCatalogEdit entry={entry} closeModal={closeModal} />
    ) : (
      <FormProductCatalogAdd closeModal={closeModal} />
    );
    // closeModal is a stable function for the modal lifecycle; including
    // it in deps would re-render on every parent render without changing
    // behaviour. Consistent with TechCatalogModal.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [entry, loading]);

  return (
    <>
      {open && (
        <Modal
          open={open}
          onClose={closeModal}
          aria-labelledby="modal-product-catalog-label"
          aria-describedby="modal-product-catalog-description"
          sx={{
            "& .MuiPaper-root:focus": { outline: "none" },
          }}
        >
          <MainCard
            sx={{
              width: `calc(100% - 48px)`,
              minWidth: 340,
              maxWidth: 720,
              height: "auto",
              maxHeight: "calc(100vh - 48px)",
            }}
            modal
            content={false}
          >
            {/* Native scroll container — mirrors TechCatalogModal. */}
            <Box
              sx={{
                maxHeight: "calc(100vh - 48px)",
                overflowY: "auto",
                WebkitOverflowScrolling: "touch",
                overscrollBehavior: "contain",
                "& > :last-child": { marginBottom: 0, paddingBottom: 0 },
              }}
            >
              {loading ? (
                <Box sx={{ p: 5 }}>
                  <Stack direction="row" justifyContent="center">
                    <CircularWithPath />
                  </Stack>
                </Box>
              ) : (
                form
              )}
            </Box>
          </MainCard>
        </Modal>
      )}
    </>
  );
}

ProductCatalogModal.propTypes = {
  open: PropTypes.bool,
  modalToggler: PropTypes.func,
  entry: PropTypes.object,
};
