import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const apiProxyTarget = env.VITE_API_PROXY_TARGET || "http://127.0.0.1:8000";

  return {
    plugins: [react()],
    build: {
      rollupOptions: {
        output: {
          manualChunks(id) {
            const normalizedId = id.replaceAll("\\", "/");

            const isPackage = (name: string): boolean =>
              normalizedId.includes(`/node_modules/${name}/`);

            if (id.includes("node_modules")) {
              if (
                isPackage("react") ||
                isPackage("react-dom") ||
                isPackage("scheduler") ||
                isPackage("use-sync-external-store")
              ) {
                return "vendor-react";
              }
              if (isPackage("axios")) {
                return "vendor-axios";
              }
              if (isPackage("zustand")) {
                return "vendor-state";
              }
              if (isPackage("dayjs")) {
                return "vendor-dayjs";
              }
              if (
                isPackage("@ant-design/pro-table") ||
                isPackage("@ant-design/pro-field") ||
                isPackage("@ant-design/pro-form")
              ) {
                return "vendor-pro-table";
              }
              if (
                isPackage("@ant-design/pro-layout") ||
                isPackage("@ant-design/pro-card") ||
                isPackage("@ant-design/pro-provider") ||
                isPackage("@umijs/route-utils") ||
                isPackage("@umijs/use-params")
              ) {
                return "vendor-pro-layout";
              }
              // Merge antd + rc- + icons into one chunk to eliminate
              // circular chunk warnings (antd <-> rc- <-> antd)
              if (
                isPackage("antd") ||
                isPackage("@ant-design/cssinjs") ||
                isPackage("@ant-design/cssinjs-utils") ||
                isPackage("@ant-design/colors") ||
                isPackage("@ant-design/fast-color") ||
                normalizedId.includes("/node_modules/rc-") ||
                isPackage("@rc-component") ||
                isPackage("@ant-design/icons") ||
                isPackage("@ant-design/icons-svg")
              ) {
                return "vendor-antd";
              }
              return undefined;
            }

            return undefined;
          },
        },
      },
    },
    server: {
      host: "0.0.0.0",
      port: 5174,
      strictPort: true,
      proxy: {
        "/api": {
          target: apiProxyTarget,
          changeOrigin: true,
          agent: false,
        },
      },
    },
  };
});
