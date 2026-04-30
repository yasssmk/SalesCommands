// frontend/src/sections/businessData/techCatalog/TechCatalogModal.jsx
"use client";

import PropTypes from "prop-types";
import { useMemo } from "react";

// material-ui
import Box from "@mui/material/Box";
import Modal from "@mui/material/Modal";
import Stack from "@mui/material/Stack";

// project imports
import FormTechCatalogAdd from "./FormTechCatalogAdd";
import FormTechCatalogEdit from "./FormTechCatalogEdit";
import MainCard from "components/MainCard";
import CircularWithPath from "components/@extended/progress/CircularWithPath";

// api
import { useGetTechCatalogEntries } from "api/businessData/techCatalog";

// ==============================|| TECH CATALOG MODAL ||============================== //

/**
 * Wrapper modal that displays either FormTechCatalogAdd or
 * FormTechCatalogEdit based on whether an entry is provided.
 *
 * Mirrors AccountModal exactly — the loading state is keyed off the
 * entries list query so the modal won't open while the underlying
 * collection is still loading. This prevents flashes of stale data
 * when the modal mounts mid-fetch.
 *
 * @param {boolean}  open         - Modal open state
 * @param {Function} modalToggler - Setter for the modal open state
 * @param {Object}   entry        - Entry object for edit mode (null for create)
 */
export default function TechCatalogModal({ open, modalToggler, entry }) {
  const { entriesLoading: loading } = useGetTechCatalogEntries();

  const closeModal = () => modalToggler(false);

  const form = useMemo(() => {
    if (loading) return null;
    return entry && entry.id ? (
      <FormTechCatalogEdit
        entry={entry}
        entryId={entry.id}
        closeModal={closeModal}
      />
    ) : (
      <FormTechCatalogAdd closeModal={closeModal} />
    );
    // closeModal is a stable function reference for the modal lifecycle
    // — including it in deps would re-render on every parent render
    // without changing behaviour. eslint-disable-next-line keeps the
    // pattern consistent with AccountModal.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [entry, loading]);

  return (
    <>
      {open && (
        <Modal
          open={open}
          onClose={closeModal}
          aria-labelledby="modal-tech-catalog-label"
          aria-describedby="modal-tech-catalog-description"
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
            {/* Native scroll container — see AccountModal for the same pattern */}
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

TechCatalogModal.propTypes = {
  open: PropTypes.bool,
  modalToggler: PropTypes.func,
  entry: PropTypes.object,
};
