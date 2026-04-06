import os
import re
import json
from pathlib import Path
from matplotlib.lines import Line2D
from matplotlib.ticker import FuncFormatter

import matplotlib.pyplot as plt
import pandas as pd


BASE_DIR = Path(r"C:/Users/Felin/Documents/Masterthesis/Simulation_Code/GIT")
TABLE_DOUBLE = BASE_DIR / "Overleaf_LaTeX/tabellen/aspen_luftzerlegung_components.tex"
TABLE_SINGLE = BASE_DIR / "Overleaf_LaTeX/tabellen/aspen_luftzerlegung_components_single.tex"
TABLE_DOUBLE_KLEIN = BASE_DIR / "Overleaf_LaTeX/tabellen/aspen_luftzerlegung_components_klein.tex"
TABLE_SINGLE_KLEIN = BASE_DIR / "Overleaf_LaTeX/tabellen/aspen_luftzerlegung_components_single_klein.tex"
JSON_DOUBLE = BASE_DIR / "examples/json_example/aspen_luftzerlegung.json"
JSON_DOUBLE_KLEIN = BASE_DIR / "examples/json_example/aspen_luftzerlegung_klein.json"
JSON_SINGLE = BASE_DIR / "examples/json_example/aspen_luftzerlegung_single.json"
JSON_SINGLE_KLEIN = BASE_DIR / "examples/json_example/aspen_luftzerlegung_single_klein.json"
MOLFRAC_DOUBLE = BASE_DIR / "Overleaf_LaTeX/tabellen/aspen_luftzerlegung_streams_molfrac.tex"
MOLFRAC_SINGLE = BASE_DIR / "Overleaf_LaTeX/tabellen/aspen_luftzerlegung_streams_molfrac_single.tex"
STREAMS_DOUBLE = BASE_DIR / "Overleaf_LaTeX/tabellen/aspen_luftzerlegung_streams.tex"
STREAMS_SINGLE = BASE_DIR / "Overleaf_LaTeX/tabellen/aspen_luftzerlegung_streams_single.tex"
GLOBAL_DOUBLE = BASE_DIR / "Overleaf_LaTeX/tabellen/aspen_luftzerlegung_global_check.tex"
GLOBAL_SINGLE = BASE_DIR / "Overleaf_LaTeX/tabellen/aspen_luftzerlegung_global_check_single.tex"
OUT_DIR = BASE_DIR / "Overleaf_LaTeX/bilder"
TAB_DIR = BASE_DIR / "Overleaf_LaTeX/tabellen"
WERTE_TEX = BASE_DIR / "Overleaf_LaTeX/werte.tex"
COLOR_SINGLE = "#55A868"
COLOR_DOUBLE = "#4C72B0"
PLOT_THEME = {
    "font.family": "serif",
    "mathtext.fontset": "stix",
    "axes.labelsize": 12,
    "xtick.labelsize": 11,
    "ytick.labelsize": 11,
    "legend.fontsize": 11,
}


def _apply_plot_theme(style: str = "seaborn-v0_8-whitegrid"):
    plt.style.use(style)
    plt.rcParams.update(PLOT_THEME)


def _style_axis(ax, grid_axis: str = "y"):
    ax.grid(axis=grid_axis, linestyle="--", alpha=0.35)
    # Apply decimal-comma formatting only to the likely numeric axis.
    # This keeps categorical axes (e.g., component names) unchanged.
    if grid_axis == "x":
        ax.xaxis.set_major_formatter(FuncFormatter(_tick_formatter_decimal_comma))
    elif grid_axis == "y":
        ax.yaxis.set_major_formatter(FuncFormatter(_tick_formatter_decimal_comma))
    else:
        ax.xaxis.set_major_formatter(FuncFormatter(_tick_formatter_decimal_comma))
        ax.yaxis.set_major_formatter(FuncFormatter(_tick_formatter_decimal_comma))
    for spine in ["top", "right"]:
        ax.spines[spine].set_visible(False)


def _style_bottom_legend(ax, ncol: int = 2):
    ax.legend(
        loc="upper center",
        bbox_to_anchor=(0.5, -0.12),
        ncol=ncol,
        frameon=True,
        fancybox=False,
        edgecolor="black",
    )


def _to_float(value: str):
    return _to_float_latex_number(value)


def _format_decimal_comma(value, decimals: int = 3, trim: bool = False):
    if value is None or not isinstance(value, (int, float)):
        return "-"
    x = float(value)
    text = f"{x:.{decimals}f}"
    if trim:
        text = text.rstrip("0").rstrip(".")
        if text in {"", "-0"}:
            text = "0"
    return text.replace(".", ",")


