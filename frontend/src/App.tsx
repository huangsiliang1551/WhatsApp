import {
  Suspense,
  lazy,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ComponentType,
  type JSX,
} from "react";

import {
  ApartmentOutlined,
  AppstoreOutlined,
  AuditOutlined,
  BarChartOutlined,
  BellOutlined,
  BugOutlined,
  DashboardOutlined,
  DatabaseOutlined,
  FileTextOutlined,
  LogoutOutlined,
  KeyOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  MessageOutlined,
  MonitorOutlined,
  NodeIndexOutlined,
  PartitionOutlined,
  PictureOutlined,
  SafetyCertificateOutlined,
  SendOutlined,
  SettingOutlined,
  ShopOutlined,
  TagsOutlined,
  TeamOutlined,
  ThunderboltOutlined,
  UserOutlined,
  WarningFilled,
  WarningOutlined,
} from "@ant-design/icons";
import { Avatar, Badge, Button, Col, ConfigProvider, Divider, Dropdown, Input, Layout, List, Menu, Modal, Popover, Row, Space, Spin, Tag, Typography, message } from "antd";

import { AdminRoutePageShell } from "./components/AdminRoutePageShell";
import { ErrorBoundary } from "./components/ErrorBoundary";
import {
  buildAdminLocationKey,
  parseAdminLocationPrefill,
} from "./routes/adminUrlState";
import {
  CONSOLE_ROUTES,
  getConsolePath,
  getConsoleRouteById,
  groupedConsoleRoutes,
  resolveConsoleRoute,
} from "./routes/consoleRoutes";
import { usePermissions } from "./hooks/usePermissions";
import { useAppStore, type AppPageId } from "./stores/appStore";
import type {
  ConsoleRouteDefinition,
  ConsoleRouteGroup,
  ConsoleRouteIconKey,
} from "./types/console";
import { adminAuth, type AdminUser } from "./services/adminAuth";
import { GlobalSearch } from "./components/GlobalSearch";
import {
  getRecentNotifications,
  getUnreadCount,
  getSeverityColor,
  getCategoryColor,
  markAllNotificationsRead,
  markNotificationsRead,
  type NotificationItem,
} from "./services/notificationApi";

function lazyPage(loader: () => Promise<{ default: ComponentType<any> }>) {
  return lazy(loader);
}

const LazyDashboardPage = lazyPage(() =>
  import("./pages/DashboardPage").then((module) => ({ default: module.DashboardPage }))
);
const LazyChatPage = lazyPage(() =>
  import("./pages/ChatPage").then((module) => ({ default: module.ChatPage }))
);
const LazyMetaAccountsPage = lazyPage(() =>
  import("./pages/MetaAccountsPage").then((module) => ({ default: module.MetaAccountsPage }))
);
const LazyTemplatePage = lazyPage(() =>
  import("./pages/TemplatePage").then((module) => ({ default: module.TemplatePage }))
);
const LazySettingsPage = lazyPage(() =>
  import("./pages/SettingsPage").then((module) => ({ default: module.SettingsPage }))
);
const LazyMonitoringPage = lazyPage(() =>
  import("./pages/MonitoringPage").then((module) => ({ default: module.MonitoringPage }))
);
const LazyApiWebhooksPage = lazyPage(() =>
  import("./pages/ApiWebhooksPage").then((module) => ({ default: module.ApiWebhooksPage }))
);
const LazyWhatsAppStatsPage = lazyPage(() =>
  import("./pages/WhatsAppStatsPage").then((module) => ({
    default: module.WhatsAppStatsPage,
  }))
);
const LazyAuditPage = lazyPage(() =>
  import("./pages/AuditPage").then((module) => ({ default: module.AuditPage }))
);
const LazySystemLogsPage = lazyPage(() =>
  import("./pages/SystemLogsPage").then((module) => ({ default: module.SystemLogsPage }))
);
const LazyEvidenceCenterPage = lazyPage(() =>
  import("./pages/EvidenceCenterPage").then((module) => ({
    default: module.EvidenceCenterPage,
  }))
);
const LazyOrganizationSettingsPage = lazyPage(() =>
  import("./pages/OrganizationSettingsPage").then((module) => ({
    default: module.OrganizationSettingsPage,
  }))
);
const LazyMediaLibraryPage = lazyPage(() =>
  import("./pages/MediaLibraryPage").then((module) => ({
    default: module.MediaLibraryPage,
  }))
);
const LazyEcommercePage = lazyPage(() =>
  import("./pages/EcommercePage").then((module) => ({ default: module.EcommercePage }))
);
const LazyTaskRulesPage = lazyPage(() =>
  import("./pages/TaskRulesPage").then((module) => ({ default: module.TaskRulesPage }))
);
const LazyInviteManagementPage = lazyPage(() =>
  import("./pages/InviteManagementPage").then((module) => ({
    default: module.InviteManagementPage,
  }))
);
const LazyInviteRelationsPage = lazyPage(() =>
  import("./pages/InviteRelationsPage").then((module) => ({
    default: module.InviteRelationsPage,
  }))
);
const LazyInviteRewardsPage = lazyPage(() =>
  import("./pages/InviteRewardsPage").then((module) => ({
    default: module.InviteRewardsPage,
  }))
);
const LazyAudienceRulesPage = lazyPage(() =>
  import("./pages/AudienceRulesPage").then((module) => ({
    default: module.AudienceRulesPage,
  }))
);
const LazyTagsPage = lazyPage(() =>
  import("./pages/TagsPage").then((module) => ({ default: module.TagsPage }))
);
const LazyTasksPage = lazyPage(() =>
  import("./pages/TasksPage").then((module) => ({ default: module.TasksPage }))
);
const LazyReviewsPage = lazyPage(() =>
  import("./pages/ReviewsPage").then((module) => ({ default: module.ReviewsPage }))
);
const LazyTicketsPage = lazyPage(() =>
  import("./pages/TicketsPage").then((module) => ({ default: module.TicketsPage }))
);
const LazyUsersPage = lazyPage(() =>
  import("./pages/UsersPage").then((module) => ({ default: module.UsersPage }))
);
const LazyNotificationsPage = lazyPage(() =>
  import("./pages/NotificationsPage").then((module) => ({
    default: module.NotificationsPage,
  }))
);
const LazyIdentitySyncPage = lazyPage(() =>
  import("./pages/IdentitySyncPage").then((module) => ({
    default: module.IdentitySyncPage,
  }))
);
const LazyMemberAccessPage = lazyPage(() =>
  import("./pages/MemberAccessPage").then((module) => ({
    default: module.MemberAccessPage,
  }))
);
const LazySecuritySettingsPage = lazyPage(() =>
  import("./pages/SecuritySettingsPage").then((module) => ({
    default: module.SecuritySettingsPage,
  }))
);
const LazyAccessControlPage = lazyPage(() =>
  import("./pages/AccessControlPage").then((module) => ({
    default: module.AccessControlPage,
  }))
);
const LazyMembersPage = lazyPage(() =>
  import("./pages/MembersPage").then((module) => ({ default: module.MembersPage }))
);
const LazyAssignmentsPage = lazyPage(() =>
  import("./pages/AssignmentsPage").then((module) => ({
    default: module.AssignmentsPage,
  }))
);
const LazyAutomationRulesPage = lazyPage(() =>
  import("./pages/AutomationRulesPage").then((module) => ({
    default: module.AutomationRulesPage,
  }))
);
const LazyAlertsPage = lazyPage(() =>
  import("./pages/AlertsPage").then((module) => ({ default: module.AlertsPage }))
);
const LazyProviderEventsPage = lazyPage(() =>
  import("./pages/ProviderEventsPage").then((module) => ({
    default: module.ProviderEventsPage,
  }))
);
const LazyReportsPage = lazyPage(() =>
  import("./pages/ReportsPage").then((module) => ({ default: module.ReportsPage }))
);
const LazyImportExportPage = lazyPage(() =>
  import("./pages/ImportExportPage").then((module) => ({
    default: module.ImportExportPage,
  }))
);
const LazyRiskCenterPage = lazyPage(() =>
  import("./pages/RiskCenterPage").then((module) => ({
    default: module.RiskCenterPage,
  }))
);
const LazyOperationsCenterPage = lazyPage(() =>
  import("./pages/OperationsCenterPage").then((module) => ({
    default: module.OperationsCenterPage,
  }))
);
const LazyCustomersPage = lazyPage(() =>
  import("./pages/CustomersPage").then((module) => ({ default: module.CustomersPage }))
);
const LazySitesPage = lazyPage(() =>
  import("./pages/SitesPage").then((module) => ({ default: module.SitesPage }))
);
const LazyEntryLinksPage = lazyPage(() =>
  import("./pages/EntryLinksPage").then((module) => ({ default: module.EntryLinksPage }))
);
const LazyDebugPanelPage = lazyPage(() =>
  import("./pages/DebugPanelPage").then((module) => ({ default: module.DebugPanelPage }))
);
const LazyWhatsAppAPITestPage = lazyPage(() =>
  import("./pages/WhatsAppAPITestPage").then((module) => ({ default: module.WhatsAppAPITestPage }))
);
const LazyLoginPage = lazy(() =>
  import("./pages/LoginPage").then((module) => ({ default: module.LoginPage }))
);
const LazyH5App = lazy(() =>
  import("./pages/H5App").then((module) => ({ default: module.H5App }))
);

