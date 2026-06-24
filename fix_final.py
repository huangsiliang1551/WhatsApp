"""Fix garbled text in SystemLogsPage.tsx using byte-level operations."""
import re

filepath = r"e:\codex\WhatsApp\frontend\src\pages\SystemLogsPage.tsx"

with open(filepath, "r", encoding="utf-8") as f:
    text = f.read()

# Build a comprehensive fix table - each entry: (pattern, replacement)
# pattern is a regex, replacement is the correct Chinese text
fixes = {
    # Button texts
    r">֤\ufeff֤\ufeff\ufeff\ufeff\n          </Button>": ">证据中心\n          </Button>",
    r">\ufeff\ufeff\ufeff\ufeff\n          </Button>": ">审计\n          </Button>",
    r">\ufeff\ufeff\ufeff\ufeff\ufeff\ufeff\ufeff\ufeff\n          </Button>": ">运营看板\n          </Button>",
    r">\ufeff\ufeff\ufeff\ufeff\n          </Button>": ">刷新\n          </Button>",
    # Statistics
    r'title="\ufeff\ufeff\ufeff\ufeff\ufeff\ufeff\ufeff\ufeff" value={snapshot?.audit_count': 'title="审计数量" value={snapshot?.audit_count',
    r'title="\ufeff\ufeff\ufeff\ufeff" value={snapshot?.provider_pending_count': 'title="待处理" value={snapshot?.provider_pending_count',
    r'title="\ufeff\ufeff\ufeff\ufeff\ufeff\ufeff\ufeff\ufeff" value={snapshot?.failed_job_count': 'title="失败数量" value={snapshot?.failed_job_count',
    r'title="\ufeff\ufeff\ufeff\ufeff\ufeff\ufeff\ufeff\ufeff" value={snapshot?.critical_count': 'title="严重告警" value={snapshot?.critical_count',
    # Card title
    r'title="\ufeff\ufeff\ufeff\ufeff\ufeff\ufeff\ufeff\ufeff">': 'title="当前选中">',
    # Descriptions
    r'label="\ufeff\ufeff\ufeff\ufeff">': 'label="来源">',
    r'label="\ufeff\ufeff\ufeff\ufeff">\n                  {selectedEntry.account_id ?? "\ufeff\ufeff\ufeff\ufeff"}': 'label="账号">\n                  {selectedEntry.account_id ?? "全部"}',
    r'label="\ufeff\ufeff\ufeff\ufeff">': 'label="时间">',
    r'label="\ufeff\ufeff\ufeff\ufeff">{selectedEntry.title}': 'label="标题">{selectedEntry.title}',
    r'label="\ufeff\ufeff\ufeff\ufeff">{selectedEntry.summary}': 'label="摘要">{selectedEntry.summary}',
    r'label="\ufeff\ufeff\ufeff\ufeff">{selectedEntry.detail}': 'label="详情">{selectedEntry.detail}',
    # Empty state
    r">\ufeff\ufeff\ufeff\ufeff\ufeff\ufeff\ufeff\ufeff</Typography.Text>": ">选择日志</Typography.Text>",
    # Error message
    r"\ufeff\ufeff\ufeff\ufeff\ufeff\ufeff\ufeff\ufeff\ufeff\ufeff\ufeff\ufeff\ufeff\ufeff\ufeff\ufeff": "系统日志加载失败",
}

# Actually, the U+FFFD (\ufffd) and various other chars are what we see.
# Let's just do a simple approach - first remove ALL U+FFFD
count_fffd = text.count("\ufffd")
print(f"U+FFFD count: {count_fffd}")

# Replace each garbled line by finding its unique context
# Use the fact that garbled chars are between quotes or > <

# Strategy: find unique phrases around garbled text and replace them
import os

# For the two 'ȫ' occurrences, use their unique surrounding code
# Account filter: surrounded by options=[ ...actorAccountIds
acct_pattern = '{ label: "ȫ\\ufeff\\ufeff\\ufeff\\ufeff", value: "ALL" },\n              ...actorAccountIds'
acct_replacement = '{ label: "全部账号", value: "ALL" },\n              ...actorAccountIds'