def _tick_formatter_decimal_comma(x, _pos):
    if not isinstance(x, (int, float)):
        return ""
    ax = abs(float(x))
    if ax >= 100:
        text = f"{x:.0f}"
    elif ax >= 1:
        text = f"{x:.2f}".rstrip("0").rstrip(".")
    else:
        text = f"{x:.4f}".rstrip("0").rstrip(".")
    if text in {"", "-0"}:
        text = "0"
    return text.replace(".", ",")


def _to_float_latex_number(value: str):
    if value is None:
        return None
    value = str(value)
    value = re.sub(r"\\textbf\{([^}]*)\}", r"\1", value)
    value = value.replace("$", "").replace("\\%", "").replace("%", "")
    value = value.replace("\\", "").replace("{", "").replace("}", "").strip()
    if not value or value == "-":
        return None

    # Threshold notation from tables, e.g. <1e-6: use 0.0 for plotting.
    if value.startswith("<"):
        return 0.0

    # German thousand separator format (e.g. 7.631.750 or -7.608)
    if re.match(r"^-?\d{1,3}(\.\d{3})+(,\d+)?$", value):
        value = value.replace(".", "").replace(",", ".")
        try:
            return float(value)
        except ValueError:
            return None

    # English thousand separator format (e.g. 7,631,750 or 7,631,750.25)
    if re.match(r"^-?\d{1,3}(,\d{3})+(\.\d+)?$", value):
        value = value.replace(",", "")
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

    # decimal comma and comma-separated integer fallback
    if "," in value and "." not in value:
        try:
            return float(value.replace(",", "."))
        except ValueError:
            pass
        try:
            return float(value.replace(",", ""))
        except ValueError:
            return None

    return None


def parse_component_table(tex_path: Path) -> pd.DataFrame:
    rows = []
    # Normalize old component names to their current canonical names so plots
    # remain correct even if .tex files still contain legacy names.
    name_map = {
        "MH": "MW",
        "RECO": "RC",
        "RECON": "RC",
        "TURB": "T",
    }
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
            # normalize legacy names
            if component in name_map:
                component = name_map[component]
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
    # Recompute y_D_k from parsed E_D values so shares sum to 1 per model
    total = df["E_D_W"].abs().sum()
    if total > 0:
        df["y_D_k"] = df["E_D_W"].abs() / total
    else:
        df["y_D_k"] = 0.0

    return df.sort_values("E_D_W", ascending=False).reset_index(drop=True)


def parse_component_ed_map(tex_path: Path) -> dict:
    rows = {}
    pattern = re.compile(r"^\s*([^&]+)&([^&]+)&([^&]+)&([^&]+)&([^&]+)&([^&]+)&([^&]+)(?:&([^\\]+))?\\\\")

    name_map = {
        "MH": "MW",
        "RECO": "RC",
        "RECON": "RC",
        "TURB": "T",
    }

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
            if comp in name_map:
                comp = name_map[comp]
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
            x_ar = _to_float(m.group(5))
            if x_n2 is None or x_o2 is None:
                continue

            rows.append({"Stream": stream, "x_N2": x_n2, "x_O2": x_o2, "x_AR": x_ar if x_ar is not None else 0.0})

    df = pd.DataFrame(rows)
    if df.empty:
        raise ValueError(f"Keine verwertbaren Molfraktionsdaten in {tex_path}")
    return df


def parse_stream_mass_flows(tex_path: Path) -> dict:
    rows = {}

    with tex_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("\\"):
                continue
            if line.startswith("Stream") or line.startswith("&"):
                continue

            parts = [part.strip() for part in line.replace("\\\\", "").split("&")]
            if len(parts) < 2:
                continue

            stream = parts[0]
            mass_flow = _to_float(parts[1])
            if stream and isinstance(mass_flow, (int, float)):
                rows[stream] = float(mass_flow)

    if not rows:
        raise ValueError(f"Keine verwertbaren Massenstromdaten in {tex_path}")
    return rows


def parse_stream_data_from_json(json_path: Path, stream_names: list[str]) -> dict:
    raise RuntimeError(
        "JSON input is disabled for result calculations. Use the LaTeX tables under Overleaf_LaTeX/tabellen/ as authoritative sources."
    )


def parse_stream_thermo_data(tex_path: Path) -> dict:
    """Return dict: stream -> {'m_dot': float, 'T': float, 'p_Pa': float}"""
    data = {}
    with tex_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("\\") or line.startswith("Stream") or line.startswith("&"):
                continue
            parts = [p.strip() for p in line.replace("\\\\", "").split("&")]
            if len(parts) < 5:
                continue
            stream = parts[0]
            m_dot = _to_float(parts[1])
            # parts[2] contains molar flow (mol/s) in the stream tables
            n_mol_s = _to_float(parts[2])
            T = _to_float(parts[3])
            p_Pa = _to_float(parts[4])
            if stream and m_dot is not None and T is not None and p_Pa is not None:
                data[stream] = {"m_dot": m_dot, "n_mol_s": n_mol_s, "T": T, "p_Pa": p_Pa}
    return data


