from pathlib import Path
p = Path('analyzer/skills.py')
b = p.read_bytes()
print('bytes_len=', len(b))
print('null_index=', b.find(bytes([0])))
print('start_bytes_repr=', repr(b[:300]))
# Also print guessed encoding from BOM
if b.startswith(b"\xff\xfe"):
    print('BOM: UTF-16-LE')
elif b.startswith(b"\xfe\xff"):
    print('BOM: UTF-16-BE')
elif b.startswith(b"\xef\xbb\xbf"):
    print('BOM: UTF-8')
else:
    print('BOM: none')
