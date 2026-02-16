import { defineConfig } from "astro/config";
import react from "@astrojs/react";
import node from "@astrojs/node";
import path from "node:path";

export default defineConfig({
  output: "server",
  adapter: node({ mode: "standalone" }),
  integrations: [
    react()
  ],
  vite: {
    resolve: {
      alias: {
        "@": path.resolve("src"),
        "next/link": path.resolve("src/compat/next-link.tsx"),
        "next/navigation": path.resolve("src/compat/next-navigation.ts"),
        "next/server": path.resolve("src/compat/next-server.ts")
      }
    }
  }
});
