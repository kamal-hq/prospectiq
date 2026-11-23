import fs from "node:fs";
import path from "node:path";
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

const hasLocalEnv =
  fs.existsSync(path.resolve(__dirname, ".env")) ||
  fs.existsSync(path.resolve(__dirname, ".env.local"));

export default defineConfig({
  // Locally reads repo-root `.env` if no `web/.env*` exists; on Vercel reads process.env directly.
  // Only `VITE_*` and `NEXT_PUBLIC_*` variables are exposed to the client bundle — NEVER private keys.
  envDir: hasLocalEnv ? __dirname : path.resolve(__dirname, ".."),
  envPrefix: ["VITE_", "NEXT_PUBLIC_"],
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    host: "localhost",
    port: 5173,
    strictPort: true,
  },
  preview: {
    host: "localhost",
    port: 4173,
  },
});
