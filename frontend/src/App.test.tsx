import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import App from "./App";
import { useAppStore } from "./stores/appStore";

const hoisted = vi.hoisted(() => ({
  getMeMock: vi.fn(),
  isAuthenticatedMock: vi.fn(),
  clearAuthMock: vi.fn(),
  logoutMock: vi.fn(),
  changePasswordMock: vi.fn(),
  usePermissionsMock: vi.fn(),
  getUnreadCountMock: vi.fn(),
  getRecentNotificationsMock: vi.fn(),
  markNotificationsReadMock: vi.fn(),
  markAllNotificationsReadMock: vi.fn(),
}));

vi.mock("./services/adminAuth", () => ({
  adminAuth: {
    isAuthenticated: hoisted.isAuthenticatedMock,
    getMe: hoisted.getMeMock,
    clearAuth: hoisted.clearAuthMock,
    logout: hoisted.logoutMock,
    changePassword: hoisted.changePasswordMock,
  },
}));

vi.mock("./hooks/usePermissions", () => ({
  usePermissions: hoisted.usePermissionsMock,
}));

vi.mock("./services/notificationApi", () => ({
  getUnreadCount: hoisted.getUnreadCountMock,
  getRecentNotifications: hoisted.getRecentNotificationsMock,
  getSeverityColor: () => "default",
  getCategoryColor: () => "default",
  markNotificationsRead: hoisted.markNotificationsReadMock,
  markAllNotificationsRead: hoisted.markAllNotificationsReadMock,
}));

vi.mock("./components/GlobalSearch", () => ({
  GlobalSearch: () => <div data-testid="global-search" />,
}));

vi.mock("./pages/AgentsPage", () => ({
  AgentsPage: () => (
    <button
      aria-label="open-roles-workbench"
      type="button"
      onClick={() => {
        window.history.pushState({}, "", "/system/agents?agencyId=agency-1&tab=roles&role=agent");
        window.dispatchEvent(new PopStateEvent("popstate"));
      }}
    >
      open roles workbench
    </button>
  ),
}));

vi.mock("./pages/H5App", () => ({
  H5App: ({ locationKey }: { locationKey: string }) => (
    <div data-testid="h5-app">H5 route: {locationKey}</div>
  ),
}));

