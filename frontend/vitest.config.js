// frontend/vitest.config.js
//
// Vitest configuration for the SalesCommands frontend.
//
// Packages used:
//   vitest           — Test runner (Vite-native, ESM-first, Jest-compatible API)
//   @vitest/ui       — Browser-based test explorer for interactive debugging
//   jsdom            — DOM implementation for simulating browser environment in Node
//   @testing-library/react    — React component testing utilities (render, screen, etc.)
//   @testing-library/jest-dom — Custom matchers for DOM assertions (toBeInTheDocument, etc.)
//   @testing-library/user-event — Simulates real user interactions (click, type, etc.)

import { defineConfig } from "vitest/config";
import path from "path";

export default defineConfig({
  test: {
    // jsdom simulates a browser DOM so React components can render in Node.
    environment: "jsdom",

    // Global setup: imports @testing-library/jest-dom matchers and shared mocks.
    setupFiles: ["./vitest.setup.js"],

    // File patterns — co-located tests next to source or in __tests__ dirs.
    include: ["src/**/*.{test,spec}.{js,jsx}"],

    // CI-friendly reporters: default console output + JUnit XML for GitHub Actions.
    reporters: ["default"],

    // Inline CSS module imports as identity objects (className stays the class name).
    css: { modules: { classNameStrategy: "non-scoped" } },

    // Increase timeout for slower CI environments.
    testTimeout: 10000,
  },

  resolve: {
    // Mirror jsconfig.json path aliases so test imports resolve identically to Next.js.
    alias: {
      // `react-csv` is imported by the table's CSV export leaf but isn't
      // installed in the test graph; alias it to a stub so the REAL ReusableTable
      // (and its sorting/pagination children) can mount under test.
      "react-csv": path.resolve(__dirname, "src/__tests__/_stubs/react-csv.jsx"),
      "@dnd-kit/core": path.resolve(__dirname, "src/__tests__/_stubs/dnd-kit-core.jsx"),
      components: path.resolve(__dirname, "src/components"),
      layout: path.resolve(__dirname, "src/layout"),
      hooks: path.resolve(__dirname, "src/hooks"),
      contexts: path.resolve(__dirname, "src/contexts"),
      themes: path.resolve(__dirname, "src/themes"),
      utils: path.resolve(__dirname, "src/utils"),
      sections: path.resolve(__dirname, "src/sections"),
      views: path.resolve(__dirname, "src/views"),
      "menu-items": path.resolve(__dirname, "src/menu-items"),
      api: path.resolve(__dirname, "src/api"),
      data: path.resolve(__dirname, "src/data"),
      // Bare `config` resolves to the theme-config file (as in jsconfig); more
      // specific config/* modules resolve to their file (Next does this via
      // baseUrl). Keep the specific entry BEFORE `config` so it wins.
      "config/formatters": path.resolve(__dirname, "src/config/formatters.js"),
      "config/swr": path.resolve(__dirname, "src/config/swr.js"),
      config: path.resolve(__dirname, "src/config/theme-config.js"),
    },
  },
});
