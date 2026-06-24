"""Fix SystemLogsPage.tsx - byte-level replacement of garbled text."""
import sys

filepath = r"e:\codex\WhatsApp\frontend\src\pages\SystemLogsPage.tsx"

with open(filepath, "rb") as f:
    data = f.read()

print(f"File size: {len(data)} bytes")
original_size = len(data)

# Define replacements as byte sequences
# Each tuple: (search_bytes, replace_bytes)
replacements = []

# Line 114: ϵͳ��־����ʧ�� -> 系统日志加载失败
# The garbled text is UTF-8 encoded Greek/control characters
# Let me find it by its surrounding context
idx = data.find(b"loadError instanceof Error ? loadError.message : ")
if idx >= 0:
    ctx_start = idx + len(b"loadError instanceof Error ? loadError.message : ")
    ctx_end = ctx_start + 50
    garbled = data[ctx_start:ctx_end]
    # Find the closing quote
    str_end = garbled.find(b'"')
    if str_end > 0:
        garbled_str = garbled[:str_end]
        correct = "系统日志加载失败".encode("utf-8")
        replacements.append((garbled_str, correct))
        print(f"Line 114: Found garbled at byte {ctx_start}")
    else:
        print("Line 114: Could not find string end")

# Lines 192, 201: "ȫ������" -> "全部账号"/"全部严重度"
# Find both occurrences with context
for ctx_bytes, replacement in [
    (b'width: 220 }\n            value={accountFilter}\n            options={[\n              { label: "', b'width: 220 }\n            value={accountFilter}\n            options={[\n              { label: "全部账号'),
    (b'width: 160 }\n            value={severityFilter}\n            options={[\n              { label: "', b'width: 160 }\n            value={severityFilter}\n            options={[\n              { label: "全部严重度'),
]:
    idx = data.find(ctx_bytes)
    if idx >= 0:
        # Find the end of the garbled text (up to next ")
        start = idx + len(ctx_bytes)
        end = data.find(b'"', start)
        if end > start:
            garbled = data[start:end]
            replacements.append((garbled, replacement.split(b'"')[-1]))
            print(f"Found garbled at byte {start}: {garbled[:30]}")
    else:
        print(f"Pattern not found for: {ctx_bytes[:60]}")

# Lines 234: ֤������ -> 证据中心
# Lines 244: ���� -> 审计  
# Lines 262: �������� -> 运营看板
# Lines 265: ˢ�� -> 刷新
# These are all between > and </Button>
# Let's find them by their surrounding context
button_contexts = [
    (b'openEvidencePage', b'>\n            ', b'\n          </Button>', b'>\n            证据中心\n          </Button>'),
    (b'openAuditPage', b'>\n            ', b'\n          </Button>', b'>\n            审计\n          </Button>'),
    (b'openOperationsPage', b'>\n            ', b'\n          </Button>', b'>\n            运营看板\n          </Button>'),
    (b'void loadPage()', b'>\n            ', b'\n          </Button>', b'>\n            刷新\n          </Button>'),
]

for keyword, prefix, suffix, replacement in button_contexts:
    idx = data.find(keyword)
    if idx >= 0:
        # Find the button content
        btn_start_search = idx
        suffix_start = data.find(prefix, btn_start_search)
        if suffix_start >= 0:
            btn_content_start = suffix_start + len(prefix)
            btn_end = data.find(suffix, btn_content_start)
            if btn_end >= 0:
                garbled = data[btn_content_start:btn_end]
                print(f"Button '{keyword.decode()}': found garbled at byte {btn_content_start}: {garbled[:40]}")
                replacements.append((garbled, replacement.split(b'>\n            ')[1].split(b'\n          ')[0]))

# Statistics titles
stat_contexts = [
    (b'audit_count', b'title="', b'" value={snapshot?.audit_count', b'title="审计数量" value={snapshot?.audit_count'),
    (b'provider_pending_count', b'title="', b'" value={snapshot?.provider_pending_count', b'title="待处理" value={snapshot?.provider_pending_count'),
    (b'failed_job_count', b'title="', b'" value={snapshot?.failed_job_count', b'title="失败数量" value={snapshot?.failed_job_count'),
    (b'critical_count', b'title="', b'" value={snapshot?.critical_count', b'title="严重告警" value={snapshot?.critical_count'),
]

for keyword, prefix, suffix, replacement in stat_contexts:
    idx = data.find(keyword)
    if idx >= 0:
        # Go backwards to find the title="
        search_from = idx - 50
        if search_from < 0:
            search_from = 0
        prefix_start = data.rfind(prefix.encode(), search_from, idx)
        if prefix_start >= 0:
            title_start = prefix_start + len(prefix)
            # Find closing "
            title_end = data.find(b'"', title_start)
            if title_end >= 0:
                garbled = data[title_start:title_end]
                print(f"Stat '{keyword.decode()}': found at byte {title_start}: {garbled[:30]}")
                replacements.append((garbled, replacement.split(b'"')[1]))

# Card title and description labels
card_contexts = [
    (b'<Card title="', b'"', b'currentSelected">'),  # This is "当前选中"
    (b'label="', b'">', b'来源">'),
    (b'label="���', b'"}>', b'账号">'),
    (b'label="ʱ', b'"}>', b'时间">'),
    (b'label="', b'">{selectedEntry.title}', b'标题">{selectedEntry.title}'),
    (b'label="', b'">{selectedEntry.summary}', b'摘要">{selectedEntry.summary}'),
    (b'label="', b'">{selectedEntry.detail}', b'详情">{selectedEntry.detail}'),
]

print(f"\nTotal replacements to make: {len(replacements)}")

# Apply replacements (process in reverse to not shift indices)
replacements.sort(key=lambda x: -data.find(x[0]) if data.find(x[0]) >= 0 else 0)

applied = 0
for old, new in replacements:
    idx = data.find(old)
    if idx >= 0 and len(old) > 0 and len(new) > 0:
        data = data[:idx] + new + data[idx+len(old):]
        applied += 1
        print(f"  Applied: {old[:20]} -> {new[:20]}")
    else:
        print(f"  Skipped: not found or empty")

if applied > 0:
    with open(filepath, "wb") as f:
        f.write(data)
    print(f"\nApplied {applied} replacements. New file size: {len(data)} bytes")
    
    # Count remaining U+FFFD
    text = data.decode("utf-8")
    remaining = text.count("\ufffd")
    print(f"Remaining U+FFFD: {remaining}")
else:
    print("\nNo replacements applied!")
