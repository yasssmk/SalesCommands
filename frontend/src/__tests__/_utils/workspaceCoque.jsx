// frontend/src/__tests__/_utils/workspaceCoque.jsx
//
// Test harness for the single workspace drawer coque (B3.5.x). A caller no
// longer mounts its own signal drawer: clicking a signal calls openDrawer, and
// the shared WorkspaceDrawer coque (a flex sibling of the main column, provided
// by WorkspaceLayout in the app) renders the injected detail. This wrapper
// reproduces that environment for unit tests — the aphoriQ theme the coque
// reads, the WorkspaceDrawerProvider, and the WorkspaceDrawer sibling — so an
// integration test can click a row and observe the detail (Close drawer +
// lifecycle actions) exactly as in the real workspace.
//
// Use as the React Testing Library `wrapper`.

import Box from "@mui/material/Box";

import AphoriqTheme from "./aphoriqTheme";
import { WorkspaceDrawerProvider } from "contexts/WorkspaceDrawerContext";
import WorkspaceDrawer from "components/WorkspaceDrawer";

export default function WorkspaceCoque({ children }) {
  return (
    <AphoriqTheme>
      <WorkspaceDrawerProvider>
        <Box sx={{ display: "flex", alignItems: "flex-start" }}>
          <Box sx={{ flexGrow: 1, minWidth: 0 }}>{children}</Box>
          <WorkspaceDrawer />
        </Box>
      </WorkspaceDrawerProvider>
    </AphoriqTheme>
  );
}
