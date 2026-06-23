const fs = require('fs');
const path = require('path');

// 需要处理的文件列表（排除已手动加 sorter 的 3 个页面）
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

  // 检查是否已经有 withSorter import
  const hasImport = content.includes('withSorter');
  let importLine = '';

  if (!hasImport) {
    // 需要添加 import 语句
    // 找到第一个 antd 的 import，在它后面加一行
    const antdImportRe = /(import\s+\{[^}]*\}\s+from\s+["']antd["'];/;
    if (antdImportRe.test(content)) {
      // 在 antd import 行后面加
      importLine = "\nimport { withSorter } from \"../utils/withSorter\";";
      content = content.replace(antdImportRe, (match) => match + importLine);
    } else {
      // 找不到 antd import，在文件顶部加
      importLine = "import { withSorter } from \"../utils/withSorter\";\n";
      content = importLine + content;
    }
  }

  // 替换所有 columns={...} 为 columns={withSorter(...)}
  // 但只替换 Table 组件内的 columns={，避免误伤
  // 策略：找到 <Table 标签，然后在其后面的 columns={ 加上 withSorter()

  // 更简单：直接找 columns={  且后面不是 withSorter( 的
  // 替换：columns={   → columns={withSorter(
  // 但要配对花括号

  // 实际方案：用正则找到 columns={ 然后找到对应的 }，包裹 withSorter(
  // 由于嵌套对象很复杂，我们采用简单策略：
  //   只处理 columns={变量名}  的情况（最常见）
  //   和   columns={[ ... ]}  的情况（数组字面量）

  // 模式 1: columns={变量名}
  content = content.replace(
    /\bcolumns=\{(?![^}]*withSorter)\s*([a-zA-Z_$][\w$]*)\s*\}(?=\s*[/>])/g,
    'columns={withSorter($1)}'
  );

  // 模式 2: columns={[ ... ]} （数组字面量，可能多行）
  // 由于多行匹配复杂，先跳过，手动处理

  if (content !== original) {
    fs.writeFileSync(filePath, content, 'utf8');
    console.log('✅ 已修改:', relativePath);
    modifiedCount++;
  } else {
    console.log('⏭  无需修改:', relativePath);
  }
});

console.log(`\n完成！共修改 ${modifiedCount} 个文件`);
