import os, re

pages_dir = r"E:\codex\WhatsApp\frontend\src\pages"

for f in sorted(os.listdir(pages_dir)):
    if not f.endswith('.tsx') or f in ['DashboardPage.tsx', 'ChatPage.tsx']:
        continue
    path = os.path.join(pages_dir, f)
    with open(path, 'rb') as fh:
        raw = fh.read()
    
    # Try various encoding fixes
    content = None
    # Try 1: direct UTF-8
    try:
        content = raw.decode('utf-8')
    except UnicodeDecodeError:
        pass
    
    # Try 2: Read as UTF-8 with BOM
    if content is None:
        try:
            content = raw.decode('utf-8-sig')
        except UnicodeDecodeError:
            pass
    
    # Try 3: The file might have been double-encoded (UTF-8 → Windows-1252 → read as UTF-8)
    # This is common with PowerShell Set-Content + piping.
    # Solution: read as Latin-1 (which preserves all byte values), then re-encode as UTF-8
    if content is None:
        content = raw.decode('latin-1')
        fixed = content.encode('latin-1').decode('utf-8', errors='replace')
        content = fixed
    
    # Remove AdminDataSourceLegend import
    import_pattern = r'import \{ AdminDataSourceLegend \} from "../components/AdminDataSourceLegend";\s*\n?'
    content = re.sub(import_pattern, '', content)
    content = re.sub(r'<AdminDataSourceLegend[^>]*/>\s*\n?', '', content)
    
    # Write back with UTF-8
    with open(path, 'w', encoding='utf-8') as fh:
        fh.write(content)
    print(f"✓ {f}")
