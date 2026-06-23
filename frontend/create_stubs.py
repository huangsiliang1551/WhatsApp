"""为所有编码损坏的文件创建最小可编译存根"""
import os

PAGES_DIR = r"e:\codex\WhatsApp\frontend\src\pages"
BACKUP_DIR = r"e:\codex\WhatsApp\frontend\.stubs_backup"

# 所有需要创建存根的文件（这些文件有 TS1490 或其他编译错误）
STUBS = {
    # Phase 3 pages (will be fully rewritten)
    "AssignmentsPage.tsx": "export function AssignmentsPage(): JSX.Element { return <div>Assignments</div>; }",
    "TicketsPage.tsx": "export function TicketsPage(): JSX.Element { return <div>Tickets</div>; }",
    "CustomersPage.tsx": "export function CustomersPage(): JSX.Element { return <div>Customers</div>; }",
    "ReviewsPage.tsx": "export function ReviewsPage(): JSX.Element { return <div>Reviews</div>; }",

    # Phase 4 pages
    "TemplatePage.tsx": "export function TemplatePage(): JSX.Element { return <div>Template</div>; }",
    "MetaAccountsPage.tsx": "export function MetaAccountsPage(): JSX.Element { return <div>MetaAccounts</div>; }",
    "MediaLibraryPage.tsx": "export function MediaLibraryPage(): JSX.Element { return <div>MediaLibrary</div>; }",
    "SettingsPage.tsx": "export function SettingsPage(): JSX.Element { return <div>Settings</div>; }",

    # Phase 5 pages
    "MonitoringPage.tsx": "export function MonitoringPage(): JSX.Element { return <div>Monitoring</div>; }",
    "UsersPage.tsx": "export function UsersPage(): JSX.Element { return <div>Users</div>; }",
    "AlertsPage.tsx": "export function AlertsPage(): JSX.Element { return <div>Alerts</div>; }",
    "AuditPage.tsx": "export function AuditPage(): JSX.Element { return <div>Audit</div>; }",
    "ProviderEventsPage.tsx": "export function ProviderEventsPage(): JSX.Element { return <div>ProviderEvents</div>; }",
    "ReportsPage.tsx": "export function ReportsPage(): JSX.Element { return <div>Reports</div>; }",
    "ImportExportPage.tsx": "export function ImportExportPage(): JSX.Element { return <div>ImportExport</div>; }",
    "OperationsCenterPage.tsx": "export function OperationsCenterPage(): JSX.Element { return <div>OperationsCenter</div>; }",
    "WhatsAppStatsPage.tsx": "export function WhatsAppStatsPage(): JSX.Element { return <div>WhatsAppStats</div>; }",
    "SecuritySettingsPage.tsx": "export function SecuritySettingsPage(): JSX.Element { return <div>SecuritySettings</div>; }",
    "IdentitySyncPage.tsx": "export function IdentitySyncPage(): JSX.Element { return <div>IdentitySync</div>; }",
    "MemberAccessPage.tsx": "export function MemberAccessPage(): JSX.Element { return <div>MemberAccess</div>; }",
    "AccessControlPage.tsx": "export function AccessControlPage(): JSX.Element { return <div>AccessControl</div>; }",
    "OrganizationSettingsPage.tsx": "export function OrganizationSettingsPage(): JSX.Element { return <div>OrganizationSettings</div>; }",
    "RolesPage.tsx": "export function RolesPage(): JSX.Element { return <div>Roles</div>; }",
    "RiskCenterPage.tsx": "export function RiskCenterPage(): JSX.Element { return <div>RiskCenter</div>; }",
    "SitesPage.tsx": "export function SitesPage(): JSX.Element { return <div>Sites</div>; }",

    # Other corrupted pages
    "ApiWebhooksPage.tsx": "export function ApiWebhooksPage(): JSX.Element { return <div>ApiWebhooks</div>; }",
    "EvidenceCenterPage.tsx": "export function EvidenceCenterPage(): JSX.Element { return <div>EvidenceCenter</div>; }",
    "IntegrationsPage.tsx": "export function IntegrationsPage(): JSX.Element { return <div>Integrations</div>; }",
    "MembersPage.tsx": "export function MembersPage(): JSX.Element { return <div>Members</div>; }",
    "NotificationsPage.tsx": "export function NotificationsPage(): JSX.Element { return <div>Notifications</div>; }",
    "TasksPage.tsx": "export function TasksPage(): JSX.Element { return <div>Tasks</div>; }",
    "AutomationRulesPage.tsx": "export function AutomationRulesPage(): JSX.Element { return <div>AutomationRules</div>; }",
    "EcommercePage.tsx": "export function EcommercePage(): JSX.Element { return <div>Ecommerce</div>; }",
}

os.makedirs(BACKUP_DIR, exist_ok=True)

for filename, stub_content in STUBS.items():
    filepath = os.path.join(PAGES_DIR, filename)
    if not os.path.exists(filepath):
        print(f"SKIP (not found): {filename}")
        continue

    # Backup original
    bak_path = os.path.join(BACKUP_DIR, filename + ".bak")
    with open(filepath, "rb") as f:
        original = f.read()
    with open(bak_path, "wb") as f:
        f.write(original)
    print(f"BACKUP: {filename} ({len(original)} bytes)")

    # Write stub (use proper line endings to avoid \r\r\n issues)
    # Write the import first, then the function
    content = 'import { type JSX } from "react";\n\n' + stub_content + "\n"
    with open(filepath, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)
    print(f"STUB: {filename}")

print(f"\nDone. Backups in: {BACKUP_DIR}")
