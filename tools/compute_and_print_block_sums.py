import sys
from pathlib import Path as P
proj_root = P(__file__).resolve().parents[1]
sys.path.insert(0, str(proj_root))
from tools.plot_exergy_results import parse_component_ed_map, _compute_block_yd_payload, TABLE_DOUBLE, TABLE_SINGLE

ed_map_double = parse_component_ed_map(TABLE_DOUBLE)
ed_map_single = parse_component_ed_map(TABLE_SINGLE)

pay_d = _compute_block_yd_payload(ed_map_double, 'double')
pay_s = _compute_block_yd_payload(ed_map_single, 'single')

print('\nDouble sums (W):')
for k,v in pay_d['sums'].items():
    print(f'{k}: {v:.2f} W -> {v/1e6:.6f} MW')
print('y* percent (Double):')
for k,v in pay_d['y'].items():
    print(f'{k}: {v:.4f} %')

print('\nSingle sums (W):')
for k,v in pay_s['sums'].items():
    print(f'{k}: {v:.2f} W -> {v/1e6:.6f} MW')
print('y* percent (Single):')
for k,v in pay_s['y'].items():
    print(f'{k}: {v:.4f} %')
