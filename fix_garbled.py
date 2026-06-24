"""Fix garbled Chinese text (GBK mojibake) in frontend source files."""
import os

BASE = r"e:\codex\WhatsApp\frontend\src\pages"

def fix_file(filepath, replacements):
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
    before = content
    for bad, good in replacements.items():
        content = content.replace(bad, good)
    if content != before:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        count = sum(before.count(k) for k in replacements)
        print(f"  Fixed {count} occurrences in {os.path.basename(filepath)}")
    else:
        print(f"  No changes in {os.path.basename(filepath)}")

# ===== 1. SystemLogsPage.tsx =====
fix_file(os.path.join(BASE, "SystemLogsPage.tsx"), {
    "\u03b5\u03c3\u03c4\u03b7\u03bc\u03b1\u03c1-\u03b5\u03c0\u03b1\u03b3\u03c1\u03b7\u03c4\u03b7\u03bc\u03b1": "系统日志加载失败",
})
