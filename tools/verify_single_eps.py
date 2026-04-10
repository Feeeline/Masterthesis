import re
p = 'Overleaf_LaTeX/tabellen/aspen_luftzerlegung_components_single.tex'
with open(p, encoding='utf-8') as f:
    lines = f.read().splitlines()
rows = [l for l in lines if ' & ' in l and not l.strip().startswith('\\')]
for r in rows[2:]:
    parts = [s.strip() for s in r.rstrip('\\').split(' & ')]
    if len(parts) < 8:
        continue
    name = parts[0]
    E_F_s = parts[2].replace('.', '').replace(',', '.')
    E_P_s = parts[3].replace('.', '').replace(',', '.')
    eps_s = parts[5].replace('.', '').replace(',', '.')
    try:
        E_F = float(E_F_s)
        E_P = float(E_P_s)
        eps = float(eps_s)
        calc = E_P / E_F if E_F!=0 else None
        print(name, 'E_F',E_F,'E_P',E_P,'eps_printed',eps,'eps_calc',calc)
    except Exception as e:
        print('skip', name, e)
