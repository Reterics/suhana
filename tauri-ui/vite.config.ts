import { defineConfig } from "vite";
import preact from "@preact/preset-vite";
import { configDefaults } from "vitest/config";

// @ts-expect-error process is a nodejs global
const host = process.env.TAURI_DEV_HOST;

export default defineConfig({
  plugins: [preact()],
  clearScreen: false,
  server: {
    port: 1420,
    strictPort: true,
    host: host || false,
    hmr: host
      ? {
          protocol: "ws",
          host,
          port: 1421,
        }
      : undefined,
    watch: {
      ignored: ["**/src-tauri/**"],
    },
  },
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: ['./jest.setup.ts'],
    exclude: [...configDefaults.exclude, "**/src-tauri/**"],
    coverage: {
      provider: "v8",
      enabled: true,
      ignoreEmptyLines: true,
      reporter: ["text", "json", "html", "lcov"],
      exclude: [
        ...configDefaults.coverage.exclude,
        "**/*.config.js",
        "**/*.{test,spec}.{ts,tsx}",
        "**/src-tauri/**",
      ],
    }
  },
});
