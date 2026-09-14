import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
    // Windows bind mounts don't forward inotify events into the container,
    // so the dev server keeps serving stale modules without polling.
    watch: { usePolling: true, interval: 300 },
  },
});
