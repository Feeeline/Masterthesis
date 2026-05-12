import os
import math
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from matplotlib.colors import to_rgb, to_hex

# use project theme colors
from tools.plot_exergy_results import COLOR_SINGLE, COLOR_DOUBLE


def create_dataframe():
    blocks = [
        "Luftverdichtung",
        "Gasaufbereitung",
        "Hauptwärmeübertrager",
        "Rektifikation",
        "Rest",
    ]

    data = []

    # Einzel klein
    ek = [2182152, 389341, 375332, 1225871, 431846]
    for b, v in zip(blocks, ek):
        data.append(("Einzel klein", "Einzelkolonnenmodell", "klein", b, v))

    # Einzel groß
    eg = [3881958, 1123498, 1384486, 6093183, 899251]
    for b, v in zip(blocks, eg):
        data.append(("Einzel groß", "Einzelkolonnenmodell", "groß", b, v))

    # Doppel klein
    dk = [1817067, 488984, 827218, 2322332, 649479]
    for b, v in zip(blocks, dk):
        data.append(("Doppel klein", "Doppelkolonnenmodell", "klein", b, v))

    # Doppel groß
    dg = [3223332, 2450972, 16665085, 8280687, 1201459]
    for b, v in zip(blocks, dg):
        data.append(("Doppel groß", "Doppelkolonnenmodell", "groß", b, v))

    df = pd.DataFrame(
        data, columns=["variant", "model_type", "size", "block", "CBM_EUR2026"]
    )

    # Compute share_percent per variant
    df["share_percent"] = df.groupby("variant", group_keys=False)["CBM_EUR2026"].apply(
        lambda x: x / x.sum() * 100
    )

    return df


def verify_sums(df):
    expected = {
        "Einzel klein": 4604542,
        "Einzel groß": 13382376,
        "Doppel klein": 6105080,
        "Doppel groß": 31821535,
    }

    print("Prüfung der Summen je Variante:")
    for variant, exp in expected.items():
        s = int(df.loc[df.variant == variant, "CBM_EUR2026"].sum())
        ok = "OK" if s == exp else "FEHLER"
        print(f"- {variant}: summe = {s:,}  (erwartet: {exp:,}) --> {ok}")


