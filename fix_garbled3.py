"""Fix remaining garbled text in frontend page files."""
import re

def fix_file(filepath, replacements):
    """Replace exact garbled substrings in a file."""
    with open(filepath, 'r', encoding='utf-8') as f:
        text = f.read()
    
    changed = 0
    for old, new in replacements.items():
        # Use regex with re.escape to match literally
        count = text.count(old)
        if count > 0:
            text = text.replace(old, new)
            changed += count
            print(f"  Replaced '{old}' -> '{new}' (x{count})")
    
    if changed:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(text)
        print(f"  Total: {changed} replacements")
    else:
        print("  No matches found")

base = r"e:\codex\WhatsApp\frontend\src\pages"

# === SystemLogsPage.tsx ===
fix_file(f"{base}/SystemLogsPage.tsx", {
    '\u03b5\u03c3\u03c4\u03b7\u03bc\u03b1\u03c1\u03b1\u03c1-\u03b5\u03c0\u03b1\u03b3\u03c1\u03b7\u03c4\u03b7\u03bc\u03b1': '系统日志加载失败',
    '\u020b\u001f\u001f\u001f\u001f\u001f\u001f\u001f\u001f': '全部',
    '\u001f' : '',
})

# Alternative: read file and do hex-level matching
print("\n--- Doing hex-based fix for SystemLogsPage.tsx ---")
with open(f"{base}/SystemLogsPage.tsx", 'rb') as f:
    data = f.read()

# The garbled "ȫ" is U+022B (0xC8 0xAB in UTF-8)
# "ƅ" is U+0185
replacements_hex = {
    b'\xc8\xab\xef\xbf\xbd\xef\xbf\xbd\xef\xbf\xbd\xef\xbf\xbd': b'\xe5\x85\xa8\xe9\x83\xa8',  # ȫ���� -> 全部 (line 192 account filter)
    b'\xc8\xab\xef\xbf\xbd\xef\xbf\xbd\xef\xbf\xbd\xef\xbf\xbd': b'\xe5\x85\xa8\xe9\x83\xa8',  # same for line 201
}

print(f"File size: {len(data)} bytes")
# Find positions of garbled patterns
for i in range(len(data)):
    if data[i:i+3] == b'\xef\xbf\xbd':  # U+FFFD marker
        # Get context: 20 bytes before and after
        start = max(0, i-40)
        end = min(len(data), i+40)
        ctx = data[start:end]
        # Try to show the context
        try:
            ctx_text = ctx.decode('utf-8', errors='replace')
        except:
            ctx_text = str(ctx)
        print(f"  U+FFFD at byte {i}: ...{ctx_text}...")
        break  # Just show first one

print("\nDone")
