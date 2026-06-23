// fix_all.js - 精准修复 withSorter 脚本造成的 ]}) 误替换
// 用法: node fix_all.js
const fs = require('fs');
const path = require('path');

// 递归查找所有 .tsx/.ts 文件
function walkDir(dir, exts, fileList) {
  const files = fs.readdirSync(dir, { withFileTypes: true });
  for (const f of files) {
    const full = path.join(dir, f.name);
    if (f.isDirectory() && f.name !== 'node_modules' && f.name !== '.git') {
      walkDir(full, exts, fileList);
    } else if (f.isFile() && exts.some(e => f.name.endsWith(e))) {
      fileList.push(full);
    }
  }
}

// 核心修复逻辑
// 只保留 withSorter([...])} 中的 ]})，其余 ]}) 还原为 ]}
function fixContent(content, filePath) {
  const lines = content.split('\n');
  const result = [];
  let modified = false;

  for (let i = 0; i < lines.length; i++) {
    let line = lines[i];

    // 只处理包含 ]}) 的行
    if (line.includes(']})')) {
      // 检查这一行是否包含 withSorter
      // 如果包含，则 ]}) 可能是正确的（withSorter([...) 的闭合）
      // 但还需要验证：该行是否有 withSorter([ 且没有对应的 ]}) 已配对

      // 启发式：如果这一行有 withSorter 且与 [ 配对，则保留 ]})
      // 否则还原为 ]}

      const hasWithSorter = line.includes('withSorter(');
      const hasColumnsArray = line.includes('withSorter([') || line.includes('columns={withSorter([');

      if (hasColumnsArray) {
        // 可能是正确的，保留 ]})
        result.push(line);
      } else if (hasWithSorter) {
        // withSorter(someVar)}) — 也正确，保留
        // 但检查是否是 withSorter(someVar)}) 模式
        if (line.match(/withSorter\(\w+\)\})/)) {
          result.push(line);
        } else {
          // 不确定，保守还原
          line = line.replace(/\]\}\)/g, ']}');
          modified = true;
          result.push(line);
        }
      } else {
        // 不包含 withSorter，肯定是误替换，还原
        const before = line;
        line = line.replace(/\]\}\)/g, ']}');
        if (before !== line) modified = true;
        result.push(line);
      }
    } else {
      result.push(line);
    }
  }

  return { result: result.join('\n'), modified };
}

// 二次修复：处理跨行情况
// 有些 ]}) 可能在下一行
function fixMultiline(content) {
  // 匹配 pattern: 某行以 ] 结尾，下一行以 }) 开头
  // 这只是 withSorter([ 的闭合
  // 但我们已经在单行处理了大部分情况

  // 更安全的策略：直接全文搜索 ]})，对每个出现位置做 bracket 匹配
  let result = content;
  let modified = false;

  // 找到所有 ]}) 的位置
  let pos = 0;
  while ((pos = result.indexOf(']})', pos)) !== -1) {
    // 向前搜索，看看前面有没有未配对的 withSorter([
    let before = result.lastIndexOf('withSorter([', pos);
    let beforeParen = result.lastIndexOf('withSorter(', pos);

    // 检查 withSorter([ 的 [ 是否已经配对
    let isCorrect = false;
    if (before !== -1) {
      // 检查这个 [ 是否有对应的 ] 在 pos 之前
      let bracketCount = 0;
      let searchPos = before + 'withSorter(['.length;
      while (searchPos < pos) {
        if (result[searchPos] === '[') bracketCount++;
        if (result[searchPos] === ']') bracketCount--;
        searchPos++;
      }
      // 如果到达 pos 时 bracketCount === 0，说明 [ 已配对，]}) 是正确的
      if (bracketCount === 0) isCorrect = true;
    }

    // 检查 withSorter(varName)}) 模式
    if (!isCorrect && beforeParen !== -1) {
      // 简单检查：withSorter(xxx)}) — 中间没有 [ 开盘
      let between = result.substring(beforeParen + 'withSorter('.length, pos);
      if (!between.includes('[')) {
        isCorrect = true;
      }
    }

    if (!isCorrect) {
      // 还原
      result = result.substring(0, pos) + ']}' + result.substring(pos + 3);
      modified = true;
      // 不增加 pos，因为我们已经替换了当前位置
    } else {
      pos += 3; // 跳过 ]})
    }
  }

  return { result, modified };
}

// 主逻辑
const SRC_DIR = process.argv[2] || path.join(__dirname, '..');
const exts = ['.tsx', '.ts'];
const files = [];
walkDir(SRC_DIR, exts, files);

console.log(`扫描 ${files.length} 个文件...`);

let fixedCount = 0;

files.forEach(file => {
  let content = fs.readFileSync(file, 'utf8');
  const original = content;

  // 第一遍：行级修复
  const { result: r1, modified: m1 } = fixContent(content, file);

  // 第二遍：跨行/bracket 匹配修复
  const { result: r2, modified: m2 } = fixMultiline(r1);

  if (m1 || m2) {
    fs.writeFileSync(file, r2, 'utf8');
    console.log(`✅ 修复: ${path.relative(SRC_DIR, file)}`);
    fixedCount++;
  }
});

console.log(`\n完成！共修复 ${fixedCount} 个文件`);
console.log('现在运行 TypeScript 编译检查...');
