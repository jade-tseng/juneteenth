import { defineConfig } from "vite";

// Static SPA. Served from GCS/CDN in production (per §7); base "./" keeps
// asset paths relative so it works from any bucket path.
export default defineConfig({
  base: "./",
  server: {
    port: 5173,
    open: true,
    // Same-origin proxy to the backend in dev so /api/sign works without CORS
    // fuss (the backend already sets CORS; the proxy keeps it same-origin).
    proxy: {
      "/api": { target: "http://localhost:8080", changeOrigin: true },
    },
  },
  build: { target: "es2022", sourcemap: true },
});
