"""Test GBK round-trip recovery mechanism."""
import sys

texts = ['宸', '已', '茬', '生', '教', '效', '鏁']
for t in texts:
    try:
        gbk = t.encode('gbk')
        utf8 = t.encode('utf-8')
        print(f"'{t}' GBK={gbk.hex(' ')} UTF-8={utf8.hex(' ')} match={gbk == utf8}")
    except Exception as e:
        print(f"'{t}' FAILED: {e}")

print()
# Test full phrase
corrupted = '宸茬敓鏁'
print(f'Corrupted: {corrupted}')
try:
    gbk_bytes = corrupted.encode('gbk')
    print(f'GBK bytes: {gbk_bytes.hex(" ")}')
    recovered = gbk_bytes.decode('utf-8', errors='replace')
    print(f'Recovered: {repr(recovered)}')
except Exception as e:
    print(f'Error: {e}')
