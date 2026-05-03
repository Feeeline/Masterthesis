from pathlib import Path
import importlib.util

p = Path(__file__).resolve().parents[1] / 'tools' / 'plot_exergy_results.py'
spec = importlib.util.spec_from_file_location('plot_exergy_results', str(p))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
# Force rounding pass
mod.NO_ROUNDING = False
mod.round_latex_tables(mod.TAB_DIR)
print('Rounding pass completed for', mod.TAB_DIR)