// Admin enhancement pages
const LazyAgentsPage = lazy(() =>
  import("./pages/AgentsPage").then((module) => ({ default: module.AgentsPage }))
);

// Profile page
const LazyProfilePage = lazy(() =>
  import("./pages/ProfilePage").then((module) => ({ default: module.ProfilePage }))
);

// IV-FE: New pages
const LazyBackupsPage = lazy(() =>
  import("./pages/BackupsPage").then((module) => ({ default: module.BackupsPage }))
);
const LazyKnowledgeBasePage = lazy(() =>
  import("./pages/KnowledgeBasePage").then((module) => ({ default: module.KnowledgeBasePage }))
);
const LazyApiStatsPage = lazy(() =>
  import("./pages/ApiStatsPage").then((module) => ({ default: module.ApiStatsPage }))
);
const LazyRateLimitsPage = lazy(() =>
  import("./pages/RateLimitsPage").then((module) => ({ default: module.RateLimitsPage }))
);
const LazyAIChatConfigPage = lazy(() =>
  import("./pages/AIChatConfigPage").then((module) => ({ default: module.AIChatConfigPage }))
);

// Finance & Billing pages
const LazyFinanceSettingsPage = lazy(() =>
  import("./pages/FinanceSettingsPage").then((module) => ({ default: module.FinanceSettingsPage }))
);
const LazyFinancePage = lazy(() =>
  import("./pages/FinancePage").then((module) => ({ default: module.FinancePage }))
);

// Agent pages
const LazyAgentUsagePage = lazy(() =>
  import("./pages/agent/AgentUsagePage").then((module) => ({ default: module.AgentUsagePage }))
);
const LazyAgentFinanceSettingsPage = lazy(() =>
  import("./pages/agent/AgentFinanceSettingsPage").then((module) => ({ default: module.AgentFinanceSettingsPage }))
);
const LazyAgentFinancePage = lazy(() =>
  import("./pages/agent/AgentFinancePage").then((module) => ({ default: module.AgentFinancePage }))
);

const GROUP_LABELS: Record<ConsoleRouteGroup, string> = {
  workspace: "工作台",
  content: "内容中心",
  people: "人员管理",
  analytics: "数据报表",
  finance: "财务管理",
  settings: "系统设置",
  devops: "运维监控",
};

function getBrowserLocationKey(): string {
  if (typeof window === "undefined") {
    return "/";
  }
  return `${window.location.pathname}${window.location.search}`;
}

function getPathnameFromLocationKey(locationKey: string): string {
  if (!locationKey.startsWith("/")) {
    return "/";
  }
  const queryIndex = locationKey.indexOf("?");
  return queryIndex >= 0 ? locationKey.slice(0, queryIndex) : locationKey;
}

function getSearchFromLocationKey(locationKey: string): string {
  const queryIndex = locationKey.indexOf("?");
  return queryIndex >= 0 ? locationKey.slice(queryIndex) : "";
}

function normalizePeopleWorkbenchTab(rawTab: string | null): string {
  if (
    rawTab === "permissions" ||
    rawTab === "roles" ||
    rawTab === "members" ||
    rawTab === "edit" ||
    rawTab === "billing"
  ) {
    return rawTab;
  }
  if (rawTab === "permission-grants") {
    return "permissions";
  }
  return "overview";
}

function buildPeopleWorkbenchLocation(state: {
  agencyId?: string | null;
  tab?: string | null;
  role?: string | null;
  member?: string | null;
}): string {
  const params = new URLSearchParams();
  if (state.agencyId) {
    params.set("agencyId", state.agencyId);
  }
  const tab = normalizePeopleWorkbenchTab(state.tab ?? null);
  if (tab !== "overview" || state.agencyId) {
    params.set("tab", tab);
  }
  if (tab === "roles" && state.role) {
    params.set("role", state.role);
  }
  if (tab === "members" && state.member) {
    params.set("member", state.member);
  }
  const query = params.toString();
  return query ? `/system/agents?${query}` : "/system/agents";
}

function normalizeLegacyPeopleLocation(locationKey: string): string | null {
  const pathname = getPathnameFromLocationKey(locationKey);
  const search = getSearchFromLocationKey(locationKey);
  const params = new URLSearchParams(search.startsWith("?") ? search.slice(1) : search);

  if (pathname === "/system/roles") {
    return buildPeopleWorkbenchLocation({
      agencyId: params.get("agencyId"),
      tab: "roles",
      role: params.get("role"),
      member: params.get("member"),
    });
  }

  const detailMatch = pathname.match(/^\/system\/agents\/([^/]+)$/);
  if (detailMatch) {
    return buildPeopleWorkbenchLocation({
      agencyId: decodeURIComponent(detailMatch[1]),
      tab: params.get("tab"),
      role: params.get("role"),
      member: params.get("member"),
    });
  }

  if (pathname === "/system/agents" && params.get("tab") === "permission-grants") {
    return buildPeopleWorkbenchLocation({
      agencyId: params.get("agencyId"),
      tab: "permissions",
      role: params.get("role"),
      member: params.get("member"),
    });
  }

  return null;
}

function getInitialLocationKey(): string {
  const locationKey = getBrowserLocationKey();
  const normalized = normalizeLegacyPeopleLocation(locationKey);
  if (normalized && normalized !== locationKey) {
    window.history.replaceState({}, "", normalized);
    return normalized;
  }
  return locationKey;
}

function navigateToLocation(locationKey: string): void {
  window.history.pushState({}, "", locationKey);
}

function getRouteIcon(icon: ConsoleRouteIconKey): JSX.Element {
  if (icon === "dashboard") return <DashboardOutlined />;
  if (icon === "workspace") return <MessageOutlined />;
  if (icon === "accounts") return <ApartmentOutlined />;
  if (icon === "templates") return <FileTextOutlined />;
  if (icon === "analytics") return <BarChartOutlined />;
  if (icon === "monitoring") return <MonitorOutlined />;
  if (icon === "webhooks") return <DatabaseOutlined />;
  if (icon === "integrations") return <ApartmentOutlined />;
  if (icon === "provider_events") return <DatabaseOutlined />;
  if (icon === "system_logs") return <AuditOutlined />;
  if (icon === "evidence_center") return <AuditOutlined />;
  if (icon === "media") return <PictureOutlined />;
  if (icon === "tags") return <TagsOutlined />;
  if (icon === "audience_rules") return <NodeIndexOutlined />;
  if (icon === "ecommerce") return <ShopOutlined />;
  if (icon === "tasks") return <AppstoreOutlined />;
  if (icon === "reviews") return <WarningOutlined />;
  if (icon === "tickets") return <AuditOutlined />;
  if (icon === "users") return <TeamOutlined />;
  if (icon === "identity_sync") return <SafetyCertificateOutlined />;
  if (icon === "member_access") return <TeamOutlined />;
  if (icon === "notifications") return <BellOutlined />;
  if (icon === "security") return <SafetyCertificateOutlined />;
  if (icon === "security_settings") return <SafetyCertificateOutlined />;
  if (icon === "members") return <TeamOutlined />;
  if (icon === "assignments") return <PartitionOutlined />;
  if (icon === "automation") return <ThunderboltOutlined />;
  if (icon === "alerts") return <BellOutlined />;
  if (icon === "reports") return <BarChartOutlined />;
  if (icon === "imports") return <DatabaseOutlined />;
  if (icon === "risk") return <WarningFilled />;
  if (icon === "operations") return <AppstoreOutlined />;
  if (icon === "customers") return <UserOutlined />;
  if (icon === "sites") return <UserOutlined />;
  if (icon === "agents") return <TeamOutlined />;
  if (icon === "organization") return <ApartmentOutlined />;
  if (icon === "settings") return <SettingOutlined />;
  if (icon === "my_queue") return <PartitionOutlined />;
  if (icon === "team") return <TeamOutlined />;
  if (icon === "security_center") return <SafetyCertificateOutlined />;
  if (icon === "ops_board") return <AppstoreOutlined />;
  if (icon === "debug") return <BugOutlined />;
  if (icon === "api_test") return <SendOutlined />;
  if (icon === "ai_chat") return <ThunderboltOutlined />;
  return <AuditOutlined />;
}

