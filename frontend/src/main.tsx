import React from "react";
import ReactDOM from "react-dom/client";

import "@fontsource/inter/latin-400.css";
import "@fontsource/inter/latin-500.css";
import "@fontsource/inter/latin-600.css";
import "@fontsource/inter/latin-700.css";
import "@fontsource/inter/latin-800.css";
import "@fontsource/manrope/latin-400.css";
import "@fontsource/manrope/latin-500.css";
import "@fontsource/manrope/latin-600.css";
import "@fontsource/manrope/latin-700.css";
import "@fontsource/manrope/latin-800.css";
import "@fontsource/ibm-plex-mono/latin-500.css";
import "@fontsource/ibm-plex-mono/latin-600.css";
import "@ant-design/v5-patch-for-react-19";
import { App as AntdApp, ConfigProvider, theme } from "antd";

import App from "./App";
import { ErrorBoundary } from "./components/ErrorBoundary";
import "antd/dist/reset.css";
import "./styles/admin.css";
import { initErrorTracker } from "./services/errorTracker";

initErrorTracker();

ReactDOM.createRoot(document.getElementById("root")!).render(
  <>
    <ConfigProvider
      theme={{
        algorithm: theme.defaultAlgorithm,
        token: {
          borderRadius: 12,
          colorBgBase: "#f5f7fa",
          colorBgContainer: "#ffffff",
          colorBorder: "#d7e0ea",
          colorInfo: "#1677ff",
          colorPrimary: "#1677ff",
          colorSuccess: "#52c41a",
          colorText: "#1f2937",
          colorTextSecondary: "#64748b",
          colorWarning: "#faad14",
          controlHeight: 36,
          fontFamily:
            '"Inter", "Segoe UI", "PingFang SC", "Microsoft YaHei", "Noto Sans SC", sans-serif',
        },
        components: {
          Layout: {
            bodyBg: "#f5f7fa",
            headerBg: "#ffffff",
            siderBg: "#0f172a",
            triggerBg: "#0f172a",
            triggerColor: "#dbe4f0",
          },
          Menu: {
            darkItemBg: "#0f172a",
            darkItemColor: "#cbd5e1",
            darkItemHoverBg: "#162033",
            darkItemSelectedBg: "#1677ff",
            darkItemSelectedColor: "#ffffff",
            darkSubMenuItemBg: "#111827",
            groupTitleColor: "#8ea0b8",
          },
          Card: {
            borderRadiusLG: 14,
          },
          Table: {
            borderColor: "#e2e8f0",
          },
        },
      }}
    >
      <AntdApp>
        <ErrorBoundary>
          <App />
        </ErrorBoundary>
      </AntdApp>
    </ConfigProvider>
  </>
);