def plot_pies(df, out_pdf="kostenverteilung_bare_module_pie.pdf", out_png="kostenverteilung_bare_module_pie.png"):
    # Plot settings
    plt.rcParams.update({
        "font.family": "serif",
        "font.size": 12,
        "axes.titlesize": 12,
        "legend.fontsize": 10,
    })

    variants = ["Einzel klein", "Einzel groß", "Doppel klein", "Doppel groß"]
    titles = [
        "(a) Einkolonnenmodell klein",
        "(b) Einkolonnenmodell groß",
        "(c) Doppelkolonnenmodell klein",
        "(d) Doppelkolonnenmodell groß",
    ]

    blocks = [
        "Luftverdichtung",
        "Gasaufbereitung",
        "Hauptwärmeübertrager",
        "Rektifikation",
        "Rest",
    ]

    hatches = ["", "///", "...", "xx", "\\\\"]

    # generate 5 shades while preserving the original hue by varying luminance (HLS)
    import colorsys

    def make_shades_hls(hex_color, n=5, delta_l=0.22):
        """Make n shades that are equal or darker than the base color (avoid brighter tones).

        This preserves the hue and saturation but reduces luminance from the base
        downwards so resulting shades are never brighter (greller) than the original.
        """
        r, g, b = to_rgb(hex_color)
        h, l, s = colorsys.rgb_to_hls(r, g, b)
        # produce luminance values from base (l) down to l - delta_l (clamped)
        low = max(0.05, l - delta_l)
        high = l
        ls = np.linspace(high, low, n)
        shades = []
        for lv in ls:
            rr, gg, bb = colorsys.hls_to_rgb(h, float(lv), s)
            shades.append(to_hex((rr, gg, bb)))
        # ensure one shade exactly matches the original hex color (closest to base)
        idx = 0  # high is at index 0 in our linspace
        shades[idx] = hex_color
        return shades

    greens = make_shades_hls(COLOR_SINGLE, n=5)
    blues = make_shades_hls(COLOR_DOUBLE, n=5)

    fig, axes = plt.subplots(2, 2, figsize=(10, 9.5))
    axes = axes.flatten()

    for ax, variant, title in zip(axes, variants, titles):
        sub = df[df.variant == variant]
        values = sub["CBM_EUR2026"].values
        shares = sub["share_percent"].values

        # choose colors according to model type
        if "Einzel" in variant:
            colors = greens
        else:
            colors = blues

        wedges, texts = ax.pie(
            values,
            colors=colors,
            startangle=90,
            wedgeprops={"linewidth": 0.6, "edgecolor": "k"},
        )

        # apply hatches and slightly darker edge
        for i, w in enumerate(wedges):
            w.set_hatch(hatches[i])

        # place percentage labels outside with connecting lines
        for i, (w, pct) in enumerate(zip(wedges, shares)):
            theta1, theta2 = w.theta1, w.theta2
            mid = 0.5 * (theta1 + theta2)
            x = math.cos(math.radians(mid))
            y = math.sin(math.radians(mid))

            # point on wedge (slightly outside the wedge to avoid overlap)
            x0 = 0.9 * math.cos(math.radians(mid))
            y0 = 0.9 * math.sin(math.radians(mid))
            # text position (further outside)
            xtext = 1.25 * math.cos(math.radians(mid))
            ytext = 1.25 * math.sin(math.radians(mid))

            txt = f"{pct:.1f}%"
            ax.annotate(
                txt,
                xy=(x0, y0),
                xytext=(xtext, ytext),
                ha="center",
                va="center",
                fontsize=10,
                arrowprops={"arrowstyle": "-", "lw": 0.6, "connectionstyle": "arc3,rad=0.2"},
            )

        # give extra padding so percentage labels do not overlap the title
        ax.set_title(title, pad=26)
        ax.axis("equal")

    # legend: show function blocks with their hatch only (no color fill)
    legend_patches = []
    for i, b in enumerate(blocks):
        legend_patches.append(
            Patch(facecolor="white", hatch=hatches[i], edgecolor="k", label=b)
        )

    # place legend below the subplots
    fig.legend(handles=legend_patches, loc="lower center", ncol=5)

    # increase vertical spacing between the two rows so titles don't overlap
    fig.subplots_adjust(bottom=0.18, top=0.92, hspace=0.5)

    # Save outputs to Overleaf LaTeX bilder folder
    out_dir = r"C:\Users\Felin\Documents\Masterthesis\Simulation_Code\GIT\Overleaf_LaTeX\bilder"
    os.makedirs(out_dir, exist_ok=True)
    pdf_path = os.path.join(out_dir, out_pdf)
    png_path = os.path.join(out_dir, out_png)
    fig.savefig(pdf_path, bbox_inches="tight")
    fig.savefig(png_path, dpi=300, bbox_inches="tight")

    print(f"Saved PDF: {os.path.abspath(pdf_path)}")
    print(f"Saved PNG: {os.path.abspath(png_path)}")


def create_trr_dataframe():
    data = [
        ("Einkolonnenmodell klein", 1076067, 556029, 5063682, 6695778),
        ("Einkolonnenmodell groß", 3127420, 1616011, 17325345, 22068776),
        ("Doppelkolonnenmodell klein", 1426738, 737229, 3831662, 5995630),
        ("Doppelkolonnenmodell groß", 7436595, 3842663, 13109480, 24388739),
    ]
    df = pd.DataFrame(data, columns=["variant", "CC_L", "OM_L", "EC_L", "TRR_L"])

    # convert to Mio EUR/a
    df["CC_L_Mio"] = df["CC_L"] / 1e6
    df["OM_L_Mio"] = df["OM_L"] / 1e6
    df["EC_L_Mio"] = df["EC_L"] / 1e6
    df["TRR_L_Mio"] = df["TRR_L"] / 1e6

    return df