def compute_yd_percent_from_ed_map(ed_map: dict, allowed_components: set[str] | None = None) -> dict:
    """Compute percent shares of E_D per component from an ed_map (component->E_D).

    Returns mapping component -> percent of total E_D (0..100).
    """
    e_map = {}
    for name, val in ed_map.items():
        if allowed_components is not None and name not in allowed_components:
            continue
        try:
            e_map[name] = abs(float(val))
        except Exception:
            continue

    total = sum(e_map.values())
    if total <= 0:
        return {k: 0.0 for k in e_map.keys()}
    return {k: (v / total) * 100.0 for k, v in e_map.items()}


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

    _apply_plot_theme()

    fig, ax_left = plt.subplots(figsize=(7.2, 5.4))
    ax_right = ax_left.twinx()

    categories = ["Stickstoff-Produktstrom", "Sauerstoffreststrom"]
    x = [0.0, 0.6]
    width = 0.12  # slight gap avoids visual seam between adjacent bars
    dx = 0.07

    # Colors requested to match existing style.
    color_single = COLOR_SINGLE
    color_double = COLOR_DOUBLE

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
                _format_decimal_comma(v, decimals=4, trim=False),
                ha="center",
                va="bottom",
                fontsize=9,
            )

    # Legend below the plot.
    handles = [b_single_o2[0], b_double_o2[0]]
    labels = ["Einkolonnen-Modell", "Doppelkolonnen-Modell"]
    ax_left.legend(
        handles,
        labels,
        loc="upper center",
        bbox_to_anchor=(0.5, -0.14),
        ncol=2,
        frameon=True,
        fancybox=False,
        edgecolor="black",
    )

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
        # move RC from heat transfer into the column block per user request
        heat_transfer = ["MW"]
        column_block = ["KOL", "D1", "RC"]
    else:
        comp_only = ["LK1", "ZK1", "LK2", "PK1"]
        gas_only = ["ZK2", "GW1", "GW2"]
        # move RC and RC2 from heat transfer into the column block per user request
        heat_transfer = ["MW"]
        column_block = ["KOLHP", "KOLLP", "D1", "D2", "D3", "RC", "RC2"]

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

    _apply_plot_theme()

    fig, ax = plt.subplots(figsize=(8.0, 5.8))

    c_single = COLOR_SINGLE
    c_double = COLOR_DOUBLE

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
    _style_axis(ax, grid_axis="y")

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
    product_stream = None

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
                m = re.search(r"\{(S[A-Z]*\d+)\}", parts[4])
                if m:
                    product_stream = m.group(1)
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
        r"$\dot{E}_{F,tot}$": total_input,
        r"$\dot{E}_{P,tot}$": product_total,
        r"$\dot{E}_{D,tot}$": E_dest,
        r"$\dot{E}_{L,tot}$": E_loss,
    }
    metrics_mw = {k: (v / 1e6 if isinstance(v, (int, float)) else None) for k, v in metrics_w.items()}
    return metrics_w, metrics_mw, product_stream


def compute_specific_metrics(metrics_w: dict, product_mass_flow: float) -> dict:
    if not isinstance(product_mass_flow, (int, float)) or product_mass_flow <= 0:
        raise ValueError("Produktmassenstrom muss positiv sein.")

    specific_metrics = {}
    for key, value in metrics_w.items():
        if isinstance(value, (int, float)):
            specific_metrics[key] = value / product_mass_flow / 1e3
        else:
            specific_metrics[key] = None
    return specific_metrics


def make_plot(df: pd.DataFrame, x_col: str, xlabel: str, out_path: Path, xlim=None):
    _apply_plot_theme()
    fig, ax = plt.subplots(figsize=(10, 7))

    color = COLOR_SINGLE if "single" in out_path.stem.lower() else COLOR_DOUBLE
    # For visibility: do not modify numeric values, but apply a tiny visual
    # floor for extremely small non-zero shares so they are still visible in
    # the plot (e.g. 0.00something). This floor is only applied to the
    # displayed bar widths, labels keep the original unmodified values.
    display_vals = df[x_col].astype(float).copy()
    if x_col == "y_D_k" or x_col.lower().startswith("y_"):
        # floor relative to dynamic range but absolute minimum to avoid invisibility
        maxv = float(display_vals.abs().max() if not display_vals.empty else 0.0)
        floor = max(1e-6, maxv * 1e-5)
        # apply floor only to non-zero but sub-threshold values
        small_mask = (display_vals != 0.0) & (display_vals.abs() < floor)
        display_vals[small_mask] = display_vals[small_mask].apply(lambda v: floor if v > 0 else -floor)
    ax.barh(df["Component"], display_vals, color=color)
    ax.invert_yaxis()

    ax.set_xlabel(xlabel)
    ax.set_ylabel("Component")
    if xlim is not None:
        ax.set_xlim(*xlim)
    _style_axis(ax, grid_axis="x")

    fig.tight_layout()
    fig.savefig(out_path, dpi=300)
    plt.close(fig)


