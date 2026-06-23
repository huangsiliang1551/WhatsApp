const fs = require('fs');
const src = fs.readFileSync('src/routes/consoleRoutes.ts', 'utf-8');

const groups = {workspace:0,content:0,people:0,analytics:0,settings:0,devops:0};
const groupOrder = ['workspace','content','people','analytics','settings','devops'];
const lines = src.split('\n');
let currentGroup = '';
for (const line of lines) {
  const trimmed = line.trim();
  const gMatch = trimmed.match(/^group:\s*"(\w+)"/);
  if (gMatch) currentGroup = gMatch[1];
  const vMatch = trimmed.match(/^visibleInNav:\s*(true|false)/);
  if (vMatch && vMatch[1] === 'true' && currentGroup && groups[currentGroup] !== undefined) {
    groups[currentGroup]++;
  }
}
console.log('Route validation:');
console.log('  Groups:', groupOrder.length);
console.log('  Group page counts:', JSON.stringify(groups));
const total = Object.values(groups).reduce((a,b)=>a+b,0);
console.log('  Total visible routes:', total);
const maxGroup = Math.max(...Object.values(groups));
console.log('  Max pages in a group:', maxGroup, '(max 7 OK)');
console.log('  All groups <= 7:', maxGroup <= 7);
console.log('  PASS:', total === 28 && maxGroup <= 7 && groupOrder.length === 6 ? 'YES' : 'NO');
