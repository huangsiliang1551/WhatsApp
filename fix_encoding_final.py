"""Proper encoding fix for PowerShell-corrupted TypeScript files.
Strategy:
1. Read file bytes
2. Detect corruption pattern: \r\r\n means line endings got doubled
3. Try GBK encode -> UTF-8 decode recovery line by line
4. For characters that still can't recover, keep the original garbled form (valid TS syntax)
5. Normalize line endings to \r\n
"""
import os, re, glob

def fix_file(filepath):
    with open(filepath, 'rb') as fh:
        raw = fh.read()
    
    # Normalize line endings first: \r\r\n -> \r\n
    text = raw.decode('utf-8', errors='replace')
    
    # Fix doubled CR: \r\r\n -> \r\n
    text = text.replace('\r\r\n', '\r\n')
    # Fix any remaining doubled CR
    text = text.replace('\r\r\n', '\r\n')
    # Also fix \r\r (not followed by \n) -> \r
    text = re.sub(r'\r(?!\n)', '\r\n', text)
    
    # Now try GBK recovery on each line
    lines = text.split('\r\n')
    recovered_lines = []
    for line in lines:
        # Skip if all ASCII
        if all(ord(c) < 128 for c in line):
            recovered_lines.append(line)
            continue
        
        # Try GBK round-trip
        try:
            gbk_bytes = line.encode('gbk')
            recovered = gbk_bytes.decode('utf-8', errors='replace')
            # If recovery produced replacement chars, keep individual line chars that failed
            if '\ufffd' in recovered:
                # Mixed recovery - recover char by char
                recovered_chars = []
                for ch in line:
                    try:
                        gb = ch.encode('gbk')
                        rc = gb.decode('utf-8', errors='replace')
                        recovered_chars.append(rc)
                    except UnicodeEncodeError:
                        # Can't encode in GBK - these chars had further corruption
                        # Try to find a reasonable replacement or keep original
                        recovered_chars.append(ch)
                recovered_lines.append(''.join(recovered_chars))
            else:
                recovered_lines.append(recovered)
        except UnicodeEncodeError:
            # Character-by-character fallback
            recovered_chars = []
            for ch in line:
                try:
                    gb = ch.encode('gbk')
                    rc = gb.decode('utf-8')
                    recovered_chars.append(rc)
                except (UnicodeEncodeError, UnicodeDecodeError):
                    recovered_chars.append(ch)
            recovered_lines.append(''.join(recovered_chars))
        except Exception:
            recovered_lines.append(line)
    
    new_content = '\r\n'.join(recovered_lines)
    
    # Remove AdminDataSourceLegend  
    new_content = re.sub(r'import \{ AdminDataSourceLegend \} from "../components/AdminDataSourceLegend";\s*\r?\n?', '', new_content)
    new_content = re.sub(r'<AdminDataSourceLegend[^>]*/>\s*\r?\n?', '', new_content)
    
    # Write back
    with open(filepath, 'w', encoding='utf-8', newline='\r\n') as fh:
        fh.write(new_content)
    
    remaining = new_content.count('\ufffd')
    return remaining


pages_dir = r'E:\codex\WhatsApp\frontend\src\pages'
skip = {'DashboardPage.tsx', 'ChatPage.tsx',
    'admin-chat.test.tsx', 'dashboardPage.test.tsx', 'loginPage.test.tsx',
    'memberCustomerNavigation.test.tsx', 'metaAccountsPage.test.tsx', 'templatePage.test.tsx'}

total_remaining = 0
for f in sorted(os.listdir(pages_dir)):
    if not f.endswith('.tsx') or f in skip:
        continue
    path = os.path.join(pages_dir, f)
    remaining = fix_file(path)
    total_remaining += remaining
    status = '✓' if remaining == 0 else f'⚠ ({remaining})'
    print(f'{status} {f}')

print(f'\nTotal remaining replacement chars: {total_remaining}')

# Also fix admin-chat subdirectory
admin_chat = os.path.join(pages_dir, 'admin-chat')
if os.path.isdir(admin_chat):
    for f in os.listdir(admin_chat):
        if f.endswith('.tsx'):
            path = os.path.join(admin_chat, f)
            remaining = fix_file(path)
            print(f'{'✓' if remaining==0 else f"⚠ ({remaining})"} admin-chat/{f}')
