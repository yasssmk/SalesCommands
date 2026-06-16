// frontend/src/sections/accounts/dc-workspace/ManagerNotesThread.jsx

"use client";

import PropTypes from "prop-types";
import { useState, useCallback, useRef, useEffect } from "react";

// MUI
import Avatar from "@mui/material/Avatar";
import Box from "@mui/material/Box";
import CircularProgress from "@mui/material/CircularProgress";
import IconButton from "@mui/material/IconButton";
import Stack from "@mui/material/Stack";
import TextField from "@mui/material/TextField";
import Tooltip from "@mui/material/Tooltip";
import Typography from "@mui/material/Typography";

// Icons
import {
  DeleteOutlined,
  MessageOutlined,
  SendOutlined,
} from "@ant-design/icons";

// Project imports
import {
  useGetManagerNotes,
  createManagerNote,
  deleteManagerNote,
} from "api/accounts/decisionCycles";
import useUserPermissions from "hooks/useUserPermissions";
import {
  displaySuccessSnackbar,
  displayErrorSnackbar,
} from "utils/displayError";

// ==============================|| NOTE BUBBLE ||============================== //

function NoteBubble({ note, canDelete, onDelete }) {
  const initials = (note.author_name || "?")
    .split(" ")
    .map((w) => w[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();

  const dateStr = note.created_at
    ? new Date(note.created_at).toLocaleDateString("en-US", {
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      })
    : "";

  return (
    <Stack direction="row" spacing={1.5} alignItems="flex-start">
      <Avatar sx={{ width: 32, height: 32, fontSize: "0.75rem", mt: 0.25 }}>
        {initials}
      </Avatar>
      <Box sx={{ flex: 1, minWidth: 0 }}>
        <Stack direction="row" spacing={1} alignItems="baseline">
          <Typography variant="subtitle2" fontWeight={600}>
            {note.author_name || "Unknown"}
          </Typography>
          <Typography variant="caption" color="text.secondary">
            {dateStr}
          </Typography>
        </Stack>
        <Typography
          variant="body2"
          sx={{ mt: 0.25, whiteSpace: "pre-wrap", wordBreak: "break-word" }}
        >
          {note.content}
        </Typography>
      </Box>
      {canDelete && (
        <Tooltip title="Delete note">
          <IconButton size="small" onClick={() => onDelete(note.id)}>
            <DeleteOutlined style={{ fontSize: 14 }} />
          </IconButton>
        </Tooltip>
      )}
    </Stack>
  );
}

NoteBubble.propTypes = {
  note: PropTypes.shape({
    id: PropTypes.string.isRequired,
    content: PropTypes.string.isRequired,
    author_name: PropTypes.string,
    created_by: PropTypes.string,
    created_at: PropTypes.string,
  }).isRequired,
  canDelete: PropTypes.bool,
  onDelete: PropTypes.func.isRequired,
};

// ==============================|| MANAGER NOTES THREAD ||============================== //

export default function ManagerNotesThread({ cycleId }) {
  const { notes, notesLoading, notesError, mutateNotes } =
    useGetManagerNotes(cycleId);
  const { isAdmin, isManager, currentUserId } = useUserPermissions();

  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const bottomRef = useRef(null);

  const canWrite = isAdmin || isManager;

  // Auto-scroll on new notes
  useEffect(() => {
    if (bottomRef.current) {
      bottomRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [notes.length]);

  // Chronological order (oldest first) — backend returns newest first
  const sortedNotes = [...notes].reverse();

  const handleSend = useCallback(async () => {
    const content = draft.trim();
    if (!content || sending) return;

    setSending(true);
    const result = await createManagerNote(cycleId, content);
    if (result.success) {
      setDraft("");
      mutateNotes();
    } else {
      displayErrorSnackbar(result);
    }
    setSending(false);
  }, [cycleId, draft, sending, mutateNotes]);

  const handleDelete = useCallback(
    async (noteId) => {
      const result = await deleteManagerNote(cycleId, noteId);
      if (result.success) {
        displaySuccessSnackbar("Note deleted");
        mutateNotes();
      } else {
        displayErrorSnackbar(result);
      }
    },
    [cycleId, mutateNotes],
  );

  const handleKeyDown = useCallback(
    (e) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleSend();
      }
    },
    [handleSend],
  );

  // Loading
  if (notesLoading) {
    return (
      <Box
        display="flex"
        justifyContent="center"
        alignItems="center"
        minHeight="200px"
      >
        <CircularProgress size={28} />
      </Box>
    );
  }

  // Error
  if (notesError) {
    return (
      <Box
        display="flex"
        justifyContent="center"
        alignItems="center"
        minHeight="200px"
      >
        <Typography color="error">Failed to load notes</Typography>
      </Box>
    );
  }

  return (
    <Box
      sx={{
        display: "flex",
        flexDirection: "column",
        height: "100%",
        minHeight: 300,
        maxHeight: 600,
      }}
    >
      {/* Thread */}
      <Box
        sx={{
          flex: 1,
          overflowY: "auto",
          px: 2,
          py: 1.5,
          border: 1,
          borderColor: "divider",
          borderRadius: 1.5,
        }}
      >
        {sortedNotes.length === 0 ? (
          <Box
            display="flex"
            flexDirection="column"
            justifyContent="center"
            alignItems="center"
            sx={{ py: 6 }}
          >
            <MessageOutlined
              style={{ fontSize: 32, color: "#8c8c8c", marginBottom: 8 }}
            />
            <Typography color="text.secondary" variant="body2">
              No coaching notes yet.
            </Typography>
            {canWrite && (
              <Typography variant="caption" color="text.secondary">
                Post a note to guide the deal strategy.
              </Typography>
            )}
          </Box>
        ) : (
          <Stack spacing={2}>
            {sortedNotes.map((note) => {
              const isAuthor =
                currentUserId && note.created_by === currentUserId;
              return (
                <NoteBubble
                  key={note.id}
                  note={note}
                  canDelete={isAuthor || isAdmin}
                  onDelete={handleDelete}
                />
              );
            })}
            <div ref={bottomRef} />
          </Stack>
        )}
      </Box>

      {/* Input — manager/admin only */}
      {canWrite && (
        <Stack direction="row" spacing={1} sx={{ mt: 1.5 }}>
          <TextField
            fullWidth
            size="small"
            multiline
            maxRows={4}
            placeholder="Add a coaching note…"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={sending}
          />
          <IconButton
            color="primary"
            onClick={handleSend}
            disabled={sending || !draft.trim()}
            sx={{ alignSelf: "flex-end" }}
          >
            {sending ? (
              <CircularProgress size={18} />
            ) : (
              <SendOutlined style={{ fontSize: 18 }} />
            )}
          </IconButton>
        </Stack>
      )}
    </Box>
  );
}

ManagerNotesThread.propTypes = {
  cycleId: PropTypes.string.isRequired,
};
