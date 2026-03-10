import os
import re
from pathlib import Path
from matplotlib.lines import Line2D

import matplotlib.pyplot as plt
import pandas as pd


BASE_DIR = Path(r"C:/Users/Felin/Documents/Masterthesis/Simulation_Code/GIT")
TABLE_DOUBLE = BASE_DIR / "Overleaf_LaTeX/tabellen/aspen_luftzerlegung_components.tex"
TABLE_SINGLE = BASE_DIR / "Overleaf_LaTeX/tabellen/aspen_luftzerlegung_components_single.tex"
MOLFRAC_DOUBLE = BASE_DIR / "Overleaf_LaTeX/tabellen/aspen_luftzerlegung_streams_molfrac.tex"
MOLFRAC_SINGLE = BASE_DIR / "Overleaf_LaTeX/tabellen/aspen_luftzerlegung_streams_molfrac_single.tex"
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
    # Accept both formats:
    # old: Component, Type, E_F, E_P, E_D, E_L, epsilon, y_D_k
    # new: Component, Type, E_F, E_P, E_D, epsilon, y_D_k
    pattern = re.compile(r"^\s*([^&]+)&([^&]+)&([^&]+)&([^&]+)&([^&]+)&([^&]+)&([^&]+)(?:&([^\\]+))?\\\\")

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
            y_dk_raw = m.group(8) if m.group(8) is not None else m.group(7)
            y_dk = _to_float(y_dk_raw)

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


def parse_component_ed_map(tex_path: Path) -> dict:
    rows = {}
    pattern = re.compile(r"^\s*([^&]+)&([^&]+)&([^&]+)&([^&]+)&([^&]+)&([^&]+)&([^&]+)(?:&([^\\]+))?\\\\")

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

            comp = m.group(1).strip()
            ed = _to_float(m.group(5))
            if comp and isinstance(ed, (int, float)):
                rows[comp] = float(ed)

    if not rows:
        raise ValueError(f"Keine verwertbaren Komponenten-E_D-Daten in {tex_path}")
    return rows


def parse_molfrac_table(tex_path: Path) -> pd.DataFrame:
    rows = []
    pattern = re.compile(r"^\s*([^&]+)&([^&]+)&([^&]+)&([^&]+)&([^&]+)&([^\\]+)\\\\")

    with tex_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("\\"):
                continue
            if line.startswith("Stream") or line.startswith("&"):
                continue

            m = pattern.match(line)
            if not m:
                continue

            stream = m.group(1).strip()
            x_n2 = _to_float(m.group(2))
            x_o2 = _to_float(m.group(3))
            if x_n2 is None or x_o2 is None:
                continue

            rows.append({"Stream": stream, "x_N2": x_n2, "x_O2": x_o2})

    df = pd.DataFrame(rows)
    if df.empty:
        raise ValueError(f"Keine verwertbaren Molfraktionsdaten in {tex_path}")
    return df