describe("App legacy roles compatibility routing", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "matchMedia",
      vi.fn().mockImplementation(() => ({
        matches: false,
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        addListener: vi.fn(),
        removeListener: vi.fn(),
        dispatchEvent: vi.fn(),
      }))
    );
    vi.stubGlobal(
      "getComputedStyle",
      vi.fn().mockImplementation(() => ({
        getPropertyValue: () => "",
      }))
    );

    window.history.replaceState({}, "", "/system/roles?agencyId=agency-1&role=agent");
    useAppStore.setState({
      activePage: "dashboard",
    });

    hoisted.isAuthenticatedMock.mockReset().mockReturnValue(true);
    hoisted.getMeMock.mockReset().mockResolvedValue({
      id: "admin-1",
      username: "root",
      display_name: "Root",
      role: "super_admin",
      user_type: "super_admin",
    });
    hoisted.clearAuthMock.mockReset();
    hoisted.logoutMock.mockReset().mockResolvedValue(undefined);
    hoisted.changePasswordMock.mockReset().mockResolvedValue(undefined);
    hoisted.usePermissionsMock.mockReset().mockReturnValue({
      canSeePage: () => true,
      loading: false,
    });
    hoisted.getUnreadCountMock.mockReset().mockResolvedValue(0);
    hoisted.getRecentNotificationsMock.mockReset().mockResolvedValue([]);
    hoisted.markNotificationsReadMock.mockReset().mockResolvedValue(undefined);
    hoisted.markAllNotificationsReadMock.mockReset().mockResolvedValue(0);
  });

  afterEach(() => {
    vi.clearAllMocks();
    vi.unstubAllGlobals();
    cleanup();
  });

  it("normalizes the legacy /system/roles entry into the canonical agents workbench route", async () => {
    render(<App />);

    await waitFor(() => {
      expect(window.location.pathname + window.location.search).toBe(
        "/system/agents?agencyId=agency-1&tab=roles&role=agent"
      );
      expect(useAppStore.getState().activePage).toBe("agents");
    });

    expect(window.location.pathname + window.location.search).toBe(
      "/system/agents?agencyId=agency-1&tab=roles&role=agent"
    );
    expect(useAppStore.getState().activePage).toBe("agents");
  });

  it("keeps the active workbench on the canonical agents page", async () => {
    window.history.replaceState({}, "", "/system/agents");
    useAppStore.setState({
      activePage: "dashboard",
    });

    render(<App />);

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "open-roles-workbench" })).toBeTruthy();
    });

    expect(useAppStore.getState().activePage).toBe("agents");
    expect(window.location.pathname).toBe("/system/agents");
  });

  it("navigates within the agents workbench without bouncing back to the legacy route", async () => {
    window.history.replaceState({}, "", "/system/agents");
    useAppStore.setState({
      activePage: "dashboard",
    });

    render(<App />);

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "open-roles-workbench" })).toBeTruthy();
    });

    screen.getByRole("button", { name: "open-roles-workbench" }).click();

    await waitFor(() => {
      expect(window.location.pathname + window.location.search).toBe(
        "/system/agents?agencyId=agency-1&tab=roles&role=agent"
      );
    });

    expect(useAppStore.getState().activePage).toBe("agents");
  });

  it("normalizes the legacy agent detail route into the single workbench route", async () => {
    window.history.replaceState({}, "", "/system/agents/agency-1?tab=roles&role=agent");
    useAppStore.setState({
      activePage: "dashboard",
    });

    render(<App />);

    await waitFor(() => {
      expect(window.location.pathname + window.location.search).toBe(
        "/system/agents?agencyId=agency-1&tab=roles&role=agent"
      );
    });

    expect(useAppStore.getState().activePage).toBe("agents");
  });

  it("preserves the edit tab when normalizing the legacy agent detail route", async () => {
    window.history.replaceState({}, "", "/system/agents/agency-1?tab=edit");
    useAppStore.setState({
      activePage: "dashboard",
    });

    render(<App />);

    await waitFor(() => {
      expect(window.location.pathname + window.location.search).toBe(
        "/system/agents?agencyId=agency-1&tab=edit"
      );
    });

    expect(useAppStore.getState().activePage).toBe("agents");
  });

  it("keeps the billing tab query instead of collapsing back to overview", async () => {
    window.history.replaceState({}, "", "/system/agents?agencyId=agency-1&tab=billing");
    useAppStore.setState({
      activePage: "dashboard",
    });

    render(<App />);

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "open-roles-workbench" })).toBeTruthy();
    });

    expect(window.location.pathname + window.location.search).toBe(
      "/system/agents?agencyId=agency-1&tab=billing"
    );
    expect(useAppStore.getState().activePage).toBe("agents");
  });

  it("keeps the canonical agents workbench query instead of collapsing back to the bare route", async () => {
    window.history.replaceState({}, "", "/system/agents?agencyId=agency-1&tab=roles&role=agent");
    useAppStore.setState({
      activePage: "dashboard",
    });

    render(<App />);

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "open-roles-workbench" })).toBeTruthy();
    });

    await waitFor(() => {
      expect(window.location.pathname + window.location.search).toBe(
        "/system/agents?agencyId=agency-1&tab=roles&role=agent"
      );
    });

    expect(useAppStore.getState().activePage).toBe("agents");
  });

  it("falls back to the dashboard when the retired H5 template market route is visited", async () => {
    window.history.replaceState({}, "", "/system/h5-templates");
    useAppStore.setState({
      activePage: "dashboard",
    });

    render(<App />);

    await waitFor(() => {
      expect(window.location.pathname).toBe("/");
    });

    expect(useAppStore.getState().activePage).toBe("dashboard");
  });

  it("renders the H5 app instead of the not-found page for /h5/login routes", async () => {
    window.history.replaceState({}, "", "/h5/login?site_key=mall-cn");

    render(<App />);

    await waitFor(() => {
      expect(screen.getByTestId("h5-app")).toBeTruthy();
    });

    expect(screen.queryByText("页面不存在或您没有访问权限")).toBeNull();
  });
});
