import React from "react";
import ReactDOM from "react-dom/client";

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
            '"Segoe UI", "PingFang SC", "Microsoft YaHei", "Noto Sans SC", sans-serif',
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
