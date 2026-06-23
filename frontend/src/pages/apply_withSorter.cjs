const fs = require('fs');
const path = require('path');

// 需要处理的文件列表
const FILES = [
  'TasksPage.tsx',
  'TemplatePage.tsx',
  'TicketsPage.tsx',
  'AgentsPage.tsx',
  'AuditPage.tsx',
  'AlertsPage.tsx',
  'ReviewsPage.tsx',
  'BackupsPage.tsx',
  'ApiStatsPage.tsx',
  'MonitoringPage.tsx',
  'ExchangeRatePage.tsx',
  'PaymentChannelPage.tsx',
  'RateLimitsPage.tsx',
  'SecuritySettingsPage.tsx',
  'SettingsPage.tsx',
  'TaskRulesPage.tsx',
  'AutomationRulesPage.tsx',
  'EcommercePage.tsx',
  'KnowledgeBasePage.tsx',
  'AccessControlPage.tsx',
  'IdentitySyncPage.tsx',
  'ImportExportPage.tsx',
  'OrganizationSettingsPage.tsx',
  'RiskCenterPage.tsx',
  'ProviderEventsPage.tsx',
  'MemberAccessPage.tsx',
  'OperationsCenterPage.tsx',
  'AIBillingPage.tsx',
  'agent/AgentUsagePage.tsx',
  'agent/AgentFinancePage.tsx',
  'agent/AgentFinanceSettingsPage.tsx',
];

let modifiedCount = 0;

FILES.forEach(relativePath => {
  const filePath = path.join(__dirname, relativePath);
  if (!fs.existsSync(filePath)) {
    console.log('⏭  跳过（不存在）:', relativePath);
    return;
  }

  let content = fs.readFileSync(filePath, 'utf8');
  const original = content;

  // 1) 确保有 withSorter 的 import
  if (!content.includes('withSorter')) {
    // 找 antd import 行，在它后面加一行 import
    const antImportRe = /(import\s+\{[^}]+\}\s+from\s+["']antd["'];?)/;
    if (antImportRe.test(content)) {
      content = content.replace(antImportRe, (match) => {
        return match + "\nimport { withSorter } from \"../utils/withSorter\";";
      });
    } else {
      // 找不到 antd import，在文件顶部加
      content = 'import { withSorter } from \"../utils/withSorter\";\n' + content;
    }
  }

  // 2) 替换 columns={变量} 为 columns={withSorter(变量)}
  // 只处理简单情况：columns={标识符}
  const simpleRe = /\bcolumns=\{([a-zA-Z_$][\w$]*)\}/g;
  content = content.replace(simpleRe, (match, varName) => {
    if (match.includes('withSorter')) return match;
    return `columns={withSorter(${varName})}`;
  });

  if (content !== original) {
    fs.writeFileSync(filePath, content, 'utf8');
    console.log('✅ 已修改:', relativePath);
    modifiedCount++;
  } else {
    console.log('⏭  无需修改:', relativePath);
  }
});

console.log(`\n完成！共修改 ${modifiedCount} 个文件`);
