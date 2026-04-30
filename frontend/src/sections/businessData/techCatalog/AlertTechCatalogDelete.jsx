// src/sections/businessData/techCatalog/AlertTechCatalogDelete.jsx

import PropTypes from "prop-types";
import { useState } from "react";

// material-ui
import Button from "@mui/material/Button";
import Dialog from "@mui/material/Dialog";
import DialogContent from "@mui/material/DialogContent";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";

// project imports
import Avatar from "components/@extended/Avatar";
import { PopupTransition } from "components/@extended/Transitions";
import { deleteTechCatalogEntry } from "api/businessData/techCatalog";
import {
  displayErrorSnackbar,
  displaySuccessSnackbar,
} from "utils/displayError";

// assets
import DeleteFilled from "@ant-design/icons/DeleteFilled";

// ==============================|| TECH CATALOG - DELETE ALERT ||============================== //

/**
 * Confirmation dialog for single tech catalog entry deletion.
 *
 * Hard delete — no soft-delete flag on the model. The admin must
 * confirm explicitly. Downstream FK relations (DC ↔ TechCatalog,
 * Product ↔ TechCatalog, Signal ↔ TechCatalog, when they ship) will
 * govern the cascade behaviour through their own on_delete settings;
 * this dialog doesn't try to surface that since those modules don't
 * exist yet.
 *
 * @param {Object}   entry       - Entry to delete (with id, company_name, product_name)
 * @param {boolean}  open        - Dialog open state
 * @param {Function} handleClose - Function to close the dialog
 */
export default function AlertTechCatalogDelete({ entry, open, handleClose }) {
  const [deleting, setDeleting] = useState(false);

  const deleteHandler = async () => {
    if (!entry?.id) return;

    try {
      setDeleting(true);
      const result = await deleteTechCatalogEntry(entry.id);

      if (result?.success) {
        displaySuccessSnackbar("Tech catalog entry deleted successfully");
        handleClose?.();
      } else {
        displayErrorSnackbar(result);
        // Modal stays open on error so the user sees the message
        // and can retry or cancel explicitly.
      }
    } catch (err) {
      displayErrorSnackbar(err);
    } finally {
      setDeleting(false);
    }
  };

  // Display name — collapse "Notion / Notion" to "Notion" when
  // company and product share the same name, mirroring the model's
  // __str__ logic.
  const displayName =
    entry?.company_name && entry?.product_name
      ? entry.company_name === entry.product_name
        ? entry.company_name
        : `${entry.company_name} / ${entry.product_name}`
      : entry?.company_name || "";

  return (
    <Dialog
      open={open}
      onClose={handleClose}
      keepMounted
      TransitionComponent={PopupTransition}
      maxWidth="xs"
      aria-labelledby="tech-catalog-delete-title"
      aria-describedby="tech-catalog-delete-description"
    >
      <DialogContent sx={{ mt: 2, my: 1 }}>
        <Stack alignItems="center" spacing={3.5}>
          <Avatar
            color="error"
            sx={{ width: 72, height: 72, fontSize: "1.75rem" }}
          >
            <DeleteFilled />
          </Avatar>

          <Stack spacing={2}>
            <Typography variant="h4" align="center">
              Are you sure you want to delete?
            </Typography>
            <Typography align="center">
              By deleting{" "}
              <Typography variant="subtitle1" component="span">
                &quot;{displayName}&quot;{" "}
              </Typography>
              from the tech catalog, this entry will be permanently removed.
            </Typography>
          </Stack>

          <Stack direction="row" spacing={2} sx={{ width: 1 }}>
            <Button
              fullWidth
              onClick={handleClose}
              color="secondary"
              variant="outlined"
              disabled={deleting}
            >
              Cancel
            </Button>
            <Button
              fullWidth
              color="error"
              variant="contained"
              onClick={deleteHandler}
              autoFocus
              disabled={deleting}
            >
              {deleting ? "Deleting..." : "Delete"}
            </Button>
          </Stack>
        </Stack>
      </DialogContent>
    </Dialog>
  );
}

AlertTechCatalogDelete.propTypes = {
  entry: PropTypes.shape({
    id: PropTypes.string,
    company_name: PropTypes.string,
    product_name: PropTypes.string,
  }),
  open: PropTypes.bool,
  handleClose: PropTypes.func,
};
