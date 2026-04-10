from collections import Counter
p = 'Overleaf_LaTeX/tabellen/aspen_luftzerlegung_components_single.tex'
with open(p, encoding='utf-8') as f:
    lines = f.read().splitlines()
# component rows contain ' & ' and are not LaTeX control lines
rows = [l for l in lines if ' & ' in l and not l.strip().startswith('\\')]
names = [r.split(' & ')[0].strip() for r in rows]
count = Counter(names)
print('Duplicate component counts (only >1 shown):')
for k, v in count.items():
    if v > 1:
        print(f'{k}: {v}')
print('\nAll component rows:')
for i, r in enumerate(rows, 1):
    print(f'{i}: {r}')
