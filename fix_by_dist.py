"""
Use the dist JS bundle (which has correct Chinese) to recover 
corrupted admin-chat TSX files by matching context.
"""
import os, re

DIST_JS = r'E:\codex\WhatsApp\frontend\dist\assets\ChatPage-UJmrMMyG.js'
ADMIN_CHAT = r'E:\codex\WhatsApp\frontend\src\pages\admin-chat'

# Read dist JS
with open(DIST_JS, 'rb') as fh:
    raw = fh.read()
try:
    dist_text = raw.decode('utf-8')
except:
    dist_text = raw.decode('latin-1')

# Extract all pairs of (context_before, chinese_text, context_after) from dist
# Chinese text in JS is like: "text中文more" or 'text中文more'
# We want to find each Chinese string and its surrounding ASCII context
chinese_seqs = []
for m in re.finditer(r'[\u4e00-\u9fff\u3000-\u303f\uff00-\uffef]{2,}', dist_text):
    start = max(0, m.start() - 20)
    end = min(len(dist_text), m.end() + 20)
    before = dist_text[start:m.start()]
    chinese = m.group()
    after = dist_text[m.end():end]
    chinese_seqs.append((before, chinese, after))

print(f"Found {len(chinese_seqs)} Chinese sequences in dist")

def fix_corrupted_file(filepath):
    with open(filepath, 'rb') as fh:
        raw = fh.read()
    text = raw.decode('utf-8', errors='replace')
    original = text
    
    # Find all runs of replacement chars
    runs = list(re.finditer(r'[^\x20-\x7e]+', text))
    print(f"  {os.path.basename(filepath)}: {len(runs)} non-ASCII runs")
    
    # For each run, try to find matching Chinese from dist
    for run in reversed(runs):  # Process in reverse to preserve positions
        corrupted = run.group()
        # Get context
        ctx_start = max(0, run.start() - 30)
        ctx_end = min(len(text), run.end() + 30)
        before = text[ctx_start:run.start()]
        after = text[run.end():ctx_end]
        
        # Try to match with dist Chinese sequences
        best_match = None
        best_score = 0
        
        # Look for Chinese sequences where the length matches
        expected_len = len(corrupted)
        
        for c_before, c_text, c_after in chinese_seqs:
            # Check if the surrounding context somewhat matches
            score = 0
            # Compare before contexts
            for i, (a, b) in enumerate(zip(before[-10:], c_before[-10:])):
                if a == b:
                    score += 1
            # Compare after contexts
            for i, (a, b) in enumerate(zip(after[:10], c_after[:10])):
                if a == b:
                    score += 1
            # Bonus for exact char matches in context before
            for ch in before[-5:]:
                if ch.isascii() and ch in c_before:
                    score += 0.5
            
            if score > best_score:
                best_score = score
                best_match = c_text
        
        if best_match and best_score > 5:
            text = text[:run.start()] + best_match + text[run.end():]
            print(f"    Replaced ({best_score}): '{corrupted[:20]}' -> '{best_match}' (ctx: ..{before[-15:]}...{after[:15]}..)")
        else:
            # Fall back to single char replacement
            if best_match:
                print(f"    WEAK MATCH ({best_score}): '{corrupted[:20]}' <- ctx mismatch")
    
    if text != original:
        # Fix double CRLF
        text = text.replace('\r\r\n', '\r\n')
        text = text.replace('\r\r\n', '\r\n')
        with open(filepath, 'w', encoding='utf-8', newline='\r\n') as fh:
            fh.write(text)
        return True
    return False


for f in sorted(os.listdir(ADMIN_CHAT)):
    if not f.endswith('.tsx'):
        continue
    path = os.path.join(ADMIN_CHAT, f)
    changed = fix_corrupted_file(path)
    if changed:
        print(f"  -> Fixed: {f}")

print("\nDone!")
