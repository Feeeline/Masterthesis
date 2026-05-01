from pathlib import Path
import importlib.util
spec = importlib.util.spec_from_file_location('upd', Path(__file__).with_name('update_global_balances.py'))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
print('module loaded')
print('parse_components_work func:', hasattr(mod, 'parse_components_work'))
work_file = Path(__file__).resolve().parents[1] / 'Overleaf_LaTeX' / 'tabellen' / 'aspen_luftzerlegung_components_work.tex'
print('work_file exists:', work_file.exists())
print('parsed:', mod.parse_components_work(work_file))