def _yd_axis_limit(df: pd.DataFrame, col: str = "y_D_k"):
    values = pd.to_numeric(df[col], errors="coerce").dropna()
    if values.empty:
        return (0, 1)

    share_le_half = (values <= 0.5).mean()
    # If most components are very small, use a tighter axis to enhance visibility.
    if share_le_half >= 0.8:
        return (0, 0.3)

    # Compute a high-percentile upper bound and cap it at 0.3 to show more bars.
    upper = float(values.quantile(0.95)) * 1.1
    # Allow very small upper if data warrants, but cap maximum to 0.3
    upper = max(upper, 0.01)
    upper = min(upper, 0.3)
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
            f"{_format_decimal_comma(val, decimals=3, trim=False)} {unit}",
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
            f"{_format_decimal_comma(width, decimals=3, trim=False)} {unit}",
            va="center",
            ha="left",
            fontsize=8,
        )


def _format_percent_de(value, digits: int = 4):
    """Format percent value for DE/LaTeX output.

    Do NOT coerce very small values to exactly zero here — keep precision so
    that tiny non-zero shares remain visible in textual outputs. Visual
    plotting may still apply a minimal floor for visibility only.
    """
    if value is None:
        return "-"
    x = float(value)
    # Normalize tiny numerical noise to exact 0 only when it's numerically zero.
    if x == 0.0:
        return f"{0:.{digits}f}".replace(".", ",")
    return f"{x:.{digits}f}".replace(".", ",")


def parse_component_yd_percent_from_json(json_path: Path, allowed_components: set[str] | None = None) -> dict[str, float]:
    raise RuntimeError(
        "JSON input is disabled for result calculations. Use the LaTeX tables under Overleaf_LaTeX/tabellen/ as authoritative sources."
    )


def _build_yd_large_vs_small_latex_table(
    yd_double_large: dict[str, float],
    yd_double_small: dict[str, float],
    yd_single_large: dict[str, float],
    yd_single_small: dict[str, float],
) -> str:
    def _rows_for_model(large_map: dict[str, float], small_map: dict[str, float], model_label: str):
        components = sorted(set(large_map.keys()) | set(small_map.keys()))

        rows = []
        for comp in components:
            y_large = large_map.get(comp)
            y_small = small_map.get(comp)
            diff = None
            if isinstance(y_large, (int, float)) and isinstance(y_small, (int, float)):
                diff = y_small - y_large

            rows.append(
                " & ".join(
                    [
                        model_label,
                        comp,
                        _format_percent_de(y_large),
                        _format_percent_de(y_small),
                        _format_percent_de(diff),
                    ]
                )
                + r" \\\\" 
            )
        return rows

    rows = []
    rows.extend(_rows_for_model(yd_double_large, yd_double_small, "Doppel"))
    rows.append(r"\hline")
    rows.extend(_rows_for_model(yd_single_large, yd_single_small, "Single"))

    lines = [
        r"\begin{longtable}{llrrr}",
        r"\caption{Vergleich der Exergievernichtungsanteile $y_D$ zwischen grosser und kleiner Variante} \\\\ ",
        r"\hline",
        r"Modell & Komponente & $y_D$ (Gross) [\%] & $y_D$ (Klein) [\%] & Differenz [Prozentpunkte] \\\\ ",
        r"\hline",
        *rows,
        r"\hline",
        r"\end{longtable}",
    ]
    return "\n".join(lines)


def compute_n2_recovery(streams_single: dict, streams_double: dict) -> dict:
    """Compute N2 recovery metrics for both models.

    Returns dict with keys:
      single_eta_pct   – η_N2 Single [%]:  N2 in product / N2 in feed × 100
      double_eta_pct   – η_N2 Double [%]
      single_ratio     – mol product / mol feed air (Single)
      double_ratio     – mol product / mol feed air (Double)
    """
    def _recovery(feed: dict, product: dict):
        n_feed    = feed["n_mol_s"]
        n_product = product["n_mol_s"]
        x_n2_feed    = feed["x_N2"]
        x_n2_product = product["x_N2"]
        n2_in_feed    = n_feed    * x_n2_feed
        n2_in_product = n_product * x_n2_product
        eta_pct = n2_in_product / n2_in_feed * 100.0
        ratio   = n_product / n_feed
        return eta_pct, ratio

    eta_s, ratio_s = _recovery(streams_single["S1"], streams_single["S24"])
    eta_d, ratio_d = _recovery(streams_double["S1"], streams_double["S32"])

    return {
        "single_eta_pct": eta_s,
        "double_eta_pct": eta_d,
        "single_ratio":   ratio_s,
        "double_ratio":   ratio_d,
    }


