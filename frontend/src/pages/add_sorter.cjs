const fs = require('fs');

// 简易方案：逐文件、逐列处理
// 只处理"简单列"（无嵌套对象的单行或几行 column 定义）
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
];

let modifiedCount = 0;

FILES.forEach(file => {
  if (!fs.existsSync(file)) return;
  let c = fs.readFileSync(file, 'utf8');
  const original = c;

  // 策略：找到所有 dataIndex: "XXX" 所在的 column 块
  // 如果该块内没有 sorter:，则在合适位置插入
  // 由于正则很难处理嵌套，我们采用"行级"策略：
  //   1. 找到包含 dataIndex: "XXX" 的行
  //   2. 往前找到 { title: 的行（同一个 column 开始）
  //   3. 往后找到这个 column 的结束 }
  //   4. 检查块内是否有 sorter:
  //   5. 如果没有，在 } 前插入 sorter

  // 但实际上，最安全的做法是：只处理"单行 column 定义"
  // 即：{ title: "X", dataIndex: "Y", key: "Z", width: N },
  // 这种可以在 }, 前直接插入 sorter

  // 匹配简单列：{ ... dataIndex: "XXX" ... },（无换行）
  const simpleColRe = /\{(?=[^}]*?\bdataIndex:/s*["']([^"']*)["'])(?![^}]*?\bsorter:)[^}]*?\},\s*(?=\n)/g;

  c = c.replace(simpleColRe, (match, idx) => {
    if (match.includes('render:')) return match; // 有 render 的不在这里处理
    // 在 }, 前插入 sorter
    return match.replace('},', `, sorter: (a, b) => (a.${idx} ?? "").localeCompare(b.${idx} ?? ""), sortDirections: ["ascend","descend"]},`);
  });

  // 处理有 render: 的列：在 render: 前插入 sorter
  // 匹配包含 dataIndex 和 render: 的 column 块（可能多行）
  // 简化：只处理 render: (v) => ... 或 render: (v, r) => ... 的情况
  // 在 render: 前插入 sorter
  const renderColRe = /\{(?=[^}]*?\bdataIndex:/s*["']([^"']*)["'])(?=[^}]*?\brender:)(?![^}]*?\bsorter:)[\s\S]*?\},\s*(?=\n)/g;

  c = c.replace(renderColRe, (match, idx) => {
    // 在 render: 前插入 sorter
    return match.replace(/(?<=,\s)render:/, `sorter: (a, b) => (a.${idx} ?? "").localeCompare(b.${idx} ?? ""), sortDirections: ["ascend","descend"], render:`);
  });

  if (c !== original) {
    fs.writeFileSync(file, c, 'utf8');
    console.log('✅ 已修改:', file);
    modifiedCount++;
  }
});

console.log(`\n完成！共修改 ${modifiedCount} 个文件`);
