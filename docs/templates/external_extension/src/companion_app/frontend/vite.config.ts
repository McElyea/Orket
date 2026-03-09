import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  base: "/static/",
  server: {
    host: "127.0.0.1",
    port: 5173,
  },
  build: {
    outDir: "../static",
    emptyOutDir: true,
    cssCodeSplit: false,
    rollupOptions: {
      output: {
        entryFileNames: "app.js",
        chunkFileNames: "chunks/[name].js",
        assetFileNames: (assetInfo) => {
          const name = String(assetInfo.name || "");
          if (name.endsWith(".css")) {
            return "styles.css";
          }
          return "assets/[name][extname]";
        },
        manualChunks: undefined,
      },
    },
  },
});