def _build_n2_recovery_latex_table(recovery: dict) -> str:
    """Build a small LaTeX table with N2 recovery results."""
    def fc(x, d=4):
        return _format_decimal_comma(x, d)

    rows = [
        r"Modell & $\eta_{N_2}$ [\%] & $\dot{n}_{\text{Produkt}} / \dot{n}_{\text{Luft}}$ [-] \\\\",
        r"\hline",
        f"Singlekolonne & {fc(recovery['single_eta_pct'], 2)} & {fc(recovery['single_ratio'], 6)} \\\\",
        f"Doppelkolonne & {fc(recovery['double_eta_pct'], 2)} & {fc(recovery['double_ratio'], 6)} \\\\",
    ]
    lines = [
        r"\begin{tabular}{lrr}",
        r"\hline",
        *rows,
        r"\hline",
        r"\end{tabular}",
    ]
    return "\n".join(lines)


def _build_werte_tex(recovery: dict, streams_single: dict, streams_double: dict) -> str:
    """Build central LaTeX value file with simulation results as \newcommand macros."""

    def _fmt_value(value: float, digits: int = 10) -> str:
        if value is None:
            return "0"
        text = f"{float(value):.{digits}f}".rstrip("0").rstrip(".")
        return text if text else "0"

    single_product = streams_single.get("S24", {})
    double_product = streams_double.get("S32", {})

    single_o2_ppm = float(single_product.get("x_O2", 0.0)) * 1e6
    single_ar_ppm = float(single_product.get("x_AR", 0.0)) * 1e6
    double_o2_ppm = float(double_product.get("x_O2", 0.0)) * 1e6
    double_ar_ppm = float(double_product.get("x_AR", 0.0)) * 1e6

    lines = [
        r"% werte.tex",
        r"% Zentrale Sammlung wichtiger Ergebniswerte aus der Simulation.",
        r"% Diese Datei wird automatisch von tools/plot_exergy_results.py erzeugt.",
        r"% Konventionen:",
        r"% - Alle Werte als \newcommand mit Prefix val",
        r"% - Nur Zahlenwerte im Makro, Einheit als Kommentar",
        "",
        r"% ------------------------------------------------------------",
        r"% Rueckgewinnung",
        r"% ------------------------------------------------------------",
        f"\\newcommand{{\\valSingleRueckgewinnungN2}}{{{_fmt_value(recovery.get('single_eta_pct'), 8)}}} % [%]",
        f"\\newcommand{{\\valDoppelRueckgewinnungN2}}{{{_fmt_value(recovery.get('double_eta_pct'), 8)}}} % [%]",
        f"\\newcommand{{\\valSingleN2ProduktZuLuft}}{{{_fmt_value(recovery.get('single_ratio'), 10)}}} % [-]",
        f"\\newcommand{{\\valDoppelN2ProduktZuLuft}}{{{_fmt_value(recovery.get('double_ratio'), 10)}}} % [-]",
        "",
        r"% ------------------------------------------------------------",
        r"% Druecke",
        r"% ------------------------------------------------------------",
        r"% (Platzhalter fuer zukuenftige Werte)",
        "",
        r"% ------------------------------------------------------------",
        r"% Massenstroeme",
        r"% ------------------------------------------------------------",
        r"% (Platzhalter fuer zukuenftige Werte)",
        "",
        r"% ------------------------------------------------------------",
        r"% Temperaturen",
        r"% ------------------------------------------------------------",
        r"% (Platzhalter fuer zukuenftige Werte)",
        "",
        r"% ------------------------------------------------------------",
        r"% Zusammensetzung N2-Produktstrom (ppm)",
        r"% Basis: Single S24, Doppel S32",
        r"% ------------------------------------------------------------",
        f"\\newcommand{{\\valSingleN2ProduktO2Ppm}}{{{_fmt_value(single_o2_ppm, 10)}}} % [ppm]",
        f"\\newcommand{{\\valSingleN2ProduktArPpm}}{{{_fmt_value(single_ar_ppm, 10)}}} % [ppm]",
        f"\\newcommand{{\\valDoppelN2ProduktO2Ppm}}{{{_fmt_value(double_o2_ppm, 10)}}} % [ppm]",
        f"\\newcommand{{\\valDoppelN2ProduktArPpm}}{{{_fmt_value(double_ar_ppm, 10)}}} % [ppm]",
    ]

    return "\n".join(lines) + "\n"


