from pathlib import Path
from tools import plot_exergy_results as p

TABLE_SINGLE = Path(r"Overleaf_LaTeX/tabellen/aspen_luftzerlegung_components_single.tex")
STREAMS_SINGLE = Path(r"Overleaf_LaTeX/tabellen/aspen_luftzerlegung_streams_single.tex")

if __name__ == '__main__':
    df_single = p.parse_component_table(TABLE_SINGLE)
    streams_single_thermo = p.parse_stream_thermo_data(STREAMS_SINGLE)
    # compute metrics from component/stream tables directly (no global LaTeX parsing)
    computed_single = p.compute_global_metrics_from_tables(df_single, streams_single_thermo, None, 'Einzelkolonne')
    print('computed_single:', computed_single)
    prod = computed_single.get('E_P')
    E_dest = computed_single.get('E_D')
    E_loss = computed_single.get('E_L')
    print('prod, dest, loss:', prod, E_dest, E_loss)
    if None not in (prod, E_dest, E_loss):
        print('sum_right calc:', prod + E_dest + E_loss)
