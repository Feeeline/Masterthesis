from pathlib import Path
from tools import plot_exergy_results as p

TABLE_SINGLE = Path(r"Overleaf_LaTeX/tabellen/aspen_luftzerlegung_components_single.tex")
STREAMS_SINGLE = Path(r"Overleaf_LaTeX/tabellen/aspen_luftzerlegung_streams_single.tex")
GLOBAL_SINGLE = Path(r"Overleaf_LaTeX/tabellen/aspen_luftzerlegung_global_check_single.tex")

if __name__ == '__main__':
    df_single = p.parse_component_table(TABLE_SINGLE)
    streams_single_thermo = p.parse_stream_thermo_data(STREAMS_SINGLE)
    metrics_single_w, metrics_single_mw, product_stream_single, raw_single = p.parse_global_master_table(GLOBAL_SINGLE)
    computed_single = p.compute_global_metrics_from_tables(df_single, streams_single_thermo, product_stream_single, 'Einzelkolonne')
    print('raw_single:', raw_single)
    print('computed_single:', computed_single)
    print('metrics_single_w:', metrics_single_w)
    prod = computed_single.get('E_P') or raw_single.get('E_prod')
    E_dest = computed_single.get('E_D') or raw_single.get('E_dest')
    E_loss = computed_single.get('E_L') or raw_single.get('E_loss')
    print('prod, dest, loss:', prod, E_dest, E_loss)
    if None not in (prod, E_dest, E_loss):
        print('sum_right calc:', prod + E_dest + E_loss)