def plot_trr_zusammensetzung(df, out_pdf="trr_zusammensetzung.pdf", out_png="trr_zusammensetzung.png"):
    # plotting parameters
    plt.rcParams.update({
        "font.family": "serif",
        "mathtext.fontset": "stix",
        "font.size": 11,
    })

    variants = ["Einkolonnenmodell klein", "Einkolonnenmodell groß", "Doppelkolonnenmodell klein", "Doppelkolonnenmodell groß"]
    df = df.set_index("variant").loc[variants]

    cc = df["CC_L_Mio"].values
    om = df["OM_L_Mio"].values
    ec = df["EC_L_Mio"].values
    trr = df["TRR_L_Mio"].values

    x = np.arange(len(variants))

    cc_color = "#4C6A92"
    om_color = "#E69F00"
    ec_color = "#2CA02C"
    # model colors: Einkolonnenmodell green, Doppelkolonnenmodell blue
    eink_color = COLOR_SINGLE  # green
    doppel_color = COLOR_DOUBLE  # blue

    # hatches for blocks CC, OM, EC (OM dotted, denser)
    block_hatches = ["", "....", "xx"]

    fig, ax = plt.subplots(figsize=(7.5, 4.8))

    # draw stacked bars per variant with model color; overlay hatch-only bars on top for visibility
    for i, variant in enumerate(variants):
        model_color = eink_color if "Einkolonnenmodell" in variant or "Einzel" in variant else doppel_color
        # draw filled bars (no edge) at lower z-order
        bottom = 0.0
        ax.bar(i, cc[i], bottom=bottom, color=model_color, edgecolor="none", zorder=2)
        bottom += cc[i]
        ax.bar(i, om[i], bottom=bottom, color=model_color, edgecolor="none", zorder=2)
        bottom += om[i]
        ax.bar(i, ec[i], bottom=bottom, color=model_color, edgecolor="none", zorder=2)

        # overlay hatch-only bars (transparent fill) with black edges on higher z-order
        bottom2 = 0.0
        ax.bar(i, cc[i], bottom=bottom2, facecolor="none", hatch=block_hatches[0], edgecolor="k", linewidth=0.6, zorder=3)
        bottom2 += cc[i]
        ax.bar(i, om[i], bottom=bottom2, facecolor="none", hatch=block_hatches[1], edgecolor="k", linewidth=0.6, zorder=3)
        bottom2 += om[i]
        ax.bar(i, ec[i], bottom=bottom2, facecolor="none", hatch=block_hatches[2], edgecolor="k", linewidth=0.6, zorder=3)

    # y-axis label and title
    ax.set_ylabel("Jahreskosten in Mio. EUR/a")
        # No title; user will add in LaTeX

    # x ticks: variant names rotated
    ax.set_xticks(x)
    ax.set_xticklabels(variants, rotation=25, ha="right")

    # horizontal grid only
    ax.yaxis.grid(True, linestyle="--", linewidth=0.6, color="#cccccc", zorder=0)
    ax.xaxis.grid(False)

    # remove top and right spines
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    # legend: show model colors and block hatches separately
    model_patches = [
        Patch(facecolor=eink_color, edgecolor="k", label="Einkolonnenmodell"),
        Patch(facecolor=doppel_color, edgecolor="k", label="Doppelkolonnenmodell"),
    ]
    block_patches = [
        Patch(facecolor="white", hatch=block_hatches[0], edgecolor="k", label="Kapitalgebundene Kosten $CC_L$"),
        Patch(facecolor="white", hatch=block_hatches[1], edgecolor="k", label="Betriebs- und Wartungskosten $OM_L$"),
        Patch(facecolor="white", hatch=block_hatches[2], edgecolor="k", label="Energiekosten $EC_L$"),
    ]

    # place model legend to the right and block legend below it
    leg1 = ax.legend(handles=model_patches, loc="upper left", bbox_to_anchor=(1.02, 1), frameon=False)
    ax.add_artist(leg1)
    ax.legend(handles=block_patches, loc="upper left", bbox_to_anchor=(1.02, 0.6), frameon=False)

    # set y limit to leave room for labels
    ymax = trr.max() * 1.12
    ax.set_ylim(0, ymax)

    # annotate TRR above bars
    for xi, yi in zip(x, trr):
        ax.text(xi, yi + ymax * 0.01, f"{yi:.1f}", ha="center", va="bottom", fontsize=10)

    fig.tight_layout()

    # adjust to make room for legend on the right
    fig.subplots_adjust(right=0.78)

    out_dir = r"C:\Users\Felin\Documents\Masterthesis\Simulation_Code\GIT\Overleaf_LaTeX\bilder"
    os.makedirs(out_dir, exist_ok=True)
    pdf_path = os.path.join(out_dir, out_pdf)
    png_path = os.path.join(out_dir, out_png)
    fig.savefig(pdf_path, bbox_inches="tight")
    fig.savefig(png_path, dpi=300, bbox_inches="tight")

    print(f"Saved TRR PDF: {os.path.abspath(pdf_path)}")
    print(f"Saved TRR PNG: {os.path.abspath(png_path)}")


