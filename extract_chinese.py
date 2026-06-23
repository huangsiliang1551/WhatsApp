import re
with open(r'E:\codex\WhatsApp\frontend\dist\assets\ChatPage-UJmrMMyG.js', 'rb') as fh:
    content = fh.read()
try:
    text = content.decode('utf-8')
except:
    text = content.decode('latin-1')
chinese = re.findall(r'[\u4e00-\u9fff]{2,}', text)
unique = sorted(set(chinese))
print(f'Found {len(unique)} unique Chinese strings')
for s in unique[:100]:
    print(f'  "{s}"')
