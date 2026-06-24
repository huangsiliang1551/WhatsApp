with open('app/api/routes/webhooks.py') as f:
    lines = f.readlines()
for i, line in enumerate(lines, 1):
    stripped = line.strip()
    if stripped.startswith('@router.get') or stripped.startswith('@router.post'):
        print(f'Line {i}: {stripped}')
        if i < len(lines):
            print(f'Line {i+1}: {lines[i].strip()}')
        print()
