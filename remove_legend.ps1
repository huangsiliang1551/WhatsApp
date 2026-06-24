$pages = @(
  "OperationsCenterPage", "MetaAccountsPage", "AccessControlPage", "OrganizationSettingsPage",
  "MembersPage", "IdentitySyncPage", "RolesPage", "IntegrationsPage", "AuditPage",
  "EvidenceCenterPage", "MemberAccessPage", "NotificationsPage", "TasksPage", "RiskCenterPage",
  "SettingsPage", "WhatsAppStatsPage", "TicketsPage", "CustomersPage", "AlertsPage",
  "TemplatePage", "AssignmentsPage", "UsersPage", "ReviewsPage", "SecuritySettingsPage", "SitesPage"
)

$dir = "E:\codex\WhatsApp\frontend\src\pages"
$importLine = 'import { AdminDataSourceLegend } from "../components/AdminDataSourceLegend";'

foreach ($page in $pages) {
  $path = Join-Path $dir "$page.tsx"
  if (Test-Path $path) {
    $content = Get-Content $path -Raw
    # 移除 import 行
    $content = $content -replace [regex]::Escape($importLine + "`r`n"), ""
    $content = $content -replace [regex]::Escape($importLine + "`n"), ""
    # 移除 <AdminDataSourceLegend ... /> 单行
    $content = $content -replace "<AdminDataSourceLegend[^>]*/>`r`n?", ""
    $content = $content -replace "<AdminDataSourceLegend[^>]*/>`n?", ""
    Set-Content $path -Value $content -Encoding UTF8
    Write-Output "✓ $page.tsx"
  }
}
Write-Output "Done"