function renderPage(activePage: AppPageId): JSX.Element {
  if (activePage === "dashboard") return <LazyDashboardPage />;
  if (activePage === "conversations") return <LazyChatPage />;
  if (activePage === "meta") return <LazyMetaAccountsPage />;
  if (activePage === "templates") return <LazyTemplatePage />;
  if (activePage === "settings") return <LazySettingsPage />;
  if (activePage === "monitoring") return <LazyMonitoringPage />;
  if (activePage === "api_webhooks") return <LazyApiWebhooksPage />;
  if (activePage === "whatsapp_stats") return <LazyWhatsAppStatsPage />;
  if (activePage === "audit") return <LazyAuditPage />;
  if (activePage === "system_logs") return <LazySystemLogsPage />;
  if (activePage === "evidence_center") return <LazyEvidenceCenterPage />;
  if (activePage === "organization") return <LazyOrganizationSettingsPage />;
  if (activePage === "media") return <LazyMediaLibraryPage />;
  if (activePage === "ecommerce") return <LazyEcommercePage />;
  if (activePage === "task_rules") return <LazyTaskRulesPage />;
  if (activePage === "invite_management") return <LazyInviteManagementPage />;
  if (activePage === "invite_relations") return <LazyInviteRelationsPage />;
  if (activePage === "invite_rewards") return <LazyInviteRewardsPage />;
  if (activePage === "audience_rules") return <LazyAudienceRulesPage />;
  if (activePage === "tags") return <LazyTagsPage />;
  if (activePage === "tasks") return <LazyTasksPage />;
  if (activePage === "reviews") return <LazyReviewsPage />;
  if (activePage === "tickets") return <LazyTicketsPage />;
  if (activePage === "users") return <LazyUsersPage />;
  if (activePage === "identity_sync") return <LazyIdentitySyncPage />;
  if (activePage === "member_access") return <LazyMemberAccessPage />;
  if (activePage === "notifications") return <LazyNotificationsPage />;
  if (activePage === "security_settings") return <LazySecuritySettingsPage />;
  if (activePage === "access_control") return <LazyAccessControlPage />;
  if (activePage === "members") return <LazyMembersPage />;
  if (activePage === "assignments") return <LazyAssignmentsPage />;
  if (activePage === "automation") return <LazyAutomationRulesPage />;
  if (activePage === "alerts") return <LazyAlertsPage />;
  if (activePage === "provider_events") return <LazyProviderEventsPage />;
  if (activePage === "reports") return <LazyReportsPage />;
  if (activePage === "imports") return <LazyImportExportPage />;
  if (activePage === "risk") return <LazyRiskCenterPage />;
  if (activePage === "operations") return <LazyOperationsCenterPage />;
  if (activePage === "customers") return <LazyCustomersPage />;
  if (activePage === "sites") return <LazySitesPage />;
  if (activePage === "entry_links") return <LazyEntryLinksPage />;
  if (activePage === "agents") return <LazyAgentsPage />;
  if (activePage === "profile") return <LazyProfilePage />;
  if (activePage === "debug_panel") return <LazyDebugPanelPage />;
  if (activePage === "whatsapp_api_test") return <LazyWhatsAppAPITestPage />;
  if (activePage === "backups") return <LazyBackupsPage />;
  if (activePage === "knowledge") return <LazyKnowledgeBasePage />;
  if (activePage === "api_stats") return <LazyApiStatsPage />;
  if (activePage === "rate_limits") return <LazyRateLimitsPage />;
  if (activePage === "ai_chat_config") return <LazyAIChatConfigPage />;
  if (activePage === "finance_settings") return <LazyFinanceSettingsPage />;
  if (activePage === "finance") return <LazyFinancePage />;
  if (activePage === "agent_usage") return <LazyAgentUsagePage />;
  if (activePage === "agent_finance_settings") return <LazyAgentFinanceSettingsPage />;
  if (activePage === "agent_finance") return <LazyAgentFinancePage />;
  return <LazyDashboardPage />;
}

function buildMenuItems(
  group: ConsoleRouteGroup,
  routes: ConsoleRouteDefinition[]
) {
  return {
    key: `group:${group}`,
    label: GROUP_LABELS[group],
    children: routes.map((route) => ({
      key: route.path,
      icon: getRouteIcon(route.icon),
      label: getCanonicalRouteNavLabel(route),
    })),
  };
}

function getCanonicalRouteNavLabel(route: ConsoleRouteDefinition): string {
  if (route.id === "agents") {
    return "\u4ee3\u7406\u5546\u7ba1\u7406";
  }
  return route.navLabel;
}

function navigateTo(path: string): void {
  window.history.pushState({}, "", path);
  window.dispatchEvent(new PopStateEvent("popstate"));
}

