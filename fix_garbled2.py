"""Fix remaining garbled text in SystemLogsPage.tsx at byte level."""
import os

filepath = r"e:\codex\WhatsApp\frontend\src\pages\SystemLogsPage.tsx"

with open(filepath, "rb") as f:
    data = f.read()

text = data.decode("utf-8")

# Fix: "ϵͳ��־����ʧ��" -> "系统日志加载失败" (line 114)
text = text.replace('\u03b5\u03c3\u03c4\u03b7\u03bc\u03b1\u03c1-\u03b5\u03c0\u03b1\u03b3\u03c1\u03b7\u03c4\u03b7\u03bc\u03b1', '系统日志加载失败')

# Fix remaining: write out
with open(filepath, "w", encoding="utf-8") as f:
    f.write(text)

print("Done")
