"""Fix encoding corruption caused by PowerShell Set-Content on Chinese Windows.
The original UTF-8 Chinese was read as GBK (system default on Chinese Windows),
then re-written. This script reverses that by encoding garbled Unicode back to GBK bytes,
then decoding as UTF-8 to recover the original Chinese text.
"""
import os, re

pages_dir = r"E:\codex\WhatsApp\frontend\src\pages"
skip_files = {
    'DashboardPage.tsx', 'ChatPage.tsx',
    'admin-chat.test.tsx', 'dashboardPage.test.tsx', 'loginPage.test.tsx',
    'memberCustomerNavigation.test.tsx', 'metaAccountsPage.test.tsx', 'templatePage.test.tsx',
}

for f in sorted(os.listdir(pages_dir)):
    if not f.endswith('.tsx') or f in skip_files:
        continue
    path = os.path.join(pages_dir, f)
    with open(path, 'rb') as fh:
        raw = fh.read()
    
    # Current content (already UTF-8 due to previous fix_encoding2.py run)
    try:
        content = raw.decode('utf-8')
    except UnicodeDecodeError:
        print(f"✗ {f}: NOT valid UTF-8, skipping")
        continue
    
    # Check if there are suspicious characters (Bopomofo, half-width katakana, etc.)
    suspicious_chars = {c for c in content if 0x3100 <= ord(c) <= 0x33FF or 0xFF00 <= ord(c) <= 0xFFEF}
    if not suspicious_chars:
        continue  # No corrupted Chinese detected
    
    print(f"  {f}: Found {len(suspicious_chars)} suspicious char types")
    
    # Recover by encoding as GBK, decoding as UTF-8
    recovered_lines = []
    for line in content.split('\n'):
        try:
            gbk_bytes = line.encode('gbk')
            recovered = gbk_bytes.decode('utf-8', errors='replace')
            recovered_lines.append(recovered)
        except UnicodeEncodeError:
            # Some characters can't be encoded in GBK; try character by character
            recovered_chars = []
            for ch in line:
                try:
                    gb = ch.encode('gbk')
                    rc = gb.decode('utf-8', errors='replace')
                    recovered_chars.append(rc)
                except UnicodeEncodeError:
                    # Can't recover this character, keep original
                    recovered_chars.append(ch)
            recovered_lines.append(''.join(recovered_chars))
    
    new_content = '\n'.join(recovered_lines)
    
    # Remove AdminDataSourceLegend if still present
    new_content = re.sub(r'import \{ AdminDataSourceLegend \} from "../components/AdminDataSourceLegend";\s*\n?', '', new_content)
    new_content = re.sub(r'<AdminDataSourceLegend[^>]*/>\s*\n?', '', new_content)
    
    with open(path, 'w', encoding='utf-8') as fh:
        fh.write(new_content)
    print(f"✓ {f}: recovered")

print("\nDone!")