export default function App() {
  const activePage = useAppStore((state) => state.activePage);
  const setActivePage = useAppStore((state) => state.setActivePage);
  const workspacePagePrefill = useAppStore((state) => state.workspacePagePrefill);
  const auditPagePrefill = useAppStore((state) => state.auditPagePrefill);
  const whatsappStatsPagePrefill = useAppStore((state) => state.whatsappStatsPagePrefill);
  const providerEventsPagePrefill = useAppStore((state) => state.providerEventsPagePrefill);
  const apiWebhooksPagePrefill = useAppStore((state) => state.apiWebhooksPagePrefill);
  const systemLogsPagePrefill = useAppStore((state) => state.systemLogsPagePrefill);
  const alertsPagePrefill = useAppStore((state) => state.alertsPagePrefill);
  const operationsPagePrefill = useAppStore((state) => state.operationsPagePrefill);
  const customersPagePrefill = useAppStore((state) => state.customersPagePrefill);
  const notificationsPagePrefill = useAppStore((state) => state.notificationsPagePrefill);
  const usersPagePrefill = useAppStore((state) => state.usersPagePrefill);
  const memberAccessPagePrefill = useAppStore((state) => state.memberAccessPagePrefill);
  const membersPagePrefill = useAppStore((state) => state.membersPagePrefill);
  const sitesPagePrefill = useAppStore((state) => state.sitesPagePrefill);
  const accessControlPagePrefill = useAppStore((state) => state.accessControlPagePrefill);
  const securitySettingsPagePrefill = useAppStore((state) => state.securitySettingsPagePrefill);
  const identitySyncPagePrefill = useAppStore((state) => state.identitySyncPagePrefill);
  const organizationPagePrefill = useAppStore((state) => state.organizationPagePrefill);
  const settingsPagePrefill = useAppStore((state) => state.settingsPagePrefill);
  const templatePagePrefill = useAppStore((state) => state.templatePagePrefill);
  const metaAccountsPagePrefill = useAppStore((state) => state.metaAccountsPagePrefill);
  const evidencePagePrefill = useAppStore((state) => state.evidencePagePrefill);
  const setWorkspacePagePrefill = useAppStore((state) => state.setWorkspacePagePrefill);
  const setAuditPagePrefill = useAppStore((state) => state.setAuditPagePrefill);
  const setWhatsAppStatsPagePrefill = useAppStore((state) => state.setWhatsAppStatsPagePrefill);
  const setProviderEventsPagePrefill = useAppStore((state) => state.setProviderEventsPagePrefill);
  const setApiWebhooksPagePrefill = useAppStore((state) => state.setApiWebhooksPagePrefill);
  const setSystemLogsPagePrefill = useAppStore((state) => state.setSystemLogsPagePrefill);
  const setAlertsPagePrefill = useAppStore((state) => state.setAlertsPagePrefill);
  const setOperationsPagePrefill = useAppStore((state) => state.setOperationsPagePrefill);
  const setCustomersPagePrefill = useAppStore((state) => state.setCustomersPagePrefill);
  const setNotificationsPagePrefill = useAppStore((state) => state.setNotificationsPagePrefill);
  const setUsersPagePrefill = useAppStore((state) => state.setUsersPagePrefill);
  const setMemberAccessPagePrefill = useAppStore((state) => state.setMemberAccessPagePrefill);
  const setMembersPagePrefill = useAppStore((state) => state.setMembersPagePrefill);
  const setSitesPagePrefill = useAppStore((state) => state.setSitesPagePrefill);
  const setAccessControlPagePrefill = useAppStore((state) => state.setAccessControlPagePrefill);
  const setSecuritySettingsPagePrefill = useAppStore((state) => state.setSecuritySettingsPagePrefill);
  const setIdentitySyncPagePrefill = useAppStore((state) => state.setIdentitySyncPagePrefill);
  const setOrganizationPagePrefill = useAppStore((state) => state.setOrganizationPagePrefill);
  const setSettingsPagePrefill = useAppStore((state) => state.setSettingsPagePrefill);
  const setTemplatePagePrefill = useAppStore((state) => state.setTemplatePagePrefill);
  const setMetaAccountsPagePrefill = useAppStore((state) => state.setMetaAccountsPagePrefill);
  const setEvidencePagePrefill = useAppStore((state) => state.setEvidencePagePrefill);
  const clearEvidencePagePrefill = useAppStore((state) => state.clearEvidencePagePrefill);
  const [locationKey, setLocationKey] = useState<string>(getInitialLocationKey);
  const [hydrated, setHydrated] = useState(false);
  const [authChecked, setAuthChecked] = useState(false);
  const [currentUser, setCurrentUser] = useState<AdminUser | null>(null);
  const [changePasswordModalOpen, setChangePasswordModalOpen] = useState(false);
  const [oldPassword, setOldPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [changingPassword, setChangingPassword] = useState(false);
  const [notificationCount, setNotificationCount] = useState(0);
  const [recentNotifications, setRecentNotifications] = useState<NotificationItem[]>([]);
  const lastProgrammaticLocationRef = useRef<string | null>(null);

  useEffect(() => {
    const handlePopState = (): void => setLocationKey(getBrowserLocationKey());
    window.addEventListener("popstate", handlePopState);
    return () => window.removeEventListener("popstate", handlePopState);
  }, []);

  // 认证初始化：检查已登录状态
  useEffect(() => {
    if (adminAuth.isAuthenticated()) {
      adminAuth.getMe()
        .then((user) => {
          setCurrentUser(user);
          const roleMap: Record<string, "super_admin" | "operator" | "support_agent"> = {
            admin: "super_admin",
            operator: "operator",
            agent: "support_agent",
          };
          useAppStore.getState().setConsoleAgentId(user.id);
          useAppStore.getState().setConsoleAgentName(user.display_name);
          useAppStore.getState().setActorRole(roleMap[user.role] ?? "support_agent");
        })
        .catch(() => {
          adminAuth.clearAuth();
        })
        .finally(() => setAuthChecked(true));
    } else {
      setAuthChecked(true);
    }
  }, []);

  // 通知轮询（每30秒检查未读数量 + 最近5条通知）
  useEffect(() => {
    async function pollNotifications(): Promise<void> {
      if (!adminAuth.isAuthenticated()) return;
      try {
        const [count, items] = await Promise.all([
          getUnreadCount(),
          getRecentNotifications(5),
        ]);
        setNotificationCount(count);
        setRecentNotifications(items);
      } catch { /* 静默失败 */ }
    }
    void pollNotifications();
    const interval = setInterval(() => void pollNotifications(), 30_000);
    return () => clearInterval(interval);
  }, []);

  // 未认证自动跳转登录页（使用 location.replace 避免 popstate 循环）
  // 排除 H5 会员端路径，不干扰 H5 自有认证
  useEffect(() => {
    if (!authChecked) return;
    const path = window.location.pathname.toLowerCase();

    // 排除 H5 会员端路径和登录页
    if (path.startsWith("/h5") || path.startsWith("/login")) return;

    // 未认证 → 跳转到统一登录页
    if (!adminAuth.isAuthenticated()) {
      const redirect = window.location.pathname === "/" ? "" : `?redirect=${encodeURIComponent(window.location.pathname)}`;
      window.location.replace(`/login${redirect}`);
    }
  }, [authChecked]);

  // 退出处理：先清本地状态，立即跳转登录页，后台通知后端登出
  const handleLogout = useCallback(() => {
    adminAuth.clearAuth();
    setCurrentUser(null);
    useAppStore.getState().setConsoleAgentId("agent-cn-console");
    useAppStore.getState().setConsoleAgentName("中文客服台");
    useAppStore.getState().setActorRole("super_admin");
    // 后台通知后端登出（不等待，忽略结果）
    adminAuth.logout().catch(() => {});
    // 全量跳转登录页，清理 SPA 状态
    window.location.replace("/login");
  }, []);

  // 修改密码
  const handleChangePassword = useCallback(async () => {
    setChangingPassword(true);
    try {
      await adminAuth.changePassword({ old_password: oldPassword, new_password: newPassword });
      message.success("密码修改成功");
      setChangePasswordModalOpen(false);
      setOldPassword("");
      setNewPassword("");
    } catch (err) {
      message.error(err instanceof Error ? err.message : "修改密码失败");
    } finally {
      setChangingPassword(false);
    }
  }, [oldPassword, newPassword]);

  // 退出登录确认
  const confirmLogout = useCallback(() => {
    Modal.confirm({
      title: "确认退出登录？",
      content: "退出后需要重新登录",
      okText: "退出",
      cancelText: "取消",
      onOk: handleLogout,
    });
  }, [handleLogout]);

  useEffect(() => {
    const pathname = getPathnameFromLocationKey(locationKey);
    const search = getSearchFromLocationKey(locationKey);
    const isProgrammaticLocation = lastProgrammaticLocationRef.current === locationKey;
    if (isProgrammaticLocation) {
      lastProgrammaticLocationRef.current = null;
    }

    const normalizedPeopleLocation = normalizeLegacyPeopleLocation(locationKey);
    if (normalizedPeopleLocation && normalizedPeopleLocation !== locationKey) {
      window.history.replaceState({}, "", normalizedPeopleLocation);
      setLocationKey(normalizedPeopleLocation);
      return;
    }

    if (pathname.toLowerCase().startsWith("/h5")) {
      setHydrated(true);
      return;
    }

    if (pathname === "/login") {
      setHydrated(true);
      return;
    }

    const route = resolveConsoleRoute(pathname);
    if (activePage !== route.id) {
      setActivePage(route.id);
    }

    if (!isProgrammaticLocation) {
      const parsedPrefill = parseAdminLocationPrefill(route.id, search);
      if (route.id === "conversations") {
        setWorkspacePagePrefill(
          parsedPrefill as Parameters<typeof setWorkspacePagePrefill>[0]
        );
      } else if (route.id === "audit") {
        setAuditPagePrefill(parsedPrefill as Parameters<typeof setAuditPagePrefill>[0]);
      } else if (route.id === "whatsapp_stats") {
        setWhatsAppStatsPagePrefill(
          parsedPrefill as Parameters<typeof setWhatsAppStatsPagePrefill>[0]
        );
      } else if (route.id === "provider_events") {
        setProviderEventsPagePrefill(
          parsedPrefill as Parameters<typeof setProviderEventsPagePrefill>[0]
        );
      } else if (route.id === "api_webhooks") {
        setApiWebhooksPagePrefill(
          parsedPrefill as Parameters<typeof setApiWebhooksPagePrefill>[0]
        );
      } else if (route.id === "system_logs") {
        setSystemLogsPagePrefill(
          parsedPrefill as Parameters<typeof setSystemLogsPagePrefill>[0]
        );
      } else if (route.id === "alerts") {
        setAlertsPagePrefill(parsedPrefill as Parameters<typeof setAlertsPagePrefill>[0]);
      } else if (route.id === "operations") {
        setOperationsPagePrefill(
          parsedPrefill as Parameters<typeof setOperationsPagePrefill>[0]
        );
      } else if (route.id === "customers") {
        setCustomersPagePrefill(parsedPrefill as Parameters<typeof setCustomersPagePrefill>[0]);
      } else if (route.id === "notifications") {
        setNotificationsPagePrefill(
          parsedPrefill as Parameters<typeof setNotificationsPagePrefill>[0]
        );
      } else if (route.id === "users") {
        setUsersPagePrefill(parsedPrefill as Parameters<typeof setUsersPagePrefill>[0]);
      } else if (route.id === "member_access") {
        setMemberAccessPagePrefill(
          parsedPrefill as Parameters<typeof setMemberAccessPagePrefill>[0]
        );
      } else if (route.id === "members") {
        setMembersPagePrefill(parsedPrefill as Parameters<typeof setMembersPagePrefill>[0]);
      } else if (route.id === "sites") {
        setSitesPagePrefill(parsedPrefill as Parameters<typeof setSitesPagePrefill>[0]);
      } else if (route.id === "entry_links") {
        // EntryLinksPage 暂不消费 prefill，但保持 hook 链一致。
      } else if (route.id === "access_control") {
        setAccessControlPagePrefill(
          parsedPrefill as Parameters<typeof setAccessControlPagePrefill>[0]
        );
      } else if (route.id === "security_settings") {
        setSecuritySettingsPagePrefill(
          parsedPrefill as Parameters<typeof setSecuritySettingsPagePrefill>[0]
        );
      } else if (route.id === "identity_sync") {
        setIdentitySyncPagePrefill(
          parsedPrefill as Parameters<typeof setIdentitySyncPagePrefill>[0]
        );
      } else if (route.id === "organization") {
        setOrganizationPagePrefill(
          parsedPrefill as Parameters<typeof setOrganizationPagePrefill>[0]
        );
      } else if (route.id === "settings") {
        setSettingsPagePrefill(parsedPrefill as Parameters<typeof setSettingsPagePrefill>[0]);
      } else if (route.id === "templates") {
        setTemplatePagePrefill(parsedPrefill as Parameters<typeof setTemplatePagePrefill>[0]);
      } else if (route.id === "meta") {
        setMetaAccountsPagePrefill(
          parsedPrefill as Parameters<typeof setMetaAccountsPagePrefill>[0]
        );
      } else if (route.id === "evidence_center") {
        setEvidencePagePrefill(parsedPrefill as Parameters<typeof setEvidencePagePrefill>[0]);
      }
    }

    setHydrated(true);
  }, [
    locationKey,
    setActivePage,
    setAuditPagePrefill,
    setProviderEventsPagePrefill,
    setApiWebhooksPagePrefill,
    setSystemLogsPagePrefill,
    setAlertsPagePrefill,
    setOperationsPagePrefill,
    setCustomersPagePrefill,
    setNotificationsPagePrefill,
    setUsersPagePrefill,
    setMemberAccessPagePrefill,
    setMembersPagePrefill,
    setSitesPagePrefill,
    setAccessControlPagePrefill,
    setSecuritySettingsPagePrefill,
    setIdentitySyncPagePrefill,
    setOrganizationPagePrefill,
    setSettingsPagePrefill,
    setTemplatePagePrefill,
    setMetaAccountsPagePrefill,
    setEvidencePagePrefill,
    setWhatsAppStatsPagePrefill,
    setWorkspacePagePrefill,
  ]);

  useEffect(() => {
    const pathname = getPathnameFromLocationKey(locationKey);
    if (!hydrated || pathname.toLowerCase().startsWith("/h5") || pathname === "/login") {
      return;
    }
    const resolvedRoute = resolveConsoleRoute(pathname);
    if (resolvedRoute.id !== activePage) {
      return;
    }

    const targetPath = getConsolePath(activePage);
    const nextLocationKey =
      activePage === "agents"
        ? locationKey
        : 
      activePage === "conversations" && workspacePagePrefill
        ? buildAdminLocationKey(targetPath, activePage, {
            conversations: workspacePagePrefill,
          })
        : activePage === "audit" && auditPagePrefill
          ? buildAdminLocationKey(targetPath, activePage, {
              audit: auditPagePrefill,
            })
          : activePage === "whatsapp_stats" && whatsappStatsPagePrefill
            ? buildAdminLocationKey(targetPath, activePage, {
                whatsapp_stats: whatsappStatsPagePrefill,
              })
            : activePage === "provider_events" && providerEventsPagePrefill
            ? buildAdminLocationKey(targetPath, activePage, {
                provider_events: providerEventsPagePrefill,
              })
            : activePage === "api_webhooks" && apiWebhooksPagePrefill
              ? buildAdminLocationKey(targetPath, activePage, {
                  api_webhooks: apiWebhooksPagePrefill,
                })
              : activePage === "system_logs" && systemLogsPagePrefill
                ? buildAdminLocationKey(targetPath, activePage, {
                    system_logs: systemLogsPagePrefill,
                  })
              : activePage === "alerts" && alertsPagePrefill
                ? buildAdminLocationKey(targetPath, activePage, {
                    alerts: alertsPagePrefill,
                  })
                : activePage === "operations" && operationsPagePrefill
                  ? buildAdminLocationKey(targetPath, activePage, {
                      operations: operationsPagePrefill,
                    })
                  : activePage === "customers" && customersPagePrefill
                    ? buildAdminLocationKey(targetPath, activePage, {
                        customers: customersPagePrefill,
                      })
                  : activePage === "notifications" && notificationsPagePrefill
                    ? buildAdminLocationKey(targetPath, activePage, {
                        notifications: notificationsPagePrefill,
                      })
                  : activePage === "users" && usersPagePrefill
                      ? buildAdminLocationKey(targetPath, activePage, {
                          users: usersPagePrefill,
                        })
                    : activePage === "member_access" && memberAccessPagePrefill
                      ? buildAdminLocationKey(targetPath, activePage, {
                          member_access: memberAccessPagePrefill,
                        })
                    : activePage === "members" && membersPagePrefill
                      ? buildAdminLocationKey(targetPath, activePage, {
                          members: membersPagePrefill,
                        })
                    : activePage === "sites" && sitesPagePrefill
                      ? buildAdminLocationKey(targetPath, activePage, {
                          sites: sitesPagePrefill,
                        })
                    : activePage === "access_control" && accessControlPagePrefill
                      ? buildAdminLocationKey(targetPath, activePage, {
                          access_control: accessControlPagePrefill,
                        })
                    : activePage === "security_settings" && securitySettingsPagePrefill
                      ? buildAdminLocationKey(targetPath, activePage, {
                          security_settings: securitySettingsPagePrefill,
                        })
                    : activePage === "identity_sync" && identitySyncPagePrefill
                      ? buildAdminLocationKey(targetPath, activePage, {
                          identity_sync: identitySyncPagePrefill,
                        })
                    : activePage === "organization" && organizationPagePrefill
                      ? buildAdminLocationKey(targetPath, activePage, {
                          organization: organizationPagePrefill,
                        })
                    : activePage === "settings" && settingsPagePrefill
                      ? buildAdminLocationKey(targetPath, activePage, {
                          settings: settingsPagePrefill,
                      })
                    : activePage === "templates" && templatePagePrefill
                      ? buildAdminLocationKey(targetPath, activePage, {
                          templates: templatePagePrefill,
                        })
                    : activePage === "meta" && metaAccountsPagePrefill
                      ? buildAdminLocationKey(targetPath, activePage, {
                          meta: metaAccountsPagePrefill,
                        })
                    : activePage === "evidence_center" && evidencePagePrefill
                      ? buildAdminLocationKey(targetPath, activePage, {
                          evidence_center: evidencePagePrefill,
                        })
                      : targetPath !== pathname
                        ? targetPath
                        : locationKey;

    if (nextLocationKey !== locationKey) {
      lastProgrammaticLocationRef.current = nextLocationKey;
      navigateToLocation(nextLocationKey);
      setLocationKey(nextLocationKey);
    }
  }, [
    activePage,
    auditPagePrefill,
    hydrated,
    locationKey,
    systemLogsPagePrefill,
    alertsPagePrefill,
    operationsPagePrefill,
    customersPagePrefill,
    notificationsPagePrefill,
    usersPagePrefill,
    memberAccessPagePrefill,
    membersPagePrefill,
    sitesPagePrefill,
    accessControlPagePrefill,
    securitySettingsPagePrefill,
    identitySyncPagePrefill,
    organizationPagePrefill,
    settingsPagePrefill,
    templatePagePrefill,
    metaAccountsPagePrefill,
    evidencePagePrefill,
    providerEventsPagePrefill,
    apiWebhooksPagePrefill,
    whatsappStatsPagePrefill,
    workspacePagePrefill,
  ]);

  function handleNavigate(pageId: AppPageId): void {
    const pathname = getPathnameFromLocationKey(locationKey);
    const targetPath = getConsolePath(pageId);
    if (pageId === "evidence_center") {
      clearEvidencePagePrefill();
    }
    const shouldResetEvidenceLocation =
      pageId === "evidence_center" && locationKey !== targetPath;
    if (shouldResetEvidenceLocation || targetPath !== pathname) {
      lastProgrammaticLocationRef.current = targetPath;
      navigateToLocation(targetPath);
      setLocationKey(targetPath);
    }
    setActivePage(pageId);
  }

  async function handleNotificationMarkRead(id: string): Promise<void> {
    try {
      await markNotificationsRead([id]);
      setRecentNotifications((prev) =>
        prev.map((n) => (n.id === id ? { ...n, is_read: true, read_at: new Date().toISOString() } : n))
      );
      setNotificationCount((prev) => Math.max(0, prev - 1));
    } catch { /* 静默 */ }
  }

  async function handleNotificationMarkAllRead(): Promise<void> {
    try {
      const count = await markAllNotificationsRead();
      if (count > 0) {
        setRecentNotifications((prev) =>
          prev.map((n) => ({ ...n, is_read: true, read_at: new Date().toISOString() }))
        );
        setNotificationCount(0);
      }
    } catch { /* 静默 */ }
  }

  const pathname = getPathnameFromLocationKey(locationKey);
  const activeRoute = useMemo(
    () => getConsoleRouteById(activePage) ?? resolveConsoleRoute(pathname),
    [activePage, pathname]
  );

  const { canSeePage, loading: permissionsLoading } = usePermissions();

  const menuItems = useMemo(
    () =>
      [
        buildMenuItems("workspace", groupedConsoleRoutes.workspace.filter((r) => canSeePage(r.id))),
        buildMenuItems("content", groupedConsoleRoutes.content.filter((r) => canSeePage(r.id))),
        buildMenuItems("people", groupedConsoleRoutes.people.filter((r) => canSeePage(r.id))),
        buildMenuItems("analytics", groupedConsoleRoutes.analytics.filter((r) => canSeePage(r.id))),
        buildMenuItems("finance", groupedConsoleRoutes.finance.filter((r) => canSeePage(r.id))),
        buildMenuItems("settings", groupedConsoleRoutes.settings.filter((r) => canSeePage(r.id))),
        buildMenuItems("devops", groupedConsoleRoutes.devops.filter((r) => canSeePage(r.id))),
      ].filter((group) => group.children.length > 0) as Array<{
        key: string;
        label: string;
        children: Array<{ key: string; icon: JSX.Element; label: string }>;
      }>,
    [canSeePage]
  );

  const [siderCollapsed, setSiderCollapsed] = useState(false);

  // 计算菜单容器高度（header + footer 固定，搜索框条件渲染）
  const menuContainerHeight = useMemo(() => {
    const headerH = 48;
    const searchH = siderCollapsed ? 0 : 30;
    const footerH = 52;
    return `calc(100vh - ${headerH + searchH + footerH}px)`;
  }, [siderCollapsed]);
  const [menuOpenKeys, setMenuOpenKeys] = useState<string[]>(["group:workspace"]);
  const [menuSearch, setMenuSearch] = useState("");

  // 所有菜单分组 key，用于一键展开/收缩
  const allGroupKeys = useMemo(() => menuItems.map((item) => item.key), [menuItems]);
  const isMenuFullyExpanded = useMemo(
    () => allGroupKeys.length > 0 && allGroupKeys.every((k) => menuOpenKeys.includes(k)),
    [allGroupKeys, menuOpenKeys]
  );

  const toggleAllMenuGroups = useCallback(() => {
    if (isMenuFullyExpanded) {
      setMenuOpenKeys(["group:workspace"]);
    } else {
      setMenuOpenKeys(allGroupKeys);
    }
  }, [isMenuFullyExpanded, allGroupKeys]);
  const filteredMenuItems = useMemo(() => {
    if (!menuSearch.trim()) return menuItems;
    const q = menuSearch.trim().toLowerCase();
    return menuItems
      .map((group) => {
        const matched = group.children.filter(
          (item) =>
            item.label.toLowerCase().includes(q) ||
            item.key.toLowerCase().includes(q)
        );
        if (matched.length === 0) return null;
        return { ...group, children: matched };
      })
      .filter(Boolean) as typeof menuItems;
  }, [menuItems, menuSearch]);
  const selectedMenuKey = activeRoute.path;

  const handleMenuClick = useCallback(
    (info: { key: string }) => {
      const route = resolveConsoleRoute(info.key);
      handleNavigate(route.id);
    },
    [handleNavigate]
  );

  const roleLabel: Record<string, string> = {
    admin: "管理员",
    operator: "运营",
    agent: "客服",
  };
  const roleColor: Record<string, string> = {
    admin: "blue",
    operator: "cyan",
    agent: "green",
  };
  const userRole = currentUser?.role ?? "agent";
  const dropdownItems = useMemo(() => [
    {
      key: "profile",
      icon: <UserOutlined />,
      label: `${currentUser?.display_name ?? "用户"}（${roleLabel[userRole] ?? "客服"}）`,
      disabled: true,
    },
    { type: "divider" as const },
    {
      key: "profile-page",
      icon: <UserOutlined />,
      label: "个人中心",
      onClick: () => handleNavigate("profile" as AppPageId),
    },
    {
      key: "change-password",
      icon: <KeyOutlined />,
      label: "修改密码",
      onClick: () => setChangePasswordModalOpen(true),
    },
    { type: "divider" as const },
    {
      key: "logout",
      icon: <LogoutOutlined />,
      label: "退出登录",
      onClick: confirmLogout,
    },
  ], [currentUser, userRole, confirmLogout, handleNavigate]);

function NotFoundFallback(): JSX.Element {
  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", minHeight: "100vh", background: "#f5f7fa" }}>
      <div style={{ fontSize: 64, marginBottom: 16 }}>🔍</div>
      <Typography.Title level={3}>页面不存在或您没有访问权限</Typography.Title>
      <Typography.Text type="secondary" style={{ marginBottom: 24 }}>请检查 URL 是否正确，或联系管理员</Typography.Text>
      <Button type="primary" onClick={() => window.location.replace("/")}>返回首页</Button>
    </div>
  );
}

  // H5 会员端路由
  if (pathname.toLowerCase().startsWith("/h5")) {
    return (
      <Suspense fallback={<div className="admin-loading"><Spin size="large" /></div>}>
        <LazyH5App
          locationKey={locationKey}
          navigate={(path) => {
            lastProgrammaticLocationRef.current = path;
            navigateToLocation(path);
            setLocationKey(path);
          }}
        />
      </Suspense>
    );
  }

  // 404 页面：未匹配任何路由
  if (pathname !== "/" && pathname !== "/login") {
    const isKnownConsoleRoute = CONSOLE_ROUTES.some(route => {
      if (route.path === pathname) return true;
      if (route.path !== "/" && pathname.startsWith(route.path + "/")) return true;
      return false;
    });
    if (!isKnownConsoleRoute) {
      return (
        <ConfigProvider>
          <Suspense fallback={<div className="admin-loading"><Spin size="large" /></div>}>
            <NotFoundFallback />
          </Suspense>
        </ConfigProvider>
      );
    }
  }

  // 登录页面路由（不经过 Layout）
  if (pathname === "/login") {
    return (
      <Suspense fallback={<div className="admin-loading"><Spin size="large" /></div>}>
        <LazyLoginPage />
      </Suspense>
    );
  }

  // 认证检查未完成时显示 loading
  if (!authChecked) {
    return (
      <div className="admin-loading" style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        minHeight: "100vh",
        background: "#f5f7fa"
      }}>
        <Spin size="large" tip="验证登录状态..." fullscreen />
      </div>
    );
  }

  // 未认证：重定向到登录页
  if (!adminAuth.isAuthenticated()) {
    const redirectPath = encodeURIComponent(pathname);
    return (
      <div className="admin-loading" style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        minHeight: "100vh",
        background: "#f5f7fa"
      }}>
        <Spin size="large" />
      </div>
    );
  }

  if (permissionsLoading) {
    return (
      <div className="admin-loading" style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        minHeight: "100vh",
        background: "#f5f7fa"
      }}>
        <Spin size="large" tip="加载权限中..." fullscreen />
      </div>
    );
  }

  // 页面访问权限检查
  if (!canSeePage(activeRoute.id)) {
    return (
      <Layout style={{ minHeight: "100vh" }}>
        <Layout.Sider
          collapsed={siderCollapsed}
          onCollapse={setSiderCollapsed}
          width={198}
          breakpoint="lg"
          theme="dark"
          className="sider-scrollbar"
          style={{ height: "100vh", overflow: "hidden" }}
        >
          <div
            style={{
              height: 48,
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              padding: "0 8px 0 12px",
            }}
          >
            <Typography.Text strong style={{ color: "#fff", fontSize: 15, cursor: "pointer" }}
              onClick={() => handleNavigate("dashboard")}>
              {siderCollapsed ? "W" : "管理后台"}
            </Typography.Text>
            <Button
              type="text"
              size="small"
              icon={siderCollapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
              onClick={() => setSiderCollapsed(!siderCollapsed)}
              style={{ color: "#fff", fontSize: 14 }}
            />
          </div>
          {!siderCollapsed && (
              <div style={{ padding: "0 12px 6px" }}>
                <Input
                  size="small"
                  placeholder="搜索菜单…"
                  prefix={<span style={{ fontSize: 12, opacity: 0.45 }}>&#x1F50D;</span>}
                  value={menuSearch}
                  onChange={(e) => setMenuSearch(e.target.value)}
                  allowClear
                  style={{ borderRadius: 6 }}
                />
              </div>
            )}
          <div style={{ height: menuContainerHeight, overflow: "auto", minHeight: 0 }} className="hide-scrollbar">
            <Menu
              theme="dark"
              mode="inline"
              selectedKeys={[selectedMenuKey]}
              openKeys={menuOpenKeys}
              onOpenChange={setMenuOpenKeys}
              items={filteredMenuItems}
              onClick={handleMenuClick}
            />
          </div>
          <div style={{ padding: "8px 12px 10px", borderTop: "1px solid rgba(255,255,255,0.08)" }}>
            <Button
              block
              type="text"
              icon={isMenuFullyExpanded ? <MenuFoldOutlined /> : <MenuUnfoldOutlined />}
              onClick={toggleAllMenuGroups}
              style={{
                color: "rgba(255,255,255,0.65)",
                textAlign: "left",
                paddingLeft: 8,
                height: 34,
                fontSize: 13,
              }}
            >
              {isMenuFullyExpanded ? "收缩菜单" : "展开菜单"}
            </Button>
          </div>
        </Layout.Sider>
        <Layout>
          <Layout.Header
            style={{
              padding: "0 24px",
              background: "#fff",
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              borderBottom: "1px solid #f0f0f0",
              height: 56,
              lineHeight: "56px",
            }}
          >
            <Space size={12}>
              <Space size={4}>
                <Typography.Text type="secondary" style={{ fontSize: 13 }}>
                  {activeRoute.group ? GROUP_LABELS[activeRoute.group] : ""}
                </Typography.Text>
                {activeRoute.group && <Typography.Text type="secondary" style={{ fontSize: 13 }}>/</Typography.Text>}
                <Typography.Text strong style={{ fontSize: 14 }}>
                  {getCanonicalRouteNavLabel(activeRoute)}
                </Typography.Text>
              </Space>
            </Space>
            <Space size="middle">
              <span style={{ display: "flex", alignItems: "center", justifyContent: "center", height: 32, lineHeight: 0 }}>
              <Popover
                trigger="click"
                placement="bottomRight"
                content={
                  <div style={{ width: 360, display: "flex", flexDirection: "column", maxHeight: 400 }}>
                    <Row justify="space-between" align="middle" style={{ marginBottom: 8, flexShrink: 0 }}>
                      <Col>
                        <Typography.Text strong>通知</Typography.Text>
                        {notificationCount > 0 && <Badge count={notificationCount} style={{ marginLeft: 8 }} />}
                      </Col>
                      <Col>
                        <Button type="link" size="small" onClick={() => void handleNotificationMarkAllRead()}>
                          全部已读
                        </Button>
                      </Col>
                    </Row>
                    <Divider style={{ margin: "8px 0", flexShrink: 0 }} />
                    <div style={{ flex: 1, minHeight: 0, overflowY: "auto", overflowX: "hidden" }}>
                      {recentNotifications.length === 0 ? (
                        <div style={{ textAlign: "center", padding: 24, color: "#999" }}>
                          暂无通知
                        </div>
                      ) : (
                        <List
                          size="small"
                          dataSource={recentNotifications}
                          renderItem={(n: NotificationItem) => (
                            <List.Item
                              style={{ padding: "8px 0", cursor: "pointer" }}
                              onClick={() => {
                                void handleNotificationMarkRead(n.id);
                                if (n.action_url) handleNavigate("notifications" as AppPageId);
                              }}
                            >
                              <List.Item.Meta
                                avatar={
                                  <span style={{
                                    display: "inline-block",
                                    width: 8,
                                    height: 8,
                                    borderRadius: "50%",
                                    background: getSeverityColor(n.severity),
                                    flexShrink: 0,
                                  }} />
                                }
                                title={
                                  <Typography.Text ellipsis style={{ fontSize: 12, maxWidth: 240 }}>
                                    {n.title}
                                  </Typography.Text>
                                }
                                description={
                                  <Typography.Text type="secondary" style={{ fontSize: 10 }}>
                                    {n.created_at ? new Date(n.created_at).toLocaleString("zh-CN") : ""}
                                  </Typography.Text>
                                }
                              />
                              <Tag color={getCategoryColor(n.category)} style={{ fontSize: 9, lineHeight: "14px", padding: "0 4px", flexShrink: 0 }}>
                                {n.category}
                              </Tag>
                              {!n.is_read && <Badge status="processing" />}
                            </List.Item>
                          )}
                        />
                      )}
                    </div>
                    <Divider style={{ margin: "8px 0", flexShrink: 0 }} />
                    <div style={{ textAlign: "center", flexShrink: 0 }}>
                      <Button type="link" onClick={() => handleNavigate("notifications")}>
                        查看全部通知
                      </Button>
                    </div>
                  </div>
                }
              >
                <Badge count={notificationCount} size="small" offset={[-4, 4]}>
                  <BellOutlined style={{ fontSize: 22, cursor: "pointer", color: "#64748b" }} />
                </Badge>
              </Popover>
              </span>
              <Dropdown menu={{ items: dropdownItems }} placement="bottomRight">
                <Space style={{ cursor: "pointer" }}>
                  <Avatar
                    size="small"
                    icon={<UserOutlined />}
                    style={{ backgroundColor: "#1f2937" }}
                  />
                  <Typography.Text strong>
                    {currentUser?.display_name ?? "用户"}
                  </Typography.Text>
                  <Tag color={roleColor[userRole]} style={{ marginRight: 0 }}>
                    {roleLabel[userRole] ?? "客服"}
                  </Tag>
                </Space>
              </Dropdown>
            </Space>
          </Layout.Header>
          <Layout.Content style={{ padding: 24 }}>
            <div style={{
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              justifyContent: "center",
              padding: "80px 24px",
              textAlign: "center"
            }}>
              <Typography.Title level={4} type="secondary">
                您没有权限访问该页面
              </Typography.Title>
              <Typography.Text type="secondary" style={{ marginBottom: 16 }}>
                请联系管理员获取相应的访问权限              </Typography.Text>
            </div>
          </Layout.Content>
        </Layout>
      </Layout>
    );
  }

  return (
    <ConfigProvider>
    <div style={{ height: "100vh", overflow: "hidden" }}>
      <Layout style={{ height: "100%", overflow: "hidden" }}>
        <Layout.Sider
          collapsed={siderCollapsed}
          onCollapse={setSiderCollapsed}
          width={198}
          breakpoint="lg"
          theme="dark"
          className="sider-scrollbar"
          style={{ height: "100vh", overflow: "hidden" }}
        >
          <div
            style={{
              height: 48,
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              padding: "0 8px 0 12px",
            }}
          >
            <Typography.Text strong style={{ color: "#fff", fontSize: 15, cursor: "pointer" }}
              onClick={() => handleNavigate("dashboard")}>
              {siderCollapsed ? "W" : "管理后台"}
            </Typography.Text>
            <Button
              type="text"
              size="small"
              icon={siderCollapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
              onClick={() => setSiderCollapsed(!siderCollapsed)}
              style={{ color: "#fff", fontSize: 14 }}
            />
          </div>
          {!siderCollapsed && (
              <div style={{ padding: "0 12px 6px" }}>
                <Input
                  size="small"
                  placeholder="搜索菜单…"
                  prefix={<span style={{ fontSize: 12, opacity: 0.45 }}>&#x1F50D;</span>}
                  value={menuSearch}
                  onChange={(e) => setMenuSearch(e.target.value)}
                  allowClear
                  style={{ borderRadius: 6 }}
                />
              </div>
            )}
          <div style={{ height: menuContainerHeight, overflow: "auto", minHeight: 0 }} className="hide-scrollbar">
            <Menu
              theme="dark"
              mode="inline"
              selectedKeys={[selectedMenuKey]}
              openKeys={menuOpenKeys}
              onOpenChange={setMenuOpenKeys}
              items={filteredMenuItems}
              onClick={handleMenuClick}
            />
          </div>
          <div style={{ padding: "8px 12px 10px", borderTop: "1px solid rgba(255,255,255,0.08)" }}>
            <Button
              block
              type="text"
              icon={isMenuFullyExpanded ? <MenuFoldOutlined /> : <MenuUnfoldOutlined />}
              onClick={toggleAllMenuGroups}
              style={{
                color: "rgba(255,255,255,0.65)",
                textAlign: "left",
                paddingLeft: 8,
                height: 34,
                fontSize: 13,
              }}
            >
              {isMenuFullyExpanded ? "收缩菜单" : "展开菜单"}
            </Button>
          </div>
        </Layout.Sider>
        <Layout style={{ overflow: "hidden" }}>
          <Layout.Header
            style={{
              padding: "0 24px",
              background: "#fff",
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              borderBottom: "1px solid #f0f0f0",
              height: 56,
              lineHeight: "56px",
              flexShrink: 0,
            }}
          >
            <Space size={12}>
              <Space size={4}>
                <Typography.Text type="secondary" style={{ fontSize: 13 }}>
                  {activeRoute.group ? GROUP_LABELS[activeRoute.group] : ""}
                </Typography.Text>
                {activeRoute.group && <Typography.Text type="secondary" style={{ fontSize: 13 }}>/</Typography.Text>}
                <Typography.Text strong style={{ fontSize: 14 }}>
                  {getCanonicalRouteNavLabel(activeRoute)}
                </Typography.Text>
              </Space>
            </Space>
            <Space size="middle">
              <span style={{ display: "flex", alignItems: "center", justifyContent: "center", height: 32, lineHeight: 0 }}>
              <Popover
                trigger="click"
                placement="bottomRight"
                content={
                  <div style={{ width: 360, display: "flex", flexDirection: "column", maxHeight: 400 }}>
                    <Row justify="space-between" align="middle" style={{ marginBottom: 8, flexShrink: 0 }}>
                      <Col>
                        <Typography.Text strong>通知</Typography.Text>
                        {notificationCount > 0 && <Badge count={notificationCount} style={{ marginLeft: 8 }} />}
                      </Col>
                      <Col>
                        <Button type="link" size="small" onClick={() => void handleNotificationMarkAllRead()}>
                          全部已读
                        </Button>
                      </Col>
                    </Row>
                    <Divider style={{ margin: "8px 0", flexShrink: 0 }} />
                    <div style={{ flex: 1, minHeight: 0, overflowY: "auto", overflowX: "hidden" }}>
                      {recentNotifications.length === 0 ? (
                        <div style={{ textAlign: "center", padding: 24, color: "#999" }}>
                          暂无通知
                        </div>
                      ) : (
                        <List
                          size="small"
                          dataSource={recentNotifications}
                          renderItem={(n: NotificationItem) => (
                            <List.Item
                              style={{ padding: "8px 0", cursor: "pointer" }}
                              onClick={() => {
                                void handleNotificationMarkRead(n.id);
                                if (n.action_url) handleNavigate("notifications" as AppPageId);
                              }}
                            >
                              <List.Item.Meta
                                avatar={
                                  <span style={{
                                    display: "inline-block",
                                    width: 8,
                                    height: 8,
                                    borderRadius: "50%",
                                    background: getSeverityColor(n.severity),
                                    flexShrink: 0,
                                  }} />
                                }
                                title={
                                  <Typography.Text ellipsis style={{ fontSize: 12, maxWidth: 240 }}>
                                    {n.title}
                                  </Typography.Text>
                                }
                                description={
                                  <Typography.Text type="secondary" style={{ fontSize: 10 }}>
                                    {n.created_at ? new Date(n.created_at).toLocaleString("zh-CN") : ""}
                                  </Typography.Text>
                                }
                              />
                              <Tag color={getCategoryColor(n.category)} style={{ fontSize: 9, lineHeight: "14px", padding: "0 4px", flexShrink: 0 }}>
                                {n.category}
                              </Tag>
                              {!n.is_read && <Badge status="processing" />}
                            </List.Item>
                          )}
                        />
                      )}
                    </div>
                    <Divider style={{ margin: "8px 0", flexShrink: 0 }} />
                    <div style={{ textAlign: "center", flexShrink: 0 }}>
                      <Button type="link" onClick={() => handleNavigate("notifications")}>
                        查看全部通知
                      </Button>
                    </div>
                  </div>
                }
              >
                <Badge count={notificationCount} size="small" offset={[-4, 4]}>
                  <BellOutlined style={{ fontSize: 22, cursor: "pointer", color: "#64748b" }} />
                </Badge>
              </Popover>
              </span>
              <Dropdown menu={{ items: dropdownItems }} placement="bottomRight">
                <Space style={{ cursor: "pointer" }}>
                  <Avatar
                    size="small"
                    icon={<UserOutlined />}
                    style={{ backgroundColor: "#1f2937" }}
                  />
                  <Typography.Text strong>
                    {currentUser?.display_name ?? "用户"}
                  </Typography.Text>
                  <Tag color={roleColor[userRole]} style={{ marginRight: 0 }}>
                    {roleLabel[userRole] ?? "客服"}
                  </Tag>
                </Space>
              </Dropdown>
            </Space>
          </Layout.Header>
          <Layout.Content style={{ display: "flex", flexDirection: "column", flex: 1, overflow: "hidden" }}>
            <AdminRoutePageShell
              onOpenStats={() => handleNavigate("whatsapp_stats")}
              route={activeRoute}
              compact={activeRoute.id === "conversations" || activeRoute.id === "meta"}
            >
              <Suspense
                fallback={
                  <div className="admin-loading">
                    <Spin size="large" />
                  </div>
                }
              >
                {renderPage(activeRoute.id)}
              </Suspense>
            </AdminRoutePageShell>
          </Layout.Content>
        </Layout>
      </Layout>
      <GlobalSearch
        onNavigate={(url) => {
          lastProgrammaticLocationRef.current = url;
          navigateToLocation(url);
          setLocationKey(url);
        }}
      />
      <ChangePasswordModal
        open={changePasswordModalOpen}
        onClose={() => {
          setChangePasswordModalOpen(false);
          setOldPassword("");
          setNewPassword("");
        }}
        oldPassword={oldPassword}
        newPassword={newPassword}
        onOldPasswordChange={setOldPassword}
        onNewPasswordChange={setNewPassword}
        onSubmit={handleChangePassword}
        loading={changingPassword}
      />
    </div>
    </ConfigProvider>
  );
}

/** 修改密码弹窗 */
function ChangePasswordModal(props: {
  open: boolean;
  onClose: () => void;
  oldPassword: string;
  newPassword: string;
  onOldPasswordChange: (v: string) => void;
  onNewPasswordChange: (v: string) => void;
  onSubmit: () => void;
  loading: boolean;
}): JSX.Element {
  return (
    <Modal
      title="修改密码"
      open={props.open}
      onCancel={props.onClose}
      onOk={props.onSubmit}
      confirmLoading={props.loading}
      okText="确认修改"
      cancelText="取消"
    >
      <Space direction="vertical" style={{ width: "100%" }} size="middle">
        <Input.Password
          placeholder="当前密码"
          value={props.oldPassword}
          onChange={(e) => props.onOldPasswordChange(e.target.value)}
        />
        <Input.Password
          placeholder="新密码"
          value={props.newPassword}
          onChange={(e) => props.onNewPasswordChange(e.target.value)}
        />
      </Space>
    </Modal>
  );
}


