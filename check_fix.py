"""Check encoding recovery results for remaining corruption."""
import os

for fname in ['AccessControlPage.tsx', 'UsersPage.tsx', 'WhatsAppStatsPage.tsx']:
    path = rf'E:\codex\WhatsApp\frontend\src\pages\{fname}'
    with open(path, 'rb') as fh:
        raw = fh.read()
    null_count = raw.count(b'\x00')
    lf = raw.count(b'\n')
    crlf = raw.count(b'\r\n')
    print(f'{fname}: {len(raw)} bytes, null={null_count}, CRLF={crlf} LF={lf}')
    text = raw.decode('utf-8')
    fail_count = text.count('\ufffd')
    print(f'  Replacement chars: {fail_count}')
    if fail_count > 0:
        idx = text.find('\ufffd')
        start = max(0, idx-30)
        end = min(len(text), idx+30)
        print(f'  Context: ..., {repr(text[start:end])}, ...')

    # Also look for the ` character which causes JSX issues
    for ch_type, ch in [('backtick', '`'), ('pipe', chr(124)), ('broken bar', chr(166))]:
        cnt = text.count(ch)
        if cnt > 0:
            print(f'  {ch_type} ({repr(ch)}): {cnt} occurrences')
    
    # Check for CRLF issues - some lines might have doubled CR
    if crlf > 0:
        # Check for \r\r\n
        dbl_cr = raw.count(b'\r\r\n')
        if dbl_cr > 0:
            print(f'  Double CR: {dbl_cr} occurrences')
