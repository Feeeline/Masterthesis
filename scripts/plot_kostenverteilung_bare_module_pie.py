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
        r, g, b = to_rgb(hex_color)
        h, l, s = colorsys.rgb_to_hls(r, g, b)
        # create luminance values centered on original luminance
        low = max(0.05, l - delta_l)
        high = min(0.95, l + delta_l)
        ls = np.linspace(high, low, n)
        shades = []
        for lv in ls:
            rr, gg, bb = colorsys.hls_to_rgb(h, float(lv), s)
            shades.append(to_hex((rr, gg, bb)))
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


def main():
    df = create_dataframe()
    # show the created table briefly
    print("DataFrame preview:")
    print(df)
    verify_sums(df)

    plot_pies(df)


if __name__ == "__main__":
    main()