def _build_stream_comparison_latex_table(
    streams_single: dict,
    streams_double: dict,
) -> str:
    """Build LaTeX table comparing key process streams for Single and Double column models."""

    def fmt_x(x_n2: float, x_o2: float, x_ar: float) -> str:
        return (
            f"{_format_decimal_comma(x_n2, 6)} / "
            f"{_format_decimal_comma(x_o2, 6)} / "
            f"{_format_decimal_comma(x_ar, 6)}"
        )

    def fmt_p(p_Pa: float) -> str:
        return _format_decimal_comma(p_Pa / 1e5, 2)

    def fmt_T(T: float) -> str:
        return _format_decimal_comma(T, 2)

    def fmt_m(m: float) -> str:
        return _format_decimal_comma(m, 2)

    # (single_stream_key, double_stream_key, row_label)
    stream_defs = [
        ("S1",  "S1",  "Luft (S1)"),
        ("S24", "S32", r"N$_2$-Produkt (S24 / S32)"),
        ("S21", "S28", "Reststrom (S21 / S28)"),
    ]

    rows = []
    for s_key, d_key, label in stream_defs:
        s = streams_single.get(s_key, {})
        d = streams_double.get(d_key, {})
        m_s = fmt_m(s.get("m_dot"))
        m_d = fmt_m(d.get("m_dot"))
        p_val = fmt_p(s.get("p_Pa", 0.0))
        T_s = fmt_T(s.get("T", 0.0))
        T_d = fmt_T(d.get("T", 0.0))
        rows.append(
            f"{label} & {m_s} & {m_d} & {fmt_x(s.get('x_N2', 0.0), s.get('x_O2', 0.0), s.get('x_AR', 0.0))} "
            f"& {fmt_x(d.get('x_N2', 0.0), d.get('x_O2', 0.0), d.get('x_AR', 0.0))} & {p_val} & {T_s} & {T_d} \\\\" 
        )

    lines = [
        r"\begin{longtable}{lrrrrrrrr}",
        r"\caption{Gegenüberstellung der Ergebnisse der Prozesssimulation für das Singlekolonnenmodell und das Doppelkolonnenmodell anhand ausgewählter Stoffstromgrößen, Zusammensetzungen und thermodynamischer Zustandsparameter.} \\",
        r"\hline",
        (
            r"Stoffstrom & $\dot{m}_{\text{Single}}$ [kg/s] & $\dot{m}_{\text{Doppel}}$ [kg/s]"
            r" & $x_{\text{N}_2/\text{O}_2/\text{Ar},\,\text{Single}}$ [-] & $x_{\text{N}_2/\text{O}_2/\text{Ar},\,\text{Doppel}}$ [-]"
            r" & $p$ [bar] & $T_{\text{Single}}$ [K] & $T_{\text{Doppel}}$ [K] \\"
        ),
        r"\hline",
        *rows,
        r"\hline",
        r"\end{longtable}",
    ]
    return "\n".join(lines)


def plot_grouped_system_metrics(metrics_double_mw, metrics_single_mw, out_path: Path):
    categories = [r"$\dot{E}_{F,tot}$", r"$\dot{E}_{P,tot}$", r"$\dot{E}_{D,tot}$", r"$\dot{E}_{L,tot}$"]
    vals_double = [metrics_double_mw.get(c) for c in categories]
    vals_single = [metrics_single_mw.get(c) for c in categories]

    _apply_plot_theme()
    fig, ax = plt.subplots(figsize=(10, 6))
    x = range(len(categories))
    width = 0.38

    bars_double = ax.bar([i - width / 2 for i in x], vals_double, width=width, label="Doppelkolonne", color=COLOR_DOUBLE)
    bars_single = ax.bar([i + width / 2 for i in x], vals_single, width=width, label="Singlekolonne", color=COLOR_SINGLE)

    ax.set_xticks(list(x))
    ax.set_xticklabels(categories)
    ax.set_ylabel("Exergiestrom [MW]")
    _style_axis(ax, grid_axis="y")
    _style_bottom_legend(ax)

    _annotate_vertical_bars(ax, bars_double, vals_double, unit="MW")
    _annotate_vertical_bars(ax, bars_single, vals_single, unit="MW")

    fig.subplots_adjust(left=0.10, right=0.98, bottom=0.20, top=0.96)
    fig.savefig(out_path, dpi=300)
    plt.close(fig)


