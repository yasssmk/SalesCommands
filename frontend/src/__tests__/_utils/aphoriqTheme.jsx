// frontend/src/__tests__/_utils/aphoriqTheme.jsx
//
// Minimal theme provider for unit tests that render components consuming
// theme.aphoriQ.* / theme.iconSizes.*. Builds a real MUI theme from the
// default palette and attaches the project's aphoriQ + iconSizes namespaces
// via the same factories used by the app (themes/index.jsx) — no next/font or
// emotion SSR machinery required.

import { createTheme, ThemeProvider } from "@mui/material/styles";
import AphoriQ from "themes/aphoriq";
import IconSizes from "themes/iconSizes";

const base = createTheme();
const testTheme = createTheme(base, {
  iconSizes: IconSizes(),
  aphoriQ: AphoriQ(base),
});

export default function AphoriqTheme({ children }) {
  return <ThemeProvider theme={testTheme}>{children}</ThemeProvider>;
}

export { testTheme };
