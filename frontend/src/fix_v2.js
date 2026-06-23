// fix_v2.js - 简化版修复脚本
const fs = require('fs');
const path = require('path');

const SRC = process.argv[2] || __dirname;
const exts = ['.tsx', '.ts'];
const files = [];

function walk(dir) {
  try {
    const items = fs.readdirSync(dir, { withFileTypes: true });
    for (const it of items) {
      const full = path.join(dir, it.name);
      if (it.isDirectory() && !['node_modules', '.git', 'dist', 'build'].includes(it.name)) walk(full);
      else if (it.isFile() && exts.some(e => it.name.endsWith(e))) files.push(full);
    }
  } catch {}
}
walk(SRC);

let fixed = 0;

files.forEach(file => {
  let c = fs.readFileSync(file, 'utf8');
  const orig = c;

  // 只处理包含 withSorter 的文件（其他文件不可能有 ]}) 来自我们的脚本）
  if (!c.includes('withSorter')) return;

  // 策略：逐字符扫描，做括号匹配
  // 找到所有 withSorter([ 的位置，记录它们对应的 ]}) 位置
  // 其余 ]}) 都还原

  const validClosings = new Set(); // 记录合法的 ]}) 的索引

  // 找所有 withSorter([ 
  let idx = 0;
  while ((idx = c.indexOf('withSorter([', idx)) !== -1) {
    // 从这个 [ 开始做括号匹配
    let depth = 1; // 已经有一个未配对的 [
    let pos = idx + 'withSorter(['.length;
    while (pos < c.length && depth > 0) {
      if (c[pos] === '[') depth++;
      else if (c[pos] === ']') depth--;
      if (depth === 0) {
        // 找到了配对的 ]，现在期望后面是 }) 
        if (c[pos + 1] === '}' && c[pos + 2] === ')') {
          validClosings.add(pos + 1); // 记录 } 的位置
        }
        break;
      }
      pos++;
    }
    idx++;
  }

  // 找所有 withSorter(varName)}) 模式
  idx = 0;
  while ((idx = c.indexOf('withSorter(', idx)) !== -1) {
    // 检查是否是 withSorter(varName)}) （即不是 withSorter([）
    const after = idx + 'withSorter('.length;
    if (c[after] === '[') { idx++; continue; } // 已经是数组模式，上面处理了
    // 找配对的 )
    let parenDepth = 1;
    let pos = after;
    while (pos < c.length && parenDepth > 0) {
      if (c[pos] === '(') parenDepth++;
      else if (c[pos] === ')') parenDepth--;
      if (parenDepth === 0) {
        // 期望后面是 }
        if (c[pos + 1] === '}') {
          validClosings.add(pos + 1);
        }
        break;
      }
      pos++;
    }
    idx++;
  }

  // 现在还原所有不在 validClosings 中的 ]})
  let result = '';
  for (let i = 0; i < c.length; i++) {
    if (c[i] === ']' && c[i+1] === '}' && c[i+2] === ')') {
      const bracePos = i + 1;
      if (validClosings.has(bracePos)) {
        result += ']})';
        i += 2;
      } else {
        result += ']}';
        i += 2;
      }
    } else {
      result += c[i];
    }
  }

  if (result !== c) {
    fs.writeFileSync(file, result, 'utf8');
    console.log('✅ ' + path.relative(SRC, file));
    fixed++;
  }
});

console.log(`\n完成！修复 ${fixed} 个文件`);
