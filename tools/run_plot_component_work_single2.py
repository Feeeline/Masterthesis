from pathlib import Path
from plot_exergy_results import plot_component_work_side_by_side

single = Path("Overleaf_LaTeX/tabellen/aspen_luftzerlegung_components_work_single2.tex")
double = Path("Overleaf_LaTeX/tabellen/aspen_luftzerlegung_components_work.tex")
out = Path("Overleaf_LaTeX/bilder/vergleich_component_work_side_by_side2.png")

plot_component_work_side_by_side(single, double, out)
print(f"Wrote: {out}")