def plot_grouped_specific_system_metrics(metrics_double_spec, metrics_single_spec, out_path: Path):
    # Lookup keys correspond to the computed specific metrics (capital E labels).
    lookup_keys = [r"$\dot{E}_{F,tot}$", r"$\dot{E}_{P,tot}$", r"$\dot{E}_{D,tot}$", r"$\dot{E}_{L,tot}$"]
    # Display labels should show lowercase e as requested.
    display_labels = [r"$\dot{e}_{f,tot}$", r"$\dot{e}_{p,tot}$", r"$\dot{e}_{d,tot}$", r"$\dot{e}_{l,tot}$"]
    vals_double = [metrics_double_spec.get(k) for k in lookup_keys]
    vals_single = [metrics_single_spec.get(k) for k in lookup_keys]

    _apply_plot_theme()
    fig, ax = plt.subplots(figsize=(10, 6))
    x = range(len(lookup_keys))
    width = 0.38

    bars_double = ax.bar([i - width / 2 for i in x], vals_double, width=width, label="Doppelkolonne", color=COLOR_DOUBLE)
    bars_single = ax.bar([i + width / 2 for i in x], vals_single, width=width, label="Singlekolonne", color=COLOR_SINGLE)

    ax.set_xticks(list(x))
    ax.set_xticklabels(display_labels)
    ax.set_ylabel(r"Spezifischer Exergiestrom [kJ/kg]")
    _style_axis(ax, grid_axis="y")
    _style_bottom_legend(ax)

    _annotate_vertical_bars(ax, bars_double, vals_double, unit="kJ/kg")
    _annotate_vertical_bars(ax, bars_single, vals_single, unit="kJ/kg")

    fig.subplots_adjust(left=0.10, right=0.98, bottom=0.20, top=0.96)
    fig.savefig(out_path, dpi=300)
    plt.close(fig)


def plot_component_pareto_comparison(df_double: pd.DataFrame, df_single: pd.DataFrame, out_path: Path):
    _apply_plot_theme()
    fig, axes = plt.subplots(2, 1, figsize=(11, 12), sharex=False)

    bars_d = axes[0].barh(df_double["Component"], df_double["E_D_MW"], color=COLOR_DOUBLE)
    axes[0].invert_yaxis()
    axes[0].set_xlabel(r"$\dot{E}_D$ [MW]")
    axes[0].set_ylabel("Doppelkolonne")
    _style_axis(axes[0], grid_axis="x")
    _annotate_horizontal_bars(axes[0], bars_d, unit="MW")

    bars_s = axes[1].barh(df_single["Component"], df_single["E_D_MW"], color=COLOR_SINGLE)
    axes[1].invert_yaxis()
    axes[1].set_xlabel(r"$\dot{E}_D$ [MW]")
    axes[1].set_ylabel("Singlekolonne")
    _style_axis(axes[1], grid_axis="x")
    _annotate_horizontal_bars(axes[1], bars_s, unit="MW")

    fig.subplots_adjust(left=0.16, right=0.97, bottom=0.08, top=0.98, hspace=0.25)
    fig.savefig(out_path, dpi=300)
    plt.close(fig)