def create_n2_dataframe():
    """Create DataFrame with raw specific nitrogen costs (EUR/t_N2) and convert to EUR/kg_N2."""
    data = [
        ("Einzel klein", "Einzelkolonnenmodell", 50.00),
        ("Einzel groß", "Einzelkolonnenmodell", 48.17),
        ("Doppel klein", "Doppelkolonnenmodell", 44.77),
        ("Doppel groß", "Doppelkolonnenmodell", 53.23),
    ]

    df = pd.DataFrame(data, columns=["variant", "model_type", "c_N2_EUR_per_t"])
    df["c_N2_EUR_per_kg"] = df["c_N2_EUR_per_t"] / 1000.0
    return df


def plot_spezifische_stickstoffkosten(df, out_pdf="spezifische_stickstoffkosten_basisfall.pdf", out_png="spezifische_stickstoffkosten_basisfall.png"):
    plt.rcParams.update({
        "font.family": "serif",
        "mathtext.fontset": "stix",
        "font.size": 11,
        "axes.titlesize": 12,
        "axes.labelsize": 11,
        "xtick.labelsize": 10,
        "ytick.labelsize": 10,
        "legend.fontsize": 10,
    })

    # ensure consistent ordering
    variants_order = ["Einzel klein", "Einzel groß", "Doppel klein", "Doppel groß"]
    df = df.set_index("variant").loc[variants_order]

    # draw four equally spaced bars (Einzel klein, Einzel groß, Doppel klein, Doppel groß)
    variant_order = ["Einzel klein", "Einzel groß", "Doppel klein", "Doppel groß"]
    vals = [df.loc[v, "c_N2_EUR_per_kg"] for v in variant_order]
    x = np.arange(len(variant_order))
    width = 0.22

    fig, ax = plt.subplots(figsize=(6.2, 4.2))

    eink_color = COLOR_SINGLE
    doppel_color = COLOR_DOUBLE

    bars = []
    for i, v in enumerate(variant_order):
        color = eink_color if df.loc[v, "model_type"] == "Einzelkolonnenmodell" else doppel_color
        bars.append(ax.bar(x[i], vals[i], width, color=color, edgecolor="none"))

    # no title as requested
    ax.set_ylabel("Spezifische Kosten in EUR/kg$_{N_2}$", fontsize=11)

    # xticks under each bar with full variant labels like TRR plot
    variant_labels = ["Einkolonnenmodell klein", "Einkolonnenmodell groß", "Doppelkolonnenmodell klein", "Doppelkolonnenmodell groß"]
    ax.set_xticks(x)
    ax.set_xticklabels(variant_labels, rotation=25, ha="right")

    # start y at 0 and set limit to show room above bars
    ax.set_ylim(0, 0.060)

    # subtle horizontal grid
    ax.yaxis.grid(True, linestyle="--", linewidth=0.6, color="#dddddd", zorder=0)
    ax.xaxis.grid(False)

    # remove top and right spines
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    # annotate values above bars with four decimals
    for rects in bars:
        for rect in rects:
            h = rect.get_height()
            ax.text(rect.get_x() + rect.get_width() / 2, h + 0.0015, f"{h:.4f}", ha="center", va="bottom", fontsize=9)

    # no legend

    fig.tight_layout()

    out_dir = r"C:\Users\Felin\Documents\Masterthesis\Simulation_Code\GIT\Overleaf_LaTeX\bilder"
    os.makedirs(out_dir, exist_ok=True)
    pdf_path = os.path.join(out_dir, out_pdf)
    png_path = os.path.join(out_dir, out_png)
    fig.savefig(pdf_path, bbox_inches="tight")
    fig.savefig(png_path, dpi=300, bbox_inches="tight")

    print(f"Saved specific N2 PDF: {os.path.abspath(pdf_path)}")
    print(f"Saved specific N2 PNG: {os.path.abspath(png_path)}")