def plot_grouped_product_purity(df_double_mol: pd.DataFrame, df_single_mol: pd.DataFrame, out_path: Path):
    # Requested product stream mapping.
    stream_map = {
        "single": {"n2": "S24", "o2": "S21"},
        "double": {"n2": "S32", "o2": "S28"},
    }

    def _pick(df: pd.DataFrame, stream: str, key: str):
        hit = df.loc[df["Stream"] == stream, key]
        if hit.empty:
            raise ValueError(f"Stream {stream} nicht in Molfraktions-Tabelle gefunden.")
        return float(hit.iloc[0])

    single_n2 = _pick(df_single_mol, stream_map["single"]["n2"], "x_N2")
    single_o2 = _pick(df_single_mol, stream_map["single"]["o2"], "x_O2")
    double_n2 = _pick(df_double_mol, stream_map["double"]["n2"], "x_N2")
    double_o2 = _pick(df_double_mol, stream_map["double"]["o2"], "x_O2")

    plt.style.use("seaborn-v0_8-whitegrid")
    plt.rcParams.update(
        {
            "font.family": "serif",
            "mathtext.fontset": "stix",
            "axes.labelsize": 12,
            "xtick.labelsize": 11,
            "ytick.labelsize": 10,
            "legend.fontsize": 10,
        }
    )

    fig, ax_left = plt.subplots(figsize=(7.2, 5.4))
    ax_right = ax_left.twinx()

    categories = ["Stickstoff-Produktstrom", "Sauerstoffreststrom"]
    x = [0.0, 0.6]
    width = 0.12  # slight gap avoids visual seam between adjacent bars
    dx = 0.07

    # Colors requested to match existing style.
    color_single = "#55A868"
    color_double = "#4C72B0"

    # Nitrogen product category on left axis.
    b_single_n2 = ax_left.bar(
        x[0] - dx,
        single_n2,
        width=width,
        color=color_single,
        edgecolor="none",
        linewidth=0,
        label="Einkolonnen-Modell",
    )
    b_double_n2 = ax_left.bar(
        x[0] + dx,
        double_n2,
        width=width,
        color=color_double,
        edgecolor="none",
        linewidth=0,
        label="Doppelkolonnen-Modell",
    )

    # Oxygen category on right axis (0..1).
    b_single_o2 = ax_right.bar(
        x[1] - dx,
        single_o2,
        width=width,
        color=color_single,
        edgecolor="none",
        linewidth=0,
    )
    b_double_o2 = ax_right.bar(
        x[1] + dx,
        double_o2,
        width=width,
        color=color_double,
        edgecolor="none",
        linewidth=0,
    )

    ax_left.set_xticks(x)
    ax_left.set_xticklabels(categories)
    ax_left.set_ylabel(r"Molare Zusammensetzung, $x_i$ (kmol/kmol)")

    # Left axis for high-purity N2 visibility.
    ax_left.set_ylim(0.9999, 1.00)
    ax_left.set_yticks([0.9999 + 0.00002 * i for i in range(int((1.00 - 0.9999) / 0.00002) + 1)])

    # Right axis for O2 full range.
    ax_right.set_ylim(0.0, 1.0)
    ax_right.set_yticks([0.1 * i for i in range(11)])
    ax_left.set_xlim(-0.28, 0.88)

    # Remove all vertical axis lines and tick marks for cleaner look.
    ax_left.spines["left"].set_visible(False)
    ax_left.spines["right"].set_visible(False)
    ax_right.spines["left"].set_visible(False)
    ax_right.spines["right"].set_visible(False)
    ax_left.spines["top"].set_visible(False)
    ax_right.spines["top"].set_visible(False)
    ax_left.tick_params(axis="y", length=0)
    ax_right.tick_params(axis="y", length=0)

    ax_left.grid(axis="y", linestyle="--", alpha=0.35)
    ax_right.grid(False)

    # Value labels for transparency.
    for bars, axis in ((b_single_o2, ax_right), (b_double_o2, ax_right), (b_single_n2, ax_left), (b_double_n2, ax_left)):
        y_max = axis.get_ylim()[1]
        offset = y_max * 0.01
        for bar in bars:
            v = bar.get_height()
            axis.text(
                bar.get_x() + bar.get_width() / 2,
                v + offset,
                f"{v:.4f}",
                ha="center",
                va="bottom",
                fontsize=9,
            )

    # Legend below the plot.
    handles = [b_single_o2[0], b_double_o2[0]]
    labels = ["Einkolonnen-Modell", "Doppelkolonnen-Modell"]
    ax_left.legend(handles, labels, loc="upper center", bbox_to_anchor=(0.5, -0.14), ncol=2, frameon=False)

    fig.subplots_adjust(left=0.16, right=0.90, bottom=0.22, top=0.97)
    fig.savefig(out_path, dpi=300)
    plt.close(fig)


def _component_sum(ed_map: dict, components: list[str]) -> float:
    return float(sum(float(ed_map.get(c, 0.0)) for c in components))


def _compute_block_yd_payload(ed_map: dict, model: str):
    # Cooled-compression is not shown as a separate point,
    # but its components remain included inside the V+G block.
    ignored = set()

    if model == "single":
        comp_only = ["LK1", "ZK1", "LK2"]
        gas_only = ["ZK2", "GW1", "GW2"]
        heat_transfer = ["MH", "RECO"]
        column_block = ["KOL", "D1"]
    else:
        comp_only = ["LK1", "ZK1", "LK2", "PK1"]
        gas_only = ["ZK2", "GW1", "GW2"]
        heat_transfer = ["MW", "RC", "RC2"]
        column_block = ["KOLHP", "KOLLP", "D1", "D2", "D3"]

    named_sets = {
        "comp_only": set(comp_only),
        "gas_only": set(gas_only),
        "combined": set(comp_only) | set(gas_only),
        "heat": set(heat_transfer),
        "column": set(column_block),
    }

    all_components = set(ed_map.keys())
    used = set()
    for s in named_sets.values():
        used |= set(s)
    used -= ignored
    rest_components = sorted((all_components - used) - ignored)

    # Normalize by all considered components (excluding explicitly ignored ones),
    # so combined + heat + column + rest sums to 100%.
    considered_components = sorted(all_components - ignored)
    total_ed = _component_sum(ed_map, considered_components)
    if total_ed <= 0:
        total_ed = 1.0

    sums = {
        "combined": _component_sum(ed_map, sorted(named_sets["combined"] - ignored)),
        "comp_only": _component_sum(ed_map, sorted(named_sets["comp_only"] - ignored)),
        "gas_only": _component_sum(ed_map, sorted(named_sets["gas_only"] - ignored)),
        "heat": _component_sum(ed_map, sorted(named_sets["heat"] - ignored)),
        "column": _component_sum(ed_map, sorted(named_sets["column"] - ignored)),
        "rest": _component_sum(ed_map, rest_components),
    }

    y_percent = {k: 100.0 * v / total_ed for k, v in sums.items()}
    return {"total_ed": total_ed, "sums": sums, "y": y_percent}


