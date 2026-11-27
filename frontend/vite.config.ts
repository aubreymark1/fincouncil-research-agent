import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

// The production build is served by Caddy from the `dist` directory.
// During local development, `/api` is proxied to the FastAPI backend.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, ".", "");
  const apiTarget = env.VITE_API_TARGET || "http://127.0.0.1:8000";

  return {
    plugins: [react()],
    server: {
      port: 5173,
      proxy: {
        "/api": {
          target: apiTarget,
          changeOrigin: true,
        },
      },
    },
    build: {
      outDir: "dist",
      sourcemap: false,
    },
  };
});