def create_sensitivity_dataframe():
    """Create DataFrame for sensitivity analysis over electricity prices."""
    prices = [0.13, 0.16, 0.19]
    data = []

    # Einzelkolonne klein
    ek_small = [42.91, 50.00, 57.09]
    for p, v in zip(prices, ek_small):
        data.append(("Einzel klein", "Einzelkolonnenmodell", "klein", p, v))

    # Einzelkolonne groß
    ek_large = [41.07, 48.17, 55.25]
    for p, v in zip(prices, ek_large):
        data.append(("Einzel groß", "Einzelkolonnenmodell", "groß", p, v))

    # Doppelkolonne klein
    dk_small = [39.41, 44.77, 50.13]
    for p, v in zip(prices, dk_small):
        data.append(("Doppel klein", "Doppelkolonnenmodell", "klein", p, v))

    # Doppelkolonne groß
    dk_large = [47.86, 53.23, 58.59]
    for p, v in zip(prices, dk_large):
        data.append(("Doppel groß", "Doppelkolonnenmodell", "groß", p, v))

    df = pd.DataFrame(data, columns=["variant", "model_type", "size", "c_el_EUR_per_kWh", "c_N2_EUR_per_t"]) 
    df["c_N2_EUR_per_kg"] = df["c_N2_EUR_per_t"] / 1000.0
    return df


def plot_sensitivitaet_stickstoffkosten(df, out_pdf="sensitivitaet_stickstoffkosten_strompreis.pdf", out_png="sensitivitaet_stickstoffkosten_strompreis.png"):
    plt.rcParams.update({
        "font.family": "serif",
        "mathtext.fontset": "stix",
        "font.size": 11,
        "axes.titlesize": 12,
        "axes.labelsize": 11,
        "xtick.labelsize": 10,
        "ytick.labelsize": 10,
        "legend.fontsize": 10,
    })
    linestyles = {"klein": "-", "groß": "--"}

    fig, ax = plt.subplots(figsize=(7.0, 4.5))

    variants = ["Einzel klein", "Einzel groß", "Doppel klein", "Doppel groß"]
    prices = sorted(df["c_el_EUR_per_kWh"].unique())

    for variant in variants:
        sub = df[df.variant == variant].sort_values("c_el_EUR_per_kWh")
        x = sub["c_el_EUR_per_kWh"].values
        y = sub["c_N2_EUR_per_kg"].values
        size = sub["size"].iloc[0]
        model = sub["model_type"].iloc[0]
        # color by model type (both sizes share the same color)
        color = COLOR_SINGLE if "Einzel" in model else COLOR_DOUBLE
        # create descriptive legend label
        label_map = {
            "Einzel klein": "Einkolonnenmodell klein",
            "Einzel groß": "Einkolonnenmodell groß",
            "Doppel klein": "Doppelkolonnenmodell klein",
            "Doppel groß": "Doppelkolonnenmodell groß",
        }
        ax.plot(x, y, marker="o", linestyle=linestyles.get(size, "-"), color=color, label=label_map.get(variant, variant))

    # no title per request
    ax.set_xlabel("Strompreis in EUR/kWh", fontsize=11)
    ax.set_ylabel("Spezifische Kosten in EUR/kg$_{N_2}$", fontsize=11)

    # x-ticks exactly as requested
    ax.set_xticks(prices)

    # y-axis start — choose 0.035 for better readability
    ax.set_ylim(0.035, None)

    # subtle horizontal grid
    ax.yaxis.grid(True, linestyle="--", linewidth=0.6, color="#dddddd", zorder=0)
    ax.xaxis.grid(False)

    # remove top and right spines
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    ax.legend(loc="best", fontsize=10)

    fig.tight_layout()

    out_dir = r"C:\Users\Felin\Documents\Masterthesis\Simulation_Code\GIT\Overleaf_LaTeX\bilder"
    os.makedirs(out_dir, exist_ok=True)
    pdf_path = os.path.join(out_dir, out_pdf)
    png_path = os.path.join(out_dir, out_png)
    fig.savefig(pdf_path, bbox_inches="tight")
    fig.savefig(png_path, dpi=300, bbox_inches="tight")

    print(f"Saved sensitivity PDF: {os.path.abspath(pdf_path)}")
    print(f"Saved sensitivity PNG: {os.path.abspath(png_path)}")
    print(f"Saved specific N2 PNG: {os.path.abspath(png_path)}")

