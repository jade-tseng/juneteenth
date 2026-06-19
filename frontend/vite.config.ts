import { defineConfig } from "vite";

// Static SPA. Served from GCS/CDN in production (per §7); base "./" keeps
// asset paths relative so it works from any bucket path.
export default defineConfig({
  base: "./",
  server: { port: 5173, open: true },
  build: { target: "es2022", sourcemap: true },
});
