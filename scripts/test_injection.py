import re
from pathlib import Path
p=Path('Overleaf_LaTeX/tabellen/aspen_luftzerlegung_global_single.tex')
s=p.read_text(encoding='utf-8')
keys=['S1','S24','S21']
for key in keys:
    pat=re.compile(rf"(\$\\dot\{{E\}}_\{{{re.escape(key)}\}}\$\s*&\s*)([-0-9.,eE+\s]+)(\\\\)")
    m=pat.search(s)
    print(key, 'found?', bool(m))
    if m:
        print('groups:', m.groups())
    target=f"$\\dot{{E}}_{{{key}}}$ & 0 W"
    print('fallback target in file?', target in s)
