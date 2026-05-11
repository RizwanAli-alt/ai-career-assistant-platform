import sys, pathlib
from pathlib import Path

print('sys.path length=', len(sys.path))
for p in sys.path:
    try:
        base = Path(p)
    except Exception:
        continue
    candidate = base / 'transformers'
    if candidate.exists():
        print('Found transformers package at', candidate)
        for f in candidate.rglob('*.py'):
            b = f.read_bytes()
            idx = b.find(bytes([0]))
            if idx!=-1:
                print('NULL in', f, 'at', idx)
                # print a short hexdump around location
                start = max(0, idx-20)
                end = min(len(b), idx+20)
                print(b[start:end])
                raise SystemExit(0)
        print('No NULs found in .py files under', candidate)
        # Also inspect __init__.py
        if (candidate / '__init__.py').exists():
            b = (candidate / '__init__.py').read_bytes()
            print('__init__ size', len(b))

print('Search complete')
