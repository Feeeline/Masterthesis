import os
import re
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


BASE_DIR = Path(r"C:/Users/Felin/Documents/Masterthesis/Simulation_Code/GIT")
TABLE_DOUBLE = BASE_DIR / "Overleaf_LaTeX/tabellen/aspen_luftzerlegung_components.tex"
TABLE_SINGLE = BASE_DIR / "Overleaf_LaTeX/tabellen/aspen_luftzerlegung_components_single.tex"
GLOBAL_DOUBLE = BASE_DIR / "Overleaf_LaTeX/tabellen/aspen_luftzerlegung_global_check.tex"
GLOBAL_SINGLE = BASE_DIR / "Overleaf_LaTeX/tabellen/aspen_luftzerlegung_global_check_single.tex"
OUT_DIR = BASE_DIR / "Overleaf_LaTeX/bilder"


def _to_float(value: str):
    value = value.strip()
    if value in {"-", ""}:
        return None
    value = value.replace("\\", "").strip()
    try:
        return float(value)
    except ValueError:
        return None


def _to_float_latex_number(value: str):
    if value is None:
        return None
    value = str(value)
    value = re.sub(r"\\textbf\{([^}]*)\}", r"\1", value)
    value = value.replace("$", "").replace("\\%", "").replace("%", "")
    value = value.replace("\\", "").replace("{", "").replace("}", "").strip()
    if not value or value == "-":
        return None

    # German thousand separator format (e.g. 7.631.750 or -7.608)
    if re.match(r"^-?\d{1,3}(\.\d{3})+(,\d+)?$", value):
        value = value.replace(".", "").replace(",", ".")
        try:
            return float(value)
        except ValueError:
            return None

    # scientific notation or regular float
    sci_candidate = value.replace(" ", "")
    try:
        return float(sci_candidate)
    except ValueError:
        pass

    # mixed comma decimal fallback
    if "," in value:
        value = value.replace(".", "").replace(",", ".")
        try:
            return float(value)
        except ValueError:
            return None

    return None


def parse_component_table(tex_path: Path) -> pd.DataFrame:
    rows = []
    pattern = re.compile(r"^\s*([^&]+)&([^&]+)&([^&]+)&([^&]+)&([^&]+)&([^&]+)&([^&]+)&([^\\]+)\\\\")

    with tex_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("\\"):
                continue
            if line.startswith("Component") or line.startswith("&"):
                continue

            m = pattern.match(line)
            if not m:
                continue

            component = m.group(1).strip()
            e_d = _to_float(m.group(5))
            y_dk = _to_float(m.group(8))

            if e_d is None or y_dk is None:
                continue

            rows.append(
                {
                    "Component": component,
                    "E_D_W": e_d,
                    "E_D_MW": e_d / 1e6,
                    "y_D_k": y_dk,
                }
            )

    df = pd.DataFrame(rows)
    if df.empty:
        raise ValueError(f"Keine verwertbaren Daten in {tex_path}")

    return df.sort_values("E_D_W", ascending=False).reset_index(drop=True)


def parse_global_master_table(tex_path: Path):
    E_s1 = None
    E_comp = None
    E_prod = None
    W_turb = None
    E_dest = None
    E_loss = None
    E_in_sum = None

    with tex_path.open("r", encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()
            if "&" not in line or line.startswith("\\"):
                continue
            if line.startswith("Posten"):
                continue

            parts = [p.strip() for p in line.replace("\\\\", "").split("&")]
            if len(parts) != 6:
                continue

            left_label = parts[0]
            left_value = _to_float_latex_number(parts[2])
            right_label = parts[3]
            right_value = _to_float_latex_number(parts[5])

            if left_label.startswith("Strom 1"):
                E_s1 = left_value
            elif left_label.startswith("Verdichtung"):
                E_comp = left_value
            elif "Summe Ein" in left_label:
                E_in_sum = left_value

            if right_label.startswith("Produkt"):
                E_prod = right_value
            elif right_label.startswith("Turbinenarbeit"):
                W_turb = right_value
            elif "Exerget. Vernichtung" in right_label:
                E_dest = right_value
            elif "Austrittsverluste" in right_label:
                E_loss = right_value

    total_input = E_in_sum
    if total_input is None and isinstance(E_s1, (int, float)) and isinstance(E_comp, (int, float)):
        total_input = E_s1 + E_comp

    product_total = None
    if isinstance(E_prod, (int, float)) and isinstance(W_turb, (int, float)):
        product_total = E_prod + W_turb

    metrics_w = {
        "Total Input": total_input,
        "Product": product_total,
        "Destruction": E_dest,
        "Losses": E_loss,
    }
    metrics_mw = {k: (v / 1e6 if isinstance(v, (int, float)) else None) for k, v in metrics_w.items()}
    return metrics_w, metrics_mw


def make_plot(df: pd.DataFrame, x_col: str, xlabel: str, out_path: Path, xlim=None):
    plt.style.use("seaborn-v0_8")
    fig, ax = plt.subplots(figsize=(10, 7))

    ax.barh(df["Component"], df[x_col], color="#4C72B0")
    ax.invert_yaxis()

    ax.set_xlabel(xlabel)
    ax.set_ylabel("Component")
    if xlim is not None:
        ax.set_xlim(*xlim)
    ax.grid(axis="x", alpha=0.3)

    fig.tight_layout()
    fig.savefig(out_path, dpi=300)
    plt.close(fig)


def _yd_axis_limit(df: pd.DataFrame, col: str = "y_D_k"):
    values = pd.to_numeric(df[col], errors="coerce").dropna()
    if values.empty:
        return (0, 1)

    share_le_half = (values <= 0.5).mean()
    if share_le_half >= 0.8:
        return (0, 0.5)

    upper = float(values.quantile(0.95))
    upper = max(0.5, min(1.0, upper * 1.1))
    return (0, upper)


def _annotate_vertical_bars(ax, bars, values, unit="MW"):
    ymax = ax.get_ylim()[1]
    offset = ymax * 0.015
    for bar, val in zip(bars, values):
        if val is None:
            continue
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + offset,
            f"{val:.3f} {unit}",
            ha="center",
            va="bottom",
            fontsize=9,
            rotation=0,
        )


