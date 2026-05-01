import re
from pathlib import Path
p=Path('Overleaf_LaTeX/tabellen/aspen_luftzerlegung_global_single.tex')
s=p.read_text(encoding='utf-8')
key='S1'
pat_math = re.compile(rf"(\$\\dot\{{E\}}_\{{{re.escape(key)}\}}\$\s*&\s*)(.*?)(\\\\)", re.DOTALL)
print('math match:', bool(pat_math.search(s)))
pat_plain = re.compile(rf"(\b{re.escape(key)}\b\s*&\s*)(.*?)(\\\\)", re.DOTALL)
print('plain match:', bool(pat_plain.search(s)))
print('file snippet:')
print('\n'.join(s.splitlines()[4:11]))
