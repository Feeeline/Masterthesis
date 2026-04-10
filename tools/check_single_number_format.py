import re
p = 'Overleaf_LaTeX/tabellen/aspen_luftzerlegung_components_single.tex'
with open(p, encoding='utf-8') as f:
    lines = f.read().splitlines()
rows = [l for l in lines if ' & ' in l and not l.strip().startswith('\\')]
print(f'total rows: {len(rows)}')
bad = []
for i, r in enumerate(rows, 1):
    parts = [s.strip() for s in r.rstrip('\\').split(' & ')]
    if len(parts) < 8:
        continue
    eps, y, ystar = parts[5], parts[6], parts[7]
    pat = re.compile(r'^-?$|^-?\d+,\d{4}$')
    if not pat.match(eps):
        bad.append((i, 'epsilon', eps))
    if not pat.match(y):
        bad.append((i, 'y', y))
    if not pat.match(ystar):
        bad.append((i, 'y*', ystar))

if not bad:
    print('All epsilon/y columns have correct 4-decimal format.')
else:
    print('Format issues found:')
    for item in bad:
        print(item)
    print('\nRows:')
    for i, r in enumerate(rows, 1):
        print(f'{i}: {r}')
