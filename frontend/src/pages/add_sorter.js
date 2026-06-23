// 批量给所有页面的 Table columns 加 sorter
const fs = require('fs');
const path = require('path');

const TARGET = process.argv[2]; // 如果传了文件名，只处理该文件

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

const files = TARGET ? [TARGET] : FILES;

let totalModified = 0;

files.forEach(file => {
  if (!fs.existsSync(file)) {
    // console.log('跳过（不存在）:', file);
    return;
  }

  let content = fs.readFileSync(file, 'utf8');
  const original = content;

  // 策略：找到所有包含 dataIndex 的 column 定义行
  // 如果同一行（或紧接着几行内）没有 sorter:，则加上
  //
  // 分两种情况：
  // 1) 列有 render 函数 → 在 render: 前插入 sorter
  // 2) 列没有 render（只有 title/dataIndex/key/width 等） → 在 } 前插入 sorter
  //
  // 用正则匹配整个 column 对象（从 { title: 到对应的 }）
  // 但嵌套对象很难用正则，所以用栈式解析

  const lines = content.split('\n');
  const newLines = [];
  let modified = false;

  for (let i = 0; i < lines.length; i++) {
    let line = lines[i];

    // 检测 column 开始：行中包含 `title:` 且后面（在同一 `{}` 内）有 `dataIndex:`
    // 简化：直接找包含 `dataIndex:` 的行，然后往前找到 `{ title:`
    // 再判断这个 column 块里有没有 `sorter:`

    // 更实用的简化方案：
    // 对于 "无 render 的纯数据列"，直接在包含 `dataIndex:` 的行尾加 sorter
    // 对于有 render 的列，在 `render:` 前一行插入 sorter

    newLines.push(line);
  }

  // 简化方案 2：直接针对常见模式做字符串替换
  // 模式 A：{ title: "xxx", dataIndex: "yyy", key: "zzz", width: N }
  //         → 在 } 前加 , sorter: (a, b) => (a.yyy ?? "").localeCompare(b.yyy ?? "")

  // 先处理有 dataIndex 但没有 sorter: 的 column 定义
  // 用正则匹配从 { 到对应 } 的整个 column（非嵌套版本）

  // 实际上，最可靠的方案是：直接用之前成功的方式——
  // 对已经处理过的三个页面，验证过 Edit 工具可以工作
  // 对其他页面，用 node 脚本逐列处理

  // 重新用可靠的正则（只处理简单列定义）
  // 匹配：{ title: "...", dataIndex: "...", ... } 这样的单选对象
  // 排除已经有 sorter: 的

  // 实用方案：只给 "以 }, 或 } 结尾的简单列" 加 sorter
  // 匹配模式：`{ title: "X", dataIndex: "Y", key: "Z", width: N },`
  // 或：`{ title: "X", dataIndex: "Y", key: "Z", width: N, render: ..., }`,

  // 最终简化：用之前 MembersPage.tsx 中验证过的模式，直接字符串替换

  content = original;

  // 1) 给有 dataIndex 但没有 sorter: 且以 }, 结尾的简单列加 sorter
  //    匹配：`{ title: "...", dataIndex: "YYY", ... },`
  //    在 }, 前插入：, sorter: (a, b) => (a.YYY ?? "").localeCompare(b.YYY ?? ""), sortDirections: ["ascend","descend"]

  const colRe = /\{(?=[^}]*?dataIndex:\s*["']([^"']*)["'])(?![^}]*?sorter:)[^}]*?\},\s*(?=\n)/g;

  content = content.replace(colRe, (match, dataIdx) => {
    if (match.includes('render:')) return match; // 有 render 的另处理
    const insert = `, sorter: (a, b) => (a.${dataIdx} ?? "").localeCompare(b.${dataIdx} ?? ""), sortDirections: ["ascend","descend"]`;
    return match.replace('},', `}${insert},`);
  });

  // 2) 给有 render: 的列，在 render: 前插入 sorter
  const renderColRe = /\{(?=[^}]*?dataIndex:\s*["']([^"']*)["'])(?![^}]*?sorter:)[^}]*?render:/g;

  content = content.replace(renderColRe, (match, dataIdx) => {
    const insert = `, sorter: (a, b) => (a.${dataIdx} ?? "").localeCompare(b.${dataIdx} ?? ""), sortDirections: ["ascend","descend"]`;
    return match.replace('render:', `${insert}, render:`);
  });

  if (content !== original) {
    fs.writeFileSync(file, content, 'utf8');
    console.log('✅ 已修改:', file);
    totalModified++;
    modified = true;
  } else {
    // console.log('⏭  无需修改:', file);
  }
});

console.log(`\n完成！共修改 ${totalModified} 个文件`);