def main():
    df = create_dataframe()
    # show the created table briefly
    print("DataFrame preview:")
    print(df)
    verify_sums(df)
    plot_pies(df)

    # --- TRR stacked bar plot ---
    df_trr = create_trr_dataframe()
    print("TRR DataFrame preview:")
    print(df_trr)
    plot_trr_zusammensetzung(df_trr)

    # --- Spezifische Stickstoffkosten Balkenplot ---
    df_n2 = create_n2_dataframe()
    print("N2 DataFrame preview:")
    print(df_n2)
    plot_spezifische_stickstoffkosten(df_n2)

    # --- Sensitivity: specific N2 costs vs electricity price ---
    df_sens = create_sensitivity_dataframe()
    print("Sensitivity DataFrame preview:")
    print(df_sens)
    plot_sensitivitaet_stickstoffkosten(df_sens)


if __name__ == "__main__":
    main()


def create_trr_dataframe():
    data = [
        ("Einzel klein", 1076067, 556029, 5063682, 6695778),
        ("Einzel groß", 3127420, 1616011, 17325345, 22068776),
        ("Doppel klein", 1426738, 737229, 3831662, 5995630),
        ("Doppel groß", 7436595, 3842663, 13109480, 24388739),
    ]
    df = pd.DataFrame(data, columns=["variant", "CC_L", "OM_L", "EC_L", "TRR_L"])

    # convert to Mio EUR/a
    df["CC_L_Mio"] = df["CC_L"] / 1e6
    df["OM_L_Mio"] = df["OM_L"] / 1e6
    df["EC_L_Mio"] = df["EC_L"] / 1e6
    df["TRR_L_Mio"] = df["TRR_L"] / 1e6

    return df


def plot_trr_zusammensetzung(df, out_pdf="trr_zusammensetzung.pdf", out_png="trr_zusammensetzung.png"):
    # plotting parameters
    plt.rcParams.update({
        "font.family": "serif",
        "mathtext.fontset": "stix",
        "font.size": 11,
    })

    variants = ["Einzel klein", "Einzel groß", "Doppel klein", "Doppel groß"]
    df = df.set_index("variant").loc[variants]

    cc = df["CC_L_Mio"].values
    om = df["OM_L_Mio"].values
    ec = df["EC_L_Mio"].values
    trr = df["TRR_L_Mio"].values

    x = np.arange(len(variants))

    cc_color = "#4C6A92"
    om_color = "#E69F00"
    ec_color = "#2CA02C"

    fig, ax = plt.subplots(figsize=(7.5, 4.8))

    bars_cc = ax.bar(x, cc, color=cc_color, label="Kapitalgebundene Kosten $CC_L$", edgecolor="none")
    bars_om = ax.bar(x, om, bottom=cc, color=om_color, label="Betriebs- und Wartungskosten $OM_L$", edgecolor="none")
    bars_ec = ax.bar(x, ec, bottom=cc + om, color=ec_color, label="Energiekosten $EC_L$", edgecolor="none")

    # y-axis label and title
    ax.set_ylabel("Jahreskosten in Mio. EUR/a")
    ax.set_title("Zusammensetzung des jährlichen Total Revenue Requirement")

    # x ticks: variant names rotated
    ax.set_xticks(x)
    ax.set_xticklabels(variants, rotation=25, ha="right")

    # horizontal grid only
    ax.yaxis.grid(True, linestyle="--", linewidth=0.6, color="#cccccc", zorder=0)
    ax.xaxis.grid(False)

    # remove top and right spines
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    # place legend to the right outside
    ax.legend(loc="upper left", bbox_to_anchor=(1.02, 1), frameon=False)

    # set y limit to leave room for labels
    ymax = trr.max() * 1.12
    ax.set_ylim(0, ymax)

    # annotate TRR above bars
    for xi, yi in zip(x, trr):
        ax.text(xi, yi + ymax * 0.01, f"{yi:.1f}", ha="center", va="bottom", fontsize=10)

    fig.tight_layout()

    # adjust to make room for legend on the right
    fig.subplots_adjust(right=0.78)

    out_dir = r"C:\Users\Felin\Documents\Masterthesis\Simulation_Code\GIT\Overleaf_LaTeX\bilder"
    os.makedirs(out_dir, exist_ok=True)
    pdf_path = os.path.join(out_dir, out_pdf)
    png_path = os.path.join(out_dir, out_png)
    fig.savefig(pdf_path, bbox_inches="tight")
    fig.savefig(png_path, dpi=300, bbox_inches="tight")

    print(f"Saved TRR PDF: {os.path.abspath(pdf_path)}")
    print(f"Saved TRR PNG: {os.path.abspath(png_path)}")