def plot_block_yd_comparison(ed_single: dict, ed_double: dict, out_path: Path):
    payload_single = _compute_block_yd_payload(ed_single, "single")
    payload_double = _compute_block_yd_payload(ed_double, "double")

    cats = ["V+G Block", "Wärmeübertrager", "Kolonnenblock", "Rest"]
    x = [0, 1, 2, 3]

    y_s = [
        payload_single["y"]["combined"],
        payload_single["y"]["heat"],
        payload_single["y"]["column"],
        payload_single["y"]["rest"],
    ]
    y_d = [
        payload_double["y"]["combined"],
        payload_double["y"]["heat"],
        payload_double["y"]["column"],
        payload_double["y"]["rest"],
    ]

    s_sub = [payload_single["y"]["comp_only"], payload_single["y"]["gas_only"]]
    d_sub = [payload_double["y"]["comp_only"], payload_double["y"]["gas_only"]]

    plt.style.use("seaborn-v0_8-whitegrid")
    plt.rcParams.update(
        {
            "font.family": "serif",
            "mathtext.fontset": "stix",
            "axes.labelsize": 12,
            "xtick.labelsize": 11,
            "ytick.labelsize": 11,
            "legend.fontsize": 11,
        }
    )

    fig, ax = plt.subplots(figsize=(8.0, 5.8))

    c_single = "#55A868"
    c_double = "#4C72B0"

    dx = 0.12
    x_single = [xi - dx for xi in x]
    x_double = [xi + dx for xi in x]

    ax.scatter(x_single, y_s, marker="s", s=62, color=c_single, edgecolors="black", linewidths=0.6, label="Singlekolonne", zorder=4)
    ax.scatter(x_double, y_d, marker="^", s=68, color=c_double, edgecolors="black", linewidths=0.6, label="Doppelkolonne", zorder=4)

    # Sub-points only for the combined compression+gas-treatment block.
    x0s = x_single[0]
    x0d = x_double[0]
    # first sub-point = Kompression, second = Reinigung
    ax.scatter([x0s], [s_sub[0]], marker="o", s=34, color=c_single, edgecolors="black", linewidths=0.5, zorder=5)
    ax.scatter([x0s], [s_sub[1]], marker="D", s=34, color=c_single, edgecolors="black", linewidths=0.5, zorder=5)
    ax.scatter([x0d], [d_sub[0]], marker="o", s=34, color=c_double, edgecolors="black", linewidths=0.5, zorder=5)
    ax.scatter([x0d], [d_sub[1]], marker="D", s=34, color=c_double, edgecolors="black", linewidths=0.5, zorder=5)

    ax.set_xticks(x)
    ax.set_xticklabels(cats)
    ax.set_ylabel(r"$y_{D,b}$ [%]")
    ax.set_ylim(0, max(y_s + y_d + s_sub + d_sub) * 1.2)
    ax.grid(axis="y", linestyle="--", alpha=0.35)

    for spine in ["top", "right"]:
        ax.spines[spine].set_visible(False)

    model_handles, model_labels = ax.get_legend_handles_labels()
    extra_handles = [
        Line2D([0], [0], marker="o", color="black", markerfacecolor="black", markersize=6, linestyle="None"),
        Line2D([0], [0], marker="D", color="black", markerfacecolor="black", markersize=6, linestyle="None"),
    ]
    extra_labels = ["Unterpunkt Kompression", "Unterpunkt Reinigung"]
    ax.legend(
        model_handles + extra_handles,
        model_labels + extra_labels,
        loc="upper center",
        bbox_to_anchor=(0.5, -0.12),
        ncol=2,
        frameon=True,
        fancybox=False,
        edgecolor="black",
    )
    fig.subplots_adjust(left=0.14, right=0.97, bottom=0.22, top=0.96)
    fig.savefig(out_path, dpi=300)
    plt.close(fig)


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
    ed_map_double = parse_component_ed_map(TABLE_DOUBLE)
    ed_map_single = parse_component_ed_map(TABLE_SINGLE)
    df_mol_double = parse_molfrac_table(MOLFRAC_DOUBLE)
    df_mol_single = parse_molfrac_table(MOLFRAC_SINGLE)
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

    plot_grouped_product_purity(
        df_mol_double,
        df_mol_single,
        out_path=OUT_DIR / "vergleich_reinheit_produktstroeme_dualaxis.png",
    )

    plot_block_yd_comparison(
        ed_map_single,
        ed_map_double,
        out_path=OUT_DIR / "vergleich_yD_funktionsbloecke.png",
    )

    print("Plots gespeichert in:")
    print(OUT_DIR)


if __name__ == "__main__":
    main()