def plot_absolute_ed_large_vs_small(df_large: pd.DataFrame, df_small: pd.DataFrame, model_label: str, out_path: Path):
    _apply_plot_theme()
    fig, axes = plt.subplots(2, 1, figsize=(11, 12), sharex=False)

    color = COLOR_DOUBLE if "doppel" in model_label.lower() else COLOR_SINGLE

    bars_large = axes[0].barh(df_large["Component"], df_large["E_D_MW"], color=color)
    axes[0].invert_yaxis()
    axes[0].set_xlabel(r"$\dot{E}_D$ [MW]")
    axes[0].set_ylabel(f"{model_label} groß")
    _style_axis(axes[0], grid_axis="x")
    _annotate_horizontal_bars(axes[0], bars_large, unit="MW")

    bars_small = axes[1].barh(df_small["Component"], df_small["E_D_MW"], color=color)
    axes[1].invert_yaxis()
    axes[1].set_xlabel(r"$\dot{E}_D$ [MW]")
    axes[1].set_ylabel(f"{model_label} klein")
    _style_axis(axes[1], grid_axis="x")
    _annotate_horizontal_bars(axes[1], bars_small, unit="MW")

    fig.subplots_adjust(left=0.16, right=0.97, bottom=0.08, top=0.98, hspace=0.25)
    fig.savefig(out_path, dpi=300)
    plt.close(fig)


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs(TAB_DIR, exist_ok=True)

    df_double = parse_component_table(TABLE_DOUBLE)
    df_single = parse_component_table(TABLE_SINGLE)
    # Recompute y_D_k from the component E_D totals in the LaTeX tables
    # User request: y_D_k = E_D_component / sum(|E_D_component|) per model
    def _recompute_yd(df: pd.DataFrame) -> pd.DataFrame:
        if "E_D_W" not in df.columns:
            return df
        total = df["E_D_W"].abs().sum()
        if total <= 0:
            df["y_D_k"] = 0.0
        else:
            df["y_D_k"] = df["E_D_W"].abs() / total
        return df

    df_double = _recompute_yd(df_double)
    df_single = _recompute_yd(df_single)
    ed_map_double = parse_component_ed_map(TABLE_DOUBLE)
    ed_map_single = parse_component_ed_map(TABLE_SINGLE)
    df_mol_double = parse_molfrac_table(MOLFRAC_DOUBLE)
    df_mol_single = parse_molfrac_table(MOLFRAC_SINGLE)
    stream_mdot_double = parse_stream_mass_flows(STREAMS_DOUBLE)
    stream_mdot_single = parse_stream_mass_flows(STREAMS_SINGLE)
    metrics_double_w, metrics_double_mw, product_stream_double = parse_global_master_table(GLOBAL_DOUBLE)
    metrics_single_w, metrics_single_mw, product_stream_single = parse_global_master_table(GLOBAL_SINGLE)

    if product_stream_double not in stream_mdot_double:
        raise ValueError(f"Produktstrom {product_stream_double} nicht in {STREAMS_DOUBLE} gefunden.")
    if product_stream_single not in stream_mdot_single:
        raise ValueError(f"Produktstrom {product_stream_single} nicht in {STREAMS_SINGLE} gefunden.")

    metrics_double_spec = compute_specific_metrics(metrics_double_w, stream_mdot_double[product_stream_double])
    metrics_single_spec = compute_specific_metrics(metrics_single_w, stream_mdot_single[product_stream_single])

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

    plot_grouped_specific_system_metrics(
        metrics_double_spec,
        metrics_single_spec,
        out_path=OUT_DIR / "vergleich_global_kennzahlen_grouped_spezifisch.png",
    )

    plot_component_pareto_comparison(
        df_double,
        df_single,
        out_path=OUT_DIR / "vergleich_component_pareto_ED.png",
    )

    # Gross/Klein comparison plots removed per user request.

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

    # Gross/Klein y_D comparison removed per user request.

    # Build stream thermo + molfraction payloads from LaTeX tables (not JSON)
    thermo_tex_single = parse_stream_thermo_data(STREAMS_SINGLE)
    thermo_tex_double = parse_stream_thermo_data(STREAMS_DOUBLE)

    # mol fraction tables provide x_N2, x_O2, x_AR
    mol_single = parse_molfrac_table(MOLFRAC_SINGLE).set_index("Stream").to_dict(orient="index")
    mol_double = parse_molfrac_table(MOLFRAC_DOUBLE).set_index("Stream").to_dict(orient="index")

    def _combine_streams(thermo_map, mol_map, keys: list[str]):
        out = {}
        for k in keys:
            t = thermo_map.get(k, {})
            m = mol_map.get(k, {})
            out[k] = {
                "m_dot": t.get("m_dot"),
                "n_mol_s": t.get("n_mol_s"),
                "T": t.get("T"),
                "p_Pa": t.get("p_Pa"),
                "x_N2": m.get("x_N2", 0.0),
                "x_O2": m.get("x_O2", 0.0),
                "x_AR": m.get("x_AR", 0.0),
            }
        return out

    thermo_single = _combine_streams(thermo_tex_single, mol_single, ["S1", "S21", "S24"])
    thermo_double = _combine_streams(thermo_tex_double, mol_double, ["S1", "S28", "S32"])

    recovery = compute_n2_recovery(thermo_single, thermo_double)
    print("\n=== N2-Rueckgewinnung ===")
    print(f"  Single  eta_N2 = {recovery['single_eta_pct']:.4f} %   ratio = {recovery['single_ratio']:.6f} mol/mol")
    print(f"  Doppel  eta_N2 = {recovery['double_eta_pct']:.4f} %   ratio = {recovery['double_ratio']:.6f} mol/mol")
    recovery_table = _build_n2_recovery_latex_table(recovery)
    recovery_out = TAB_DIR / "aspen_luftzerlegung_n2_recovery.tex"
    with recovery_out.open("w", encoding="utf-8") as f:
        f.write(recovery_table)
    print("N2-Rueckgewinnung gespeichert:", recovery_out)

    stream_comp_table = _build_stream_comparison_latex_table(
        thermo_single,
        thermo_double,
    )
    stream_comp_out = TAB_DIR / "aspen_luftzerlegung_streams_vergleich.tex"
    with stream_comp_out.open("w", encoding="utf-8") as f:
        f.write(stream_comp_table)

    werte_tex = _build_werte_tex(recovery, thermo_single, thermo_double)
    with WERTE_TEX.open("w", encoding="utf-8") as f:
        f.write(werte_tex)
    print("Werte-Datei gespeichert:", WERTE_TEX)

    print("Plots gespeichert in:")
    print(OUT_DIR)


if __name__ == "__main__":
    main()