def _annotate_horizontal_bars(ax, bars, unit="MW"):
    xmax = ax.get_xlim()[1]
    offset = xmax * 0.01
    for bar in bars:
        width = bar.get_width()
        ax.text(
            width + offset,
            bar.get_y() + bar.get_height() / 2,
            f"{width:.3f} {unit}",
            va="center",
            ha="left",
            fontsize=8,
        )


def plot_grouped_system_metrics(metrics_double_mw, metrics_single_mw, out_path: Path):
    categories = ["Total Input", "Product", "Destruction", "Losses"]
    vals_double = [metrics_double_mw.get(c) for c in categories]
    vals_single = [metrics_single_mw.get(c) for c in categories]

    plt.style.use("seaborn-v0_8")
    fig, ax = plt.subplots(figsize=(10, 6))
    x = range(len(categories))
    width = 0.38

    bars_double = ax.bar([i - width / 2 for i in x], vals_double, width=width, label="Doppelkolonne", color="#4C72B0")
    bars_single = ax.bar([i + width / 2 for i in x], vals_single, width=width, label="Singlekolonne", color="#55A868")

    ax.set_xticks(list(x))
    ax.set_xticklabels(categories)
    ax.set_ylabel("Exergiestrom [MW]")
    ax.legend()
    ax.grid(axis="y", alpha=0.3)

    _annotate_vertical_bars(ax, bars_double, vals_double, unit="MW")
    _annotate_vertical_bars(ax, bars_single, vals_single, unit="MW")

    fig.tight_layout()
    fig.savefig(out_path, dpi=300)
    plt.close(fig)


def plot_component_pareto_comparison(df_double: pd.DataFrame, df_single: pd.DataFrame, out_path: Path):
    plt.style.use("seaborn-v0_8")
    fig, axes = plt.subplots(2, 1, figsize=(11, 12), sharex=False)

    bars_d = axes[0].barh(df_double["Component"], df_double["E_D_MW"], color="#4C72B0")
    axes[0].invert_yaxis()
    axes[0].set_xlabel(r"$\dot{E}_D$ [MW]")
    axes[0].set_ylabel("Doppelkolonne")
    axes[0].grid(axis="x", alpha=0.3)
    _annotate_horizontal_bars(axes[0], bars_d, unit="MW")

    bars_s = axes[1].barh(df_single["Component"], df_single["E_D_MW"], color="#55A868")
    axes[1].invert_yaxis()
    axes[1].set_xlabel(r"$\dot{E}_D$ [MW]")
    axes[1].set_ylabel("Singlekolonne")
    axes[1].grid(axis="x", alpha=0.3)
    _annotate_horizontal_bars(axes[1], bars_s, unit="MW")

    fig.tight_layout()
    fig.savefig(out_path, dpi=300)
    plt.close(fig)


def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    df_double = parse_component_table(TABLE_DOUBLE)
    df_single = parse_component_table(TABLE_SINGLE)
    metrics_double_w, metrics_double_mw = parse_global_master_table(GLOBAL_DOUBLE)
    metrics_single_w, metrics_single_mw = parse_global_master_table(GLOBAL_SINGLE)

    make_plot(
        df_double,
        x_col="E_D_MW",
        xlabel=r"$\dot{E}_D$ [MW]",
        out_path=OUT_DIR / "doppelkolonne_E_D_barh.png",
    )
    make_plot(
        df_double,
        x_col="y_D_k",
        xlabel=r"$y_{D,k}$ [-]",
        xlim=_yd_axis_limit(df_double, "y_D_k"),
        out_path=OUT_DIR / "doppelkolonne_yDk_barh.png",
    )

    make_plot(
        df_single,
        x_col="E_D_MW",
        xlabel=r"$\dot{E}_D$ [MW]",
        out_path=OUT_DIR / "singlekolonne_E_D_barh.png",
    )
    make_plot(
        df_single,
        x_col="y_D_k",
        xlabel=r"$y_{D,k}$ [-]",
        xlim=_yd_axis_limit(df_single, "y_D_k"),
        out_path=OUT_DIR / "singlekolonne_yDk_barh.png",
    )

    plot_grouped_system_metrics(
        metrics_double_mw,
        metrics_single_mw,
        out_path=OUT_DIR / "vergleich_global_kennzahlen_grouped.png",
    )

    plot_component_pareto_comparison(
        df_double,
        df_single,
        out_path=OUT_DIR / "vergleich_component_pareto_ED.png",
    )

    print("Plots gespeichert in:")
    print(OUT_DIR)


if __name__ == "__main__":
    main()