# Severity filter: surrounded by options=[ { label: "严重"
sevr_pattern = '{ label: "ȫ\\ufeff\\ufeff\\ufeff\\ufeff", value: "ALL" },\n              { label: "严重"'
sevr_replacement = '{ label: "全部严重度", value: "ALL" },\n              { label: "严重"'

changes = 0

# Try replacing with unique context
for pattern, replacement in [(acct_pattern, acct_replacement), (sevr_pattern, sevr_replacement)]:
    if pattern in text:
        text = text.replace(pattern, replacement)
        changes += 1
        print(f"Fixed: {pattern[:20]}... -> {replacement[:20]}...")
    else:
        print(f"NOT FOUND: {pattern[:30]}...")

# For the buttons, find unique contexts
# 证据中心 button
if 'openEvidencePage' in text:
    old = 'openEvidencePage({\n                account_id: accountFilter !== "ALL" ? accountFilter : undefined,\n                source_kind:\n                  sourceFilter !== "ALL"\n                    ? sourceFilter\n                    : selectedEntry?.source_kind === "audit"\n                      ? "audit"\n                      : selectedEntry?.source_kind === "provider"\n                        ? "provider"\n                        : "queue",\n              })\n            }\n          >\n            \ufeff\ufeff\ufeff\ufeff\ufeff\ufeff\ufeff\ufeff\n          </Button>'
    new = 'openEvidencePage({\n                account_id: accountFilter !== "ALL" ? accountFilter : undefined,\n                source_kind:\n                  sourceFilter !== "ALL"\n                    ? sourceFilter\n                    : selectedEntry?.source_kind === "audit"\n                      ? "audit"\n                      : selectedEntry?.source_kind === "provider"\n                        ? "provider"\n                        : "queue",\n              })\n            }\n          >\n            证据中心\n          </Button>'
    if old in text:
        text = text.replace(old, new)
        changes += 1
        print("Fixed: 证据中心 button")

# 审计 button
if 'openAuditPage' in text:
    old = 'openAuditPage({\n                account_id: accountFilter !== "ALL" ? accountFilter : undefined,\n                limit: 50,\n              })\n            }\n          >\n            \ufeff\ufeff\ufeff\ufeff\ufeff\ufeff\ufeff\ufeff\n          </Button>'
    new = 'openAuditPage({\n                account_id: accountFilter !== "ALL" ? accountFilter : undefined,\n                limit: 50,\n              })\n            }\n          >\n            审计\n          </Button>'
    if old in text:
        text = text.replace(old, new)
        changes += 1
        print("Fixed: 审计 button")

# 运营看板 button
if 'openOperationsPage' in text:
    old = 'openOperationsPage({\n                account_id: accountFilter !== "ALL" ? accountFilter : undefined,\n              })\n            }\n          >\n            \ufeff\ufeff\ufeff\ufeff\ufeff\ufeff\ufeff\ufeff\n          </Button>'
    new = 'openOperationsPage({\n                account_id: accountFilter !== "ALL" ? accountFilter : undefined,\n              })\n            }\n          >\n            运营看板\n          </Button>'
    if old in text:
        text = text.replace(old, new)
        changes += 1
        print("Fixed: 运营看板 button")

# 刷新 button
old = 'loading={loading} onClick={() => void loadPage()} type="primary">\n            \ufeff\ufeff\ufeff\ufeff\ufeff\ufeff\ufeff\ufeff\n          </Button>'
new = 'loading={loading} onClick={() => void loadPage()} type="primary">\n            刷新\n          </Button>'
if old in text:
    text = text.replace(old, new)
    changes += 1
    print("Fixed: 刷新 button")

if changes:
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(text)
    
    remaining = text.count("\ufffd")
    print(f"\nTotal changes: {changes}")
    print(f"Remaining U+FFFD: {remaining}")
else:
    print("\nNo changes made!")

print("Done!")
