import json
import os
import logging
import sys
import math

from exerpy import ExergyAnalysis

# Keep full precision for generated LaTeX tables (no rounding)
NO_ROUNDING = True

# Get the log file path
log_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'parser_run.log'))

"""
Logging setup note:
- We avoid opening parser_run.log via FileHandler because shell redirection
    (e.g. `python tests/test_aspen_luftzerlegung.py > parser_run.log 2>&1`) already
    owns the file handle and causes PermissionError on Windows.
- Instead, emit logs to stdout only; the shell captures them into parser_run.log.
"""

# Reset existing handlers and configure stdout-only logging
for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)

console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(logging.Formatter('%(message)s'))
logging.root.addHandler(console_handler)
logging.root.setLevel(logging.INFO)

#model_path = r'C:\Users\Felin\Documents\Masterthesis\Code\Exerpy\exerpy\examples\asu_aspen\Doppelkolonne.bkp'
model_path = r"C:\Users\Felin\Documents\Masterthesis\Simulation_Code\GIT\examples\asu_aspen\Doppelkolonne\Doppelkolonne_Simulation_Final.bkp"


ean = ExergyAnalysis.from_aspen(model_path, chemExLib='Ahrendts', split_physical_exergy=True)

# ===== MHeatX CONFIGURATION (spezProdukt mode - OPTIONAL) =====
# If you want to configure specific stream pairs for MHeatX components,
# define them here. Otherwise, leave empty {} for balance-mode only.
#
# Structure:
# {
#     "component_name": {
#         "part": "E_PH" | "E_T" | "E_M",  # exergy component to use
#         "hot_pairs": [("S_in", "S_out"), ...],      # streams giving up exergy (fuel-like)
#         "cold_pairs": [("S_in", "S_out"), ...],     # streams taking exergy (product-like)
#         "product_pairs": [("S_in", "S_out"), ...],  # which cold pairs are "product"
#         "fuel_pairs": [("S_in", "S_out"), ...],     # optional: override fuel base (default=hot_pairs)
#     }
# }
#
# Example (uncomment and customize as needed):
MHEATX_CFG = {
    # "MW": {
    #     "part": "E_PH",
    #     "hot_pairs": [("S11", "S12"), ("S19", "S20")],       # cooled streams
    #     "cold_pairs": [("S15", "S16"), ("S27", "S28"), ("S29", "S30")],  # heated streams
    #     "product_pairs": [("S15", "S16")],  # which of the cold streams are product
    # },
}

# Apply configuration to ExergyAnalysis
if MHEATX_CFG:
    ean.set_mheatx_config(MHEATX_CFG)

# Discover power connections in the parsed model and use them for the test.
# Some Aspen files name power flows differently, so we pick available 'power' connections dynamically.
power_conns = ean.list_connections_by_kind('power')
if len(power_conns) >= 4:
    fuel = {"inputs": power_conns[:3], "outputs": [power_conns[3]]}
else:
    # Fallback: use whatever power connections exist; if none, pick first material streams as a best-effort fallback.
    material_conns = ean.list_connections_by_kind('material')
    fuel = {"inputs": material_conns[:3], "outputs": material_conns[3:4]}

# Select product and loss streams from available material streams (fall back to specific names if present)
material_conns = ean.list_connections_by_kind('material')
product = {"inputs": [], "outputs": [c for c in material_conns if c.endswith('32')][:1] or material_conns[31:32]}
loss = {"inputs": [], "outputs": [c for c in material_conns if c.endswith('28') or c.endswith('25')][:2]}

ean.analyse(E_F=fuel, E_P=product, E_L=loss)

# --- Explicit overall-system boundary check (E_F, E_P, E_L, E_D) ---
def _sum_boundary_exergy(flow_dict: dict, label: str):
    inputs = flow_dict.get("inputs", []) or []
    outputs = flow_dict.get("outputs", []) or []

    def _E(conn_name):
        conn = ean.connections.get(conn_name)
        return None if conn is None else conn.get("E")

    in_terms = [(name, _E(name)) for name in inputs]
    out_terms = [(name, _E(name)) for name in outputs]

    in_sum = sum(v for _, v in in_terms if isinstance(v, (int, float)))
    out_sum = sum(v for _, v in out_terms if isinstance(v, (int, float)))
    total = in_sum - out_sum

    logging.info(f"\n{label} boundary terms:")
    logging.info(f"  inputs : {[name for name, _ in in_terms]}")
    for name, val in in_terms:
        logging.info(f"    + {name}: E={val}")
    logging.info(f"  outputs: {[name for name, _ in out_terms]}")
    for name, val in out_terms:
        logging.info(f"    - {name}: E={val}")
    logging.info(f"  {label} = sum(inputs) - sum(outputs) = {in_sum} - {out_sum} = {total} W")
    return total


E_F_chk = _sum_boundary_exergy(fuel, "E_F")
E_P_chk = _sum_boundary_exergy(product, "E_P")
E_L_chk = _sum_boundary_exergy(loss, "E_L")

# Informational: chemical exergy of inlet air stream S1
s1_conn = ean.connections.get("S1")
E_S1_CH = None
if isinstance(s1_conn, dict):
    E_S1_CH = s1_conn.get("E_CH")
    if not isinstance(E_S1_CH, (int, float)):
        m_s1 = s1_conn.get("m")
        e_ch_s1 = s1_conn.get("e_CH")
        if isinstance(m_s1, (int, float)) and isinstance(e_ch_s1, (int, float)):
            E_S1_CH = m_s1 * e_ch_s1

E_D_chk = None
if all(isinstance(v, (int, float)) for v in [E_F_chk, E_P_chk, E_L_chk]):
    E_D_chk = E_F_chk - E_P_chk - E_L_chk

def _stream_abs_exergy(stream_name: str):
    conn = ean.connections.get(stream_name)
    if not isinstance(conn, dict):
        return None
    E_val = conn.get("E")
    if isinstance(E_val, (int, float)):
        return E_val
    m_val = conn.get("m")
    e_ph = conn.get("e_PH")
    e_ch = conn.get("e_CH")
    if all(isinstance(v, (int, float)) for v in [m_val, e_ph, e_ch]):
        return m_val * (e_ph + e_ch)
    return None

# Custom system-level balance (Tsatsaronis-consistent boundary definition)
# E_F,tot = (W_LK1 + W_LK2 + W_PK1 - W_T) + E_S1_CH
# E_P,tot = E_S32 (absolute exergy stream)
# E_L,tot = E_S25 + E_S28 (absolute exergy streams)
E_P_tot_final = _stream_abs_exergy("S32")
E_S25_abs = _stream_abs_exergy("S25")
E_S28_abs = _stream_abs_exergy("S28")
E_L_tot_final = None
if all(isinstance(v, (int, float)) for v in [E_S25_abs, E_S28_abs]):
    E_L_tot_final = E_S25_abs + E_S28_abs

E_F_tot_final = None
if isinstance(E_F_chk, (int, float)):
    E_F_tot_final = E_F_chk + (E_S1_CH if isinstance(E_S1_CH, (int, float)) else 0.0)

E_D_tot_final = None
if all(isinstance(v, (int, float)) for v in [E_F_tot_final, E_P_tot_final, E_L_tot_final]):
    E_D_tot_final = E_F_tot_final - E_P_tot_final - E_L_tot_final

logging.info("\nOVERALL SYSTEM CONSISTENCY CHECK:")
logging.info(f"  ean.E_F={ean.E_F}, recomputed={E_F_chk}, diff={None if E_F_chk is None else ean.E_F - E_F_chk}")
logging.info(f"  ean.E_P={ean.E_P}, recomputed={E_P_chk}, diff={None if E_P_chk is None else ean.E_P - E_P_chk}")
logging.info(f"  ean.E_L={ean.E_L}, recomputed={E_L_chk}, diff={None if E_L_chk is None else ean.E_L - E_L_chk}")
logging.info(f"  ean.E_D={ean.E_D}, recomputed={E_D_chk}, diff={None if E_D_chk is None else ean.E_D - E_D_chk}")
logging.info("\nCUSTOM OVERALL BALANCE (component-compatible boundary):")
logging.info(f"  E_S1_CH = {E_S1_CH} W")
logging.info(f"  E_F_tot_final = E_F_boundary + E_S1_CH = {E_F_tot_final} W")
logging.info(f"  E_P_tot_final = E_S32 = {E_P_tot_final} W")
logging.info(f"  E_L_tot_final = E_S25 + E_S28 = {E_L_tot_final} W")
logging.info(f"  E_D_tot_final = E_F_tot_final - E_P_tot_final - E_L_tot_final = {E_D_tot_final} W")
logging.info(f"  Check: E_D_tot_final + E_L_tot_final = {None if not (isinstance(E_D_tot_final, (int,float)) and isinstance(E_L_tot_final, (int,float))) else E_D_tot_final + E_L_tot_final} W")

# --- Additional RC re-calculation and comparison (sanity check) ---
export_now = ean._serialize()
connections_now = export_now.get("connections", {})

def _power_stream_abs(stream_name: str):
    # Return absolute power/energy flow for a named power connection if present.
    conn = connections_now.get(stream_name) or ean.connections.get(stream_name)
    if not isinstance(conn, dict):
        return None
    val = conn.get("energy_flow") or conn.get("E")
    if isinstance(val, (int, float)):
        return abs(float(val))
    return None

def _stream_total_exergy_from_table(stream_name: str):
    # Find connection by name/key in the exported connections and compute total exergy m*(e_PH+e_CH)
    conn = connections_now.get(stream_name)
    if not isinstance(conn, dict):
        for key, c in connections_now.items():
            if not isinstance(c, dict):
                continue
            name = str(c.get("name", key))
            if name == stream_name or str(key) == stream_name:
                conn = c
                break
    if not isinstance(conn, dict):
        return None
    m_val = conn.get("m")
    e_ph = conn.get("e_PH")
    e_ch = conn.get("e_CH")
    e_ph_eff = None
    if isinstance(e_ph, (int, float)):
        e_ph_eff = float(e_ph)
    else:
        e_t = conn.get("e_T")
        e_m = conn.get("e_M")
        if isinstance(e_t, (int, float)) and isinstance(e_m, (int, float)):
            e_ph_eff = float(e_t) + float(e_m)
        elif isinstance(e_ch, (int, float)):
            e_ph_eff = 0.0

    if all(isinstance(v, (int, float)) for v in [m_val, e_ph_eff, e_ch]):
        return float(m_val) * (float(e_ph_eff) + float(e_ch))
    return None

def _find_conn_by_suffix(suffix: str):
    for key, conn in connections_now.items():
        name = str(conn.get("name", key))
        if name.endswith(str(suffix)) or str(key).endswith(str(suffix)):
            return conn
    return None

def _get_val(conn, key_name: str):
    if not conn:
        return None
    return conn.get(key_name)

# Try to locate streams 33..36 by suffix (best-effort)
s33 = _find_conn_by_suffix("33")
s34 = _find_conn_by_suffix("34")
s35 = _find_conn_by_suffix("35")
s36 = _find_conn_by_suffix("36")

ep_calc = None
ef_calc = None
ed_calc = None
tol = 1e-6

if s34 and s35:
    et34 = _get_val(s34, "e_T") or 0.0
    et35 = _get_val(s35, "e_T") or 0.0
    ep_calc = et34 - et35

if s35 and s36 and s33 and s34:
    eph35 = _get_val(s35, "e_PH") or 0.0
    eph36 = _get_val(s36, "e_PH") or 0.0
    em33 = _get_val(s33, "e_M") or 0.0
    em34 = _get_val(s34, "e_M") or 0.0
    ef_calc = eph35 - eph36 + em33 - em34

if ep_calc is not None and ef_calc is not None:
    ed_calc = ef_calc - ep_calc

# Locate RC component (by name or prefix)
rc_comp = ean.components.get("RC") or next((c for n, c in ean.components.items() if str(n).upper().startswith("RC")), None)

E_P_comp = getattr(rc_comp, "E_P", None) if rc_comp else None
E_F_comp = getattr(rc_comp, "E_F", None) if rc_comp else None
E_D_comp = getattr(rc_comp, "E_D", None) if rc_comp else None
eps_comp = getattr(rc_comp, "epsilon", None) if rc_comp else None

logging.info("\nAdditional RC re-calculation check:")
logging.info(f"  Calculated -> Ep={ep_calc}, Ef={ef_calc}, Ed={ed_calc}")
logging.info(f"  Component  -> Ep={E_P_comp}, Ef={E_F_comp}, Ed={E_D_comp}")

def _cmp(a, b):
    if a is None or b is None:
        return False
    try:
        return abs(a - b) <= tol
    except Exception:
        return False

if E_P_comp is not None and ep_calc is not None:
    logging.info("  Ep match: " + ("YES" if _cmp(E_P_comp, ep_calc) else f"NO (diff={E_P_comp - ep_calc:.6g})"))
else:
    logging.info("  Ep match: N/A (missing values)")

if E_F_comp is not None and ef_calc is not None:
    logging.info("  Ef match: " + ("YES" if _cmp(E_F_comp, ef_calc) else f"NO (diff={E_F_comp - ef_calc:.6g})"))
else:
    logging.info("  Ef match: N/A (missing values)")

if E_D_comp is not None and ed_calc is not None:
    logging.info("  Ed match: " + ("YES" if _cmp(E_D_comp, ed_calc) else f"NO (diff={E_D_comp - ed_calc:.6g})"))
else:
    logging.info("  Ed match: N/A (missing values)")

# Compare epsilon if possible (epsilon = Ep / Ef if Ef != 0)
eps_calc = None
if ef_calc:
    try:
        eps_calc = ep_calc / ef_calc if ef_calc != 0 else None
    except Exception:
        eps_calc = None

logging.info(f"  epsilon -> comp={eps_comp}, calc={eps_calc}")
if eps_comp is not None and eps_calc is not None:
    logging.info("  epsilon match: " + ("YES" if _cmp(eps_comp, eps_calc) else f"NO (diff={eps_comp - eps_calc:.6g})"))
else:
    logging.info("  epsilon match: N/A (missing values)")

# --- Recompute using total flows (convert per-mass [J/kg] -> total [W] by multiplying with mass flow [kg/s])
def _total_from_permass(conn, key_permass: str, key_mass: str = "m"):
    if not conn:
        return None
    val_permass = conn.get(key_permass)
    mass = conn.get(key_mass)
    try:
        if val_permass is None or mass is None:
            return None
        return float(val_permass) * float(mass)
    except Exception:
        return None

et34_tot = _total_from_permass(s34, "e_T")
et35_tot = _total_from_permass(s35, "e_T")
eph35_tot = _total_from_permass(s35, "e_PH")
eph36_tot = _total_from_permass(s36, "e_PH")
em33_tot = _total_from_permass(s33, "e_M")
em34_tot = _total_from_permass(s34, "e_M")

ep_calc_tot = None
ef_calc_tot = None
ed_calc_tot = None

if et34_tot is not None and et35_tot is not None:
    ep_calc_tot = et34_tot - et35_tot

if eph35_tot is not None and eph36_tot is not None and em33_tot is not None and em34_tot is not None:
    ef_calc_tot = eph35_tot - eph36_tot + em33_tot - em34_tot

if ep_calc_tot is not None and ef_calc_tot is not None:
    ed_calc_tot = ef_calc_tot - ep_calc_tot

logging.info("\nRecomputed totals (J/kg * m [kg/s] -> W):")
logging.info(f"  Totals -> Ep={ep_calc_tot}, Ef={ef_calc_tot}, Ed={ed_calc_tot}")
if E_P_comp is not None and ep_calc_tot is not None:
    logging.info("  Ep (tot) match: " + ("YES" if _cmp(E_P_comp, ep_calc_tot) else f"NO (diff={E_P_comp - ep_calc_tot:.6g})"))
else:
    logging.info("  Ep (tot) match: N/A (missing values)")

if E_F_comp is not None and ef_calc_tot is not None:
    logging.info("  Ef (tot) match: " + ("YES" if _cmp(E_F_comp, ef_calc_tot) else f"NO (diff={E_F_comp - ef_calc_tot:.6g})"))
else:
    logging.info("  Ef (tot) match: N/A (missing values)")

if E_D_comp is not None and ed_calc_tot is not None:
    logging.info("  Ed (tot) match: " + ("YES" if _cmp(E_D_comp, ed_calc_tot) else f"NO (diff={E_D_comp - ed_calc_tot:.6g})"))
else:
    logging.info("  Ed (tot) match: N/A (missing values)")

eps_calc_tot = None
if ef_calc_tot:
    try:
        eps_calc_tot = ep_calc_tot / ef_calc_tot if ef_calc_tot != 0 else None
    except Exception:
        eps_calc_tot = None

logging.info(f"  epsilon -> comp={eps_comp}, calc_tot={eps_calc_tot}")
if eps_comp is not None and eps_calc_tot is not None:
    logging.info("  epsilon (tot) match: " + ("YES" if _cmp(eps_comp, eps_calc_tot) else f"NO (diff={eps_comp - eps_calc_tot:.6g})"))
else:
    logging.info("  epsilon (tot) match: N/A (missing values)")

# --- Condensation thermal exergy: Ep as difference of E_T totals for streams 33 and 34
et33_tot = _total_from_permass(s33, "e_T")
et34_tot = _total_from_permass(s34, "e_T")
ep_condens_tot = None
if et33_tot is not None and et34_tot is not None:
    # determine which stream has larger thermal exergy and take the difference
    larger = et33_tot if et33_tot >= et34_tot else et34_tot
    smaller = et34_tot if et33_tot >= et34_tot else et33_tot
    ep_condens_tot = larger - smaller

logging.info("\nCondensation thermal exergy (E_T) comparison:")
logging.info(f"  E_T33 = {et33_tot}, E_T34 = {et34_tot}, Ep_condensation = {ep_condens_tot}")
if E_P_comp is not None and ep_condens_tot is not None:
    logging.info("  Ep_cond match: " + ("YES" if _cmp(E_P_comp, ep_condens_tot) else f"NO (diff={E_P_comp - ep_condens_tot:.6g})"))
else:
    logging.info("  Ep_cond match: N/A (missing values)")

# --- Ef per user's spec:
#  - physical exergy difference of reboiler streams 35 and 36 (non-negative)
#  - plus mechanical exergy difference of 33 and 34 (non-negative, represents pressure loss)
eph35_tot = _total_from_permass(s35, "e_PH")
eph36_tot = _total_from_permass(s36, "e_PH")
em33_tot = _total_from_permass(s33, "e_M")
em34_tot = _total_from_permass(s34, "e_M")

phys_diff = None
mech_diff = None
ef_custom = None

if eph35_tot is not None and eph36_tot is not None:
    phys_diff = abs(eph35_tot - eph36_tot)

if em33_tot is not None and em34_tot is not None:
    mech_diff = abs(em33_tot - em34_tot)

if phys_diff is not None and mech_diff is not None:
    ef_custom = phys_diff + mech_diff

logging.info("\nEf (user formula) breakdown:")
logging.info(f"  phys | E_PH35 = {eph35_tot}, E_PH36 = {eph36_tot}, phys_diff = {phys_diff}")
logging.info(f"  mech | E_M33 = {em33_tot}, E_M34 = {em34_tot}, mech_diff = {mech_diff}")
logging.info(f"  Ef_custom = {ef_custom}")
if E_F_comp is not None and ef_custom is not None:
    logging.info("  Ef_custom match: " + ("YES" if _cmp(E_F_comp, ef_custom) else f"NO (diff={E_F_comp - ef_custom:.6g})"))
else:
    logging.info("  Ef_custom match: N/A (missing values)")

# --- Compute Ed from user's Ep/Ef and compare to RC.E_D
ed_custom = None
if ef_custom is not None and ep_condens_tot is not None:
    ed_custom = ef_custom - ep_condens_tot

logging.info("\nCUSTOM ED CHECK:")
logging.info(f"  Ep_cond = {ep_condens_tot}")
logging.info(f"  Ef_custom = {ef_custom}")
logging.info(f"  Ed_custom = {ed_custom}")
if E_D_comp is not None and ed_custom is not None:
    logging.info("  Ed match (component vs custom): " + ("YES" if _cmp(E_D_comp, ed_custom) else f"NO (diff={E_D_comp - ed_custom:.6g})"))
else:
    logging.info("  Ed match: N/A (missing values)")

# Attach custom values to RC component object (so tables/logs can access them)
if rc_comp is not None:
    try:
        rc_comp.E_P_custom = ep_condens_tot
        rc_comp.E_F_custom = ef_custom
        rc_comp.E_D_custom = ed_custom
        rc_comp.epsilon_custom = (ep_condens_tot / ef_custom) if (ef_custom and ef_custom != 0) else None
    except Exception:
        pass

# --- Repeat the same custom-calculation workflow for RC2 using streams SZ37..SZ40
s37 = _find_conn_by_suffix("37")
s38 = _find_conn_by_suffix("38")
s39 = _find_conn_by_suffix("39")
s40 = _find_conn_by_suffix("40")

# Recompute condensation thermal exergy for RC2 (E_T difference between 37 and 38)
ep_condens_tot_rc2 = None
et37_tot = _total_from_permass(s37, "e_T")
et38_tot = _total_from_permass(s38, "e_T")
if et37_tot is not None and et38_tot is not None:
    larger = et37_tot if et37_tot >= et38_tot else et38_tot
    smaller = et38_tot if et37_tot >= et38_tot else et37_tot
    ep_condens_tot_rc2 = larger - smaller

# Ef for RC2: phys diff of reboiler streams (39/40) + mech diff of 37/38
eph39_tot = _total_from_permass(s39, "e_PH")
eph40_tot = _total_from_permass(s40, "e_PH")
em37_tot = _total_from_permass(s37, "e_M")
em38_tot = _total_from_permass(s38, "e_M")

phys_diff_rc2 = None
mech_diff_rc2 = None
ef_custom_rc2 = None

if eph39_tot is not None and eph40_tot is not None:
    phys_diff_rc2 = abs(eph39_tot - eph40_tot)

if em37_tot is not None and em38_tot is not None:
    mech_diff_rc2 = abs(em37_tot - em38_tot)

if phys_diff_rc2 is not None and mech_diff_rc2 is not None:
    ef_custom_rc2 = phys_diff_rc2 + mech_diff_rc2

ed_custom_rc2 = None
if ef_custom_rc2 is not None and ep_condens_tot_rc2 is not None:
    ed_custom_rc2 = ef_custom_rc2 - ep_condens_tot_rc2

logging.info("\nRC2 custom calculation (streams 37..40):")
logging.info(f"  E_T37 = {et37_tot}, E_T38 = {et38_tot}, Ep_cond_RC2 = {ep_condens_tot_rc2}")
logging.info(f"  phys | E_PH39 = {eph39_tot}, E_PH40 = {eph40_tot}, phys_diff = {phys_diff_rc2}")
logging.info(f"  mech | E_M37 = {em37_tot}, E_M38 = {em38_tot}, mech_diff = {mech_diff_rc2}")
logging.info(f"  Ef_custom_RC2 = {ef_custom_rc2}")
logging.info(f"  Ed_custom_RC2 = {ed_custom_rc2}")

# Attach custom values to RC2 component for display/export
rc2_comp = ean.components.get("RC2") or next((c for n, c in ean.components.items() if str(n).upper().startswith("RC2")), None)
if rc2_comp is not None:
    try:
        rc2_comp.E_P_custom = ep_condens_tot_rc2
        rc2_comp.E_F_custom = ef_custom_rc2
        rc2_comp.E_D_custom = ed_custom_rc2
        rc2_comp.epsilon_custom = (ep_condens_tot_rc2 / ef_custom_rc2) if (ef_custom_rc2 and ef_custom_rc2 != 0) else None
    except Exception:
        pass


# Helper: concise comparison log for a component and its custom values
def _log_component_custom_compare(name: str, comp):
    if comp is None:
        logging.info(f"{name}: component not found")
        return
    E_F = getattr(comp, 'E_F', None)
    E_P = getattr(comp, 'E_P', None)
    E_D = getattr(comp, 'E_D', None)
    E_L = getattr(comp, 'E_L', None)
    E_F_c = getattr(comp, 'E_F_custom', None)
    E_P_c = getattr(comp, 'E_P_custom', None)
    E_D_c = getattr(comp, 'E_D_custom', None)
    E_L_c = getattr(comp, 'E_L_custom', None)
    eps = getattr(comp, 'epsilon', None)
    eps_c = getattr(comp, 'epsilon_custom', None)

    logging.info("\n--- Compact comparison for %s ---" % name)
    logging.info(f"component | E_F={E_F} W | E_P={E_P} W | E_D={E_D} W | E_L={E_L} W | eps={eps}")
    logging.info(f"custom    | E_F={E_F_c} W | E_P={E_P_c} W | E_D={E_D_c} W | E_L={E_L_c} W | eps={eps_c}")
    if E_D is not None and E_D_c is not None:
        logging.info("Ed equal: " + ("YES" if _cmp(E_D, E_D_c) else f"NO (diff={E_D - E_D_c:.6g})"))
    else:
        logging.info("Ed equal: N/A")


# Emit compact comparison blocks for RC and RC2
_log_component_custom_compare('RC', rc_comp)
_log_component_custom_compare('RC2', rc2_comp)

# --- Repeat same custom-formula process for RC2 using streams 37..40
rc2_comp = ean.components.get("RC2") or next((c for n, c in ean.components.items() if str(n).upper().startswith("RC2")), None)

# locate streams 37..40
s37 = _find_conn_by_suffix("37")
s38 = _find_conn_by_suffix("38")
s39 = _find_conn_by_suffix("39")
s40 = _find_conn_by_suffix("40")

ep_condens2_tot = None
ef_custom2 = None
ed_custom2 = None

# Ep as difference of E_T totals for streams 37 and 38
et37_tot = _total_from_permass(s37, "e_T")
et38_tot = _total_from_permass(s38, "e_T")
if et37_tot is not None and et38_tot is not None:
    larger = et37_tot if et37_tot >= et38_tot else et38_tot
    smaller = et38_tot if et37_tot >= et38_tot else et37_tot
    ep_condens2_tot = larger - smaller

# Ef: physical difference of reboiler streams 39/40 + mechanical difference of 37/38
eph39_tot = _total_from_permass(s39, "e_PH")
eph40_tot = _total_from_permass(s40, "e_PH")
em37_tot = _total_from_permass(s37, "e_M")
em38_tot = _total_from_permass(s38, "e_M")

phys_diff2 = None
mech_diff2 = None

if eph39_tot is not None and eph40_tot is not None:
    phys_diff2 = abs(eph39_tot - eph40_tot)

if em37_tot is not None and em38_tot is not None:
    mech_diff2 = abs(em37_tot - em38_tot)

if phys_diff2 is not None and mech_diff2 is not None:
    ef_custom2 = phys_diff2 + mech_diff2

if ef_custom2 is not None and ep_condens2_tot is not None:
    ed_custom2 = ef_custom2 - ep_condens2_tot

logging.info("\nRC2 custom check (streams 37..40):")
logging.info(f"  Ep_cond2 = {ep_condens2_tot}")
logging.info(f"  Ef_custom2 = {ef_custom2}")
logging.info(f"  Ed_custom2 = {ed_custom2}")
if getattr(rc2_comp, 'E_D', None) is not None and ed_custom2 is not None:
    logging.info("  Ed match (RC2 component vs custom): " + ("YES" if _cmp(getattr(rc2_comp, 'E_D', None), ed_custom2) else f"NO (diff={getattr(rc2_comp, 'E_D', None) - ed_custom2:.6g})"))
else:
    logging.info("  Ed match (RC2): N/A (missing values)")

# Attach custom values to RC2 component object for display/export
if rc2_comp is not None:
    try:
        rc2_comp.E_P_custom = ep_condens2_tot
        rc2_comp.E_F_custom = ef_custom2
        rc2_comp.E_D_custom = ed_custom2
        rc2_comp.epsilon_custom = (ep_condens2_tot / ef_custom2) if (ef_custom2 and ef_custom2 != 0) else None
    except Exception:
        pass

# --- Custom calculation for MW using provided formulas
# EP = ET12 + ET20
# EF = |EPH15 - EPH16| + |EPH29 - EPH30| + |EPH27 - EPH28| + ET11 + ET19
mw_comp = ean.components.get("MW") or next((c for n, c in ean.components.items() if str(n).upper().startswith("MW")), None)

# find streams
s11 = _find_conn_by_suffix("11")
s12 = _find_conn_by_suffix("12")
s15 = _find_conn_by_suffix("15")
s16 = _find_conn_by_suffix("16")
s19 = _find_conn_by_suffix("19")
s20 = _find_conn_by_suffix("20")
s27 = _find_conn_by_suffix("27")
s28 = _find_conn_by_suffix("28")
s29 = _find_conn_by_suffix("29")
s30 = _find_conn_by_suffix("30")

et11_tot = _total_from_permass(s11, "e_T")
et12_tot = _total_from_permass(s12, "e_T")
et19_tot = _total_from_permass(s19, "e_T")
et20_tot = _total_from_permass(s20, "e_T")

eph15_tot = _total_from_permass(s15, "e_PH")
eph16_tot = _total_from_permass(s16, "e_PH")
eph27_tot = _total_from_permass(s27, "e_PH")
eph28_tot = _total_from_permass(s28, "e_PH")
eph29_tot = _total_from_permass(s29, "e_PH")
eph30_tot = _total_from_permass(s30, "e_PH")

em11_tot = _total_from_permass(s11, "e_M")
em12_tot = _total_from_permass(s12, "e_M")
em19_tot = _total_from_permass(s19, "e_M")
em20_tot = _total_from_permass(s20, "e_M")

ep_mw = None
ef_mw = None
ed_mw = None

if et12_tot is not None and et20_tot is not None:
    ep_mw = et12_tot + et20_tot

phys15_16 = abs(eph15_tot - eph16_tot) if (eph15_tot is not None and eph16_tot is not None) else None
phys29_30 = abs(eph29_tot - eph30_tot) if (eph29_tot is not None and eph30_tot is not None) else None
phys27_28 = abs(eph27_tot - eph28_tot) if (eph27_tot is not None and eph28_tot is not None) else None

# include mechanical exergy differences per user's formula: EM11 - EM12 + EM19 - EM20
mech_term = None
if em11_tot is not None and em12_tot is not None and em19_tot is not None and em20_tot is not None:
    mech_term = (em11_tot - em12_tot) + (em19_tot - em20_tot)

if phys15_16 is not None and phys29_30 is not None and phys27_28 is not None and et11_tot is not None and et19_tot is not None and mech_term is not None:
    ef_mw = phys15_16 + phys29_30 + phys27_28 + et11_tot + et19_tot + mech_term

if ef_mw is not None and ep_mw is not None:
    ed_mw = ef_mw - ep_mw

logging.info("\nMW custom calculation:")
logging.info(f"  ET11={et11_tot}, ET12={et12_tot}, ET19={et19_tot}, ET20={et20_tot}")
logging.info(f"  EPH15={eph15_tot}, EPH16={eph16_tot}, EPH27={eph27_tot}, EPH28={eph28_tot}, EPH29={eph29_tot}, EPH30={eph30_tot}")
logging.info(f"  EM11={em11_tot}, EM12={em12_tot}, EM19={em19_tot}, EM20={em20_tot}")
logging.info(f"  Ep_mw = {ep_mw}")
logging.info(f"  Ef_mw = {ef_mw}")
logging.info(f"  Ed_mw = {ed_mw}")

# Attach to MW component for display/export
if mw_comp is not None:
    try:
        mw_comp.E_P_custom = ep_mw
        mw_comp.E_F_custom = ef_mw
        mw_comp.E_D_custom = ed_mw
        mw_comp.epsilon_custom = (ep_mw / ef_mw) if (ef_mw and ef_mw != 0) else None
    except Exception:
        pass

# Compact comparison for MW
_log_component_custom_compare('MW', mw_comp)

# --- Custom calculation for GW1 (Flash) using user formulas
# Ep = m6 * (ech6 - ech5)
# Ef = m6 * (eph5 - eph6) + E7
gw1_comp = ean.components.get("GW1") or next((c for n, c in ean.components.items() if str(n).upper().startswith("GW1")), None)

# find streams S5, S6, S7 (exact match to avoid finding S15, S16, etc.)
def _find_exact_stream(stream_name: str):
    for key, conn in connections_now.items():
        name = str(conn.get("name", ""))
        if name == stream_name or str(key) == stream_name:
            return conn
    return None

s5 = _find_exact_stream("S5")
s6 = _find_exact_stream("S6")
s7 = _find_exact_stream("S7")

# GW1 Flash: Complete exergy balance
# Ep = m6 * (ech6 - ech5)  -- chemical exergy change in gas stream
# Ef = EPH5 - EPH6 - EPH7  -- physical exergy fuel term
# El = E7 = m7*(ePH7 + eCH7) -- exergy loss stream
# Ed = Ef - Ep - El

m5 = _get_val(s5, "m")
m6 = _get_val(s6, "m")
m7 = _get_val(s7, "m")
eph5 = _get_val(s5, "e_PH")
eph6 = _get_val(s6, "e_PH")
eph7 = _get_val(s7, "e_PH")
ech5 = _get_val(s5, "e_CH")
ech6 = _get_val(s6, "e_CH")
ech7 = _get_val(s7, "e_CH")

ep_gw1 = None
ef_gw1 = None
ed_gw1 = None
el_gw1 = None

# Ep = product (chemical exergy increase in gas stream)
if m6 is not None and ech6 is not None and ech5 is not None:
    ep_gw1 = m6 * (ech6 - ech5)

# Ef = fuel (physical exergy formulation) -- use requested formula:
# Ef = m6*(eph5 - eph6) + m7*(eph5 + ech5)
ef_gw1 = None
term1 = None
term2 = None
if isinstance(m6, (int, float)) and isinstance(eph5, (int, float)) and isinstance(eph6, (int, float)):
    term1 = float(m6) * (float(eph5) - float(eph6))
if isinstance(m7, (int, float)) and isinstance(eph5, (int, float)) and isinstance(ech5, (int, float)):
    term2 = float(m7) * (float(eph5) + float(ech5))
if term1 is not None or term2 is not None:
    ef_gw1 = (term1 or 0.0) + (term2 or 0.0)

# El = exergy loss in stream 7 (total exergy)
if all(v is not None for v in [m7, eph7, ech7]):
    el_gw1 = m7 * (eph7 + ech7)

# Ed = destruction (separate from losses)
if ef_gw1 is not None and ep_gw1 is not None and el_gw1 is not None:
    ed_gw1 = ef_gw1 - ep_gw1 - el_gw1

logging.info("\nGW1 custom calculation (complete exergy balance):")
logging.info(f"  Streams: m5={m5}, m6={m6}, m7={m7} kg/s")
logging.info(f"  Physical: eph5={eph5}, eph6={eph6}, eph7={eph7} J/kg")
logging.info(f"  Chemical: ech5={ech5}, ech6={ech6}, ech7={ech7} J/kg")
logging.info(f"  Ep_gw1 = m6*(ech6-ech5) = {ep_gw1} W")
logging.info(f"  Ef_gw1 = m5*eph5 - m6*eph6 - m7*eph7 = {ef_gw1} W")
logging.info(f"  El_gw1 = m7*(eph7+ech7) = {el_gw1} W")
logging.info(f"  Ed_gw1 = Ef - Ep - El = {ed_gw1} W")

# Attach to GW1 component for display/export
if gw1_comp is not None:
    try:
        gw1_comp.E_P_custom = ep_gw1
        gw1_comp.E_F_custom = ef_gw1
        gw1_comp.E_D_custom = ed_gw1
        gw1_comp.E_L_custom = el_gw1
        gw1_comp.epsilon_custom = (ep_gw1 / ef_gw1) if (ef_gw1 and ef_gw1 != 0) else None
    except Exception:
        pass

# Compact comparison for GW1
_log_component_custom_compare('GW1', gw1_comp)


# --- GW2 custom calculations using streams 6, 8, 9, 10
# GW2 Separator: Complete exergy balance
# Ep = m8 * (ech8 - ech6)  -- chemical exergy gain in product stream 8
# Ef = EPH6 - EPH8 - EPH9 - EPH10  -- physical exergy fuel term
# El = E9 + E10 (total exergy losses)
# Ed = Ef - Ep - El

gw2_comp = ean.components.get("GW2") or next((c for n, c in ean.components.items() if str(n).upper().startswith("GW2")), None)

# locate streams 6, 8, 9, 10
s6 = _find_exact_stream("S6")
s8 = _find_exact_stream("S8")
s9 = _find_exact_stream("S9")
s10 = _find_exact_stream("S10")

m6 = _get_val(s6, "m")
m8 = _get_val(s8, "m")
m9 = _get_val(s9, "m")
m10 = _get_val(s10, "m")

eph6 = _get_val(s6, "e_PH")
eph8 = _get_val(s8, "e_PH")
eph9 = _get_val(s9, "e_PH")
eph10 = _get_val(s10, "e_PH")

ech6 = _get_val(s6, "e_CH")
ech8 = _get_val(s8, "e_CH")
ech9 = _get_val(s9, "e_CH")
ech10 = _get_val(s10, "e_CH")

ep_gw2 = None
ef_gw2 = None
ed_gw2 = None
el_gw2 = None

# Ep = product (chemical exergy gain in main product stream S8)
if m8 is not None and ech8 is not None and ech6 is not None:
    ep_gw2 = m8 * (ech8 - ech6)

# Ef = fuel using user-provided custom formula:
# Ef = m8*(eph6 - eph8) + m9*(eph6 + ech6) + m10*(eph6 + ech6)
# Note: terms are included if the required quantities exist.
term_a = None
term_b = None
term_c = None
if isinstance(m8, (int, float)) and isinstance(eph6, (int, float)) and isinstance(eph8, (int, float)):
    term_a = float(m8) * (float(eph6) - float(eph8))
if isinstance(m9, (int, float)) and isinstance(eph6, (int, float)) and isinstance(ech6, (int, float)):
    term_b = float(m9) * (float(eph6) + float(ech6))
if isinstance(m10, (int, float)) and isinstance(eph6, (int, float)) and isinstance(ech6, (int, float)):
    term_c = float(m10) * (float(eph6) + float(ech6))

if term_a is not None or term_b is not None or term_c is not None:
    ef_gw2 = (term_a or 0.0) + (term_b or 0.0) + (term_c or 0.0)

# El = total exergy carried away by streams 9 and 10 (loss streams)
E9_total = None
E10_total = None
if isinstance(m9, (int, float)) and isinstance(eph9, (int, float)) and isinstance(ech9, (int, float)):
    E9_total = float(m9) * (float(eph9) + float(ech9))
if isinstance(m10, (int, float)) and isinstance(eph10, (int, float)) and isinstance(ech10, (int, float)):
    E10_total = float(m10) * (float(eph10) + float(ech10))
if E9_total is not None or E10_total is not None:
    el_gw2 = (E9_total or 0.0) + (E10_total or 0.0)

# Ed = destruction (separate from losses)
if ef_gw2 is not None and ep_gw2 is not None and el_gw2 is not None:
    ed_gw2 = ef_gw2 - ep_gw2 - el_gw2

logging.info("\nGW2 custom calculation (complete exergy balance):")
logging.info(f"  Streams: m6={m6}, m8={m8}, m9={m9}, m10={m10} kg/s")
logging.info(f"  Physical [J/kg]: eph6={eph6}, eph8={eph8}, eph9={eph9}, eph10={eph10}")
logging.info(f"  Chemical [J/kg]: ech6={ech6}, ech8={ech8}, ech9={ech9}, ech10={ech10}")
logging.info(f"  Ep_gw2 = m8*(ech8-ech6) = {ep_gw2} W")
logging.info(f"  Ef_gw2 = m6*eph6 - m8*eph8 - m9*eph9 - m10*eph10 = {ef_gw2} W")
logging.info(f"  El_gw2 = E9 + E10 = {el_gw2} W")
logging.info(f"  Ed_gw2 = Ef - Ep - El = {ed_gw2} W")

# Attach to GW2 component for display/export
if gw2_comp is not None:
    try:
        gw2_comp.E_P_custom = ep_gw2
        gw2_comp.E_F_custom = ef_gw2
        gw2_comp.E_D_custom = ed_gw2
        gw2_comp.E_L_custom = el_gw2
        gw2_comp.epsilon_custom = (ep_gw2 / ef_gw2) if (ef_gw2 and ef_gw2 != 0) else None
    except Exception:
        pass

# Compact comparison for GW2
_log_component_custom_compare('GW2', gw2_comp)


# --- MIX1 custom calculation with total exergy (physical + chemical)
# Use complete stream exergy rates to include mixing effects represented in stream states.
mix1_comp = ean.components.get("MIX1") or next((c for n, c in ean.components.items() if str(n).strip().upper() == "MIX1"), None)
s16_mix = _find_exact_stream("S16")
s31_mix = _find_exact_stream("S31")
s32_mix = _find_exact_stream("S32")

def _total_exergy_ph_ch_mix(conn):
    if not conn:
        return None
    m = _get_val(conn, "m")
    eph = _get_val(conn, "e_PH")
    ech = _get_val(conn, "e_CH")
    if m is None or eph is None or ech is None:
        return None
    return float(m) * (float(eph) + float(ech))

E16_tot = _total_exergy_ph_ch_mix(s16_mix)
E31_tot = _total_exergy_ph_ch_mix(s31_mix)
E32_tot = _total_exergy_ph_ch_mix(s32_mix)

mix1_E_F_custom = None
mix1_E_P_custom = None
mix1_E_D_custom = None
mix1_E_L_custom = 0.0

if all(isinstance(v, (int, float)) for v in [E16_tot, E31_tot, E32_tot]):
    mix1_E_F_custom = E16_tot + E31_tot
    mix1_E_P_custom = E32_tot
    mix1_E_D_custom = mix1_E_F_custom - mix1_E_P_custom

logging.info("\nMIX1 custom calculation (total exergy based):")
logging.info(f"  E16_tot = m16*(e_PH16+e_CH16) = {E16_tot} W")
logging.info(f"  E31_tot = m31*(e_PH31+e_CH31) = {E31_tot} W")
logging.info(f"  E32_tot = m32*(e_PH32+e_CH32) = {E32_tot} W")
logging.info(f"  E_F_custom = E16_tot + E31_tot = {mix1_E_F_custom} W")
logging.info(f"  E_P_custom = E32_tot = {mix1_E_P_custom} W")
logging.info(f"  E_D_custom = E_F_custom - E_P_custom = {mix1_E_D_custom} W")

if mix1_comp is not None:
    try:
        mix1_comp.E_F_custom = mix1_E_F_custom
        mix1_comp.E_P_custom = mix1_E_P_custom
        mix1_comp.E_D_custom = mix1_E_D_custom
        mix1_comp.E_L_custom = mix1_E_L_custom
        mix1_comp.epsilon_custom = (
            mix1_E_P_custom / mix1_E_F_custom
            if (isinstance(mix1_E_P_custom, (int, float)) and isinstance(mix1_E_F_custom, (int, float)) and mix1_E_F_custom != 0)
            else None
        )
    except Exception:
        pass

_log_component_custom_compare('MIX1', mix1_comp)


# --- KOLLP (LP column) custom calculations per user definition
# Gesamtbilanz:
#   E_D_bal = sum_in m*(e_PH+e_CH) - sum_out m*(e_PH+e_CH)
#   in: 14, 21, 18, 36, 38
#   out: 22, 29, 35, 37
# SPECO Produkt:
#   E_P = E_P,ch + E_P,T + E_P,M
#   E_P,ch = m22*(e_ch,22 - e_ch,mix) + m29*(e_ch,29 - e_ch,mix)
#   E_P,T  = m22*(e_T,22 - e_T,mix)
#   E_P,M  = m29*(e_M,29 - e_M,mix)
# Brennstoff:
#   E_F = E_F,Reboiler + E_F,Kondensator + E_F,intern
#   E_F,Reboiler   = m38*e_PH,38 - m37*e_PH,37
#   E_F,Kondensator= m36*e_PH,36 - m35*e_PH,35
#   E_F,intern     = m22*(e_M,mix - e_M,22) + m29*(e_T,mix - e_T,29)
kollp_comp = ean.components.get("KOLLP") or next((c for n, c in ean.components.items() if str(n).strip().upper() == "KOLLP"), None)

def _find_exact_stream_any(*stream_names):
    for stream_name in stream_names:
        stream = _find_exact_stream(stream_name)
        if stream is not None:
            return stream
    return None

s14 = _find_exact_stream("S14")
s18 = _find_exact_stream("S18")
s21 = _find_exact_stream("S21")
s22 = _find_exact_stream("S22")
s29 = _find_exact_stream("S29")
s35 = _find_exact_stream_any("S35", "SZ35")
s36 = _find_exact_stream_any("S36", "SZ36")
s37 = _find_exact_stream_any("S37", "SZ37")
s38 = _find_exact_stream_any("S38", "SZ38")

def _total_exergy_ph_ch(conn):
    if not conn:
        return None
    m = _get_val(conn, "m")
    eph = _get_val(conn, "e_PH")
    ech = _get_val(conn, "e_CH")
    if m is None or eph is None or ech is None:
        return None
    return float(m) * (float(eph) + float(ech))

def _mix_property(streams, prop):
    masses = [_get_val(stream, "m") for stream in streams]
    props = [_get_val(stream, prop) for stream in streams]
    if any(v is None for v in masses + props):
        return None
    m_sum = sum(float(v) for v in masses)
    if m_sum == 0:
        return None
    weighted_sum = sum(float(masses[idx]) * float(props[idx]) for idx in range(len(streams)))
    return weighted_sum / m_sum

# 1) Gesamtbilanz (absolute Exergiestroeme m*(e_PH+e_CH))
eintritt_streams = [s14, s21, s18, s36, s38]
austritt_streams = [s22, s29, s35, s37]

E_in_terms = [_total_exergy_ph_ch(stream) for stream in eintritt_streams]
E_out_terms = [_total_exergy_ph_ch(stream) for stream in austritt_streams]

E_in_kollp = sum(E_in_terms) if all(v is not None for v in E_in_terms) else None
E_out_kollp = sum(E_out_terms) if all(v is not None for v in E_out_terms) else None
Ed_kollp_bal = (E_in_kollp - E_out_kollp) if (E_in_kollp is not None and E_out_kollp is not None) else None

# Mixer-Referenzzustand aus den Feedstroemen 14, 18, 21
mix_streams = [s14, s18, s21]
e_ch_mix = _mix_property(mix_streams, "e_CH")
e_T_mix = _mix_property(mix_streams, "e_T")
e_M_mix = _mix_property(mix_streams, "e_M")

m22 = _get_val(s22, "m")
m29 = _get_val(s29, "m")
m35 = _get_val(s35, "m")
m36 = _get_val(s36, "m")
m37 = _get_val(s37, "m")
m38 = _get_val(s38, "m")

ech22 = _get_val(s22, "e_CH")
ech29 = _get_val(s29, "e_CH")
eT22 = _get_val(s22, "e_T")
eT29 = _get_val(s29, "e_T")
eM22 = _get_val(s22, "e_M")
eM29 = _get_val(s29, "e_M")
ePH35 = _get_val(s35, "e_PH")
ePH36 = _get_val(s36, "e_PH")
ePH37 = _get_val(s37, "e_PH")
ePH38 = _get_val(s38, "e_PH")

Ep_ch_kollp = None
Ep_T_kollp = None
Ep_M_kollp = None
Ep_kollp = None
Ef_reboiler_kollp = None
Ef_kond_kollp = None
Ef_intern_kollp = None
Ef_kollp = None
Ed_kollp_formel = None

# 2) Exergie-Produkt
if all(v is not None for v in [m22, m29, ech22, ech29, e_ch_mix]):
    Ep_ch_kollp = float(m22) * (float(ech22) - float(e_ch_mix)) + float(m29) * (float(ech29) - float(e_ch_mix))

if all(v is not None for v in [m22, eT22, e_T_mix]):
    Ep_T_kollp = float(m22) * (float(eT22) - float(e_T_mix))

if all(v is not None for v in [m29, eM29, e_M_mix]):
    Ep_M_kollp = float(m29) * (float(eM29) - float(e_M_mix))

if Ep_ch_kollp is not None and Ep_T_kollp is not None and Ep_M_kollp is not None:
    Ep_kollp = Ep_ch_kollp + Ep_T_kollp + Ep_M_kollp

# 3) Exergie-Brennstoff
if all(v is not None for v in [m38, ePH38, m37, ePH37]):
    Ef_reboiler_kollp = float(m38) * float(ePH38) - float(m37) * float(ePH37)

if all(v is not None for v in [m36, ePH36, m35, ePH35]):
    Ef_kond_kollp = float(m36) * float(ePH36) - float(m35) * float(ePH35)

if all(v is not None for v in [m22, e_M_mix, eM22, m29, e_T_mix, eT29]):
    Ef_intern_kollp = float(m22) * (float(e_M_mix) - float(eM22)) + float(m29) * (float(e_T_mix) - float(eT29))

if Ef_reboiler_kollp is not None and Ef_kond_kollp is not None and Ef_intern_kollp is not None:
    Ef_kollp = Ef_reboiler_kollp + Ef_kond_kollp + Ef_intern_kollp

if Ef_kollp is not None and Ep_kollp is not None:
    Ed_kollp_formel = Ef_kollp - Ep_kollp

logging.info("\nKOLLP custom calculation (strict user formulas):")
logging.info(f"  Gesamtbilanz in  [14,21,18,36,38] = {E_in_kollp} W")
logging.info(f"  Gesamtbilanz out [22,29,35,37]    = {E_out_kollp} W")
logging.info(f"  Ed_kollp_bal = Ein - Aus          = {Ed_kollp_bal} W")
logging.info(f"  mix: e_ch_mix={e_ch_mix}, e_T_mix={e_T_mix}, e_M_mix={e_M_mix}")
logging.info(f"  Ep_ch={Ep_ch_kollp}, Ep_T={Ep_T_kollp}, Ep_M={Ep_M_kollp}, Ep={Ep_kollp}")
logging.info(f"  Ef_reboiler={Ef_reboiler_kollp}, Ef_kondensator={Ef_kond_kollp}, Ef_intern={Ef_intern_kollp}, Ef={Ef_kollp}")
logging.info(f"  Ed_kollp_formel = Ef - Ep         = {Ed_kollp_formel} W")
if Ed_kollp_bal is not None and Ed_kollp_formel is not None:
    logging.info(f"  Delta (Ed_bal - Ed_formel)        = {Ed_kollp_bal - Ed_kollp_formel} W")

# Attach custom values for export/table display
if kollp_comp is not None:
    try:
        kollp_comp.E_P_custom = Ep_kollp
        kollp_comp.E_F_custom = Ef_kollp
        kollp_comp.E_D_custom = Ed_kollp_formel
        kollp_comp.epsilon_custom = (Ep_kollp / Ef_kollp) if (Ef_kollp and Ef_kollp != 0) else None
    except Exception:
        pass

# Compact comparison for KOLLP
_log_component_custom_compare('KOLLP', kollp_comp)


# --- KOLHP (HP column) functional SPECO-style setup (per user/Tesch)
# Overall balance (reference):
#   Ed_bal = Ein - Aus with absolute exergy rates E = m*(e_PH + e_CH)
# Functional formulation:
#   Ef = (SZ34 -> SZ33 loop effort)
#      + m13*(e_M12 - e_M13)
#      + m15*(e_T12 - e_T15)
#   Ep = sum_{13,15,17} m_out*(e_CH,out - e_CH,12)
#      + [m13*(e_T13 - e_T12) + m17*(e_T17 - e_T12)]
#      + [m15*(e_M15 - e_M12) + m17*(e_M17 - e_M12)]
kolhp_comp = ean.components.get("KOLHP") or next((c for n, c in ean.components.items() if str(n).strip().upper() == "KOLHP"), None)

s12_hp = _find_exact_stream("S12")
s34_hp = _find_exact_stream_any("S34", "SZ34")
s13_hp = _find_exact_stream("S13")
s15_hp = _find_exact_stream("S15")
s17_hp = _find_exact_stream("S17")
s33_hp = _find_exact_stream_any("S33", "SZ33")

hp_in_streams = [s12_hp, s34_hp]
hp_out_streams = [s13_hp, s15_hp, s17_hp, s33_hp]

E_in_hp_terms = [_total_exergy_ph_ch(stream) for stream in hp_in_streams]
E_out_hp_terms = [_total_exergy_ph_ch(stream) for stream in hp_out_streams]

E_in_hp = sum(E_in_hp_terms) if all(v is not None for v in E_in_hp_terms) else None
E_out_hp = sum(E_out_hp_terms) if all(v is not None for v in E_out_hp_terms) else None
Ed_hp_bal = (E_in_hp - E_out_hp) if (E_in_hp is not None and E_out_hp is not None) else None

# --- Functional Ef / Ep for KOLHP
m12 = _get_val(s12_hp, "m")
m13 = _get_val(s13_hp, "m")
m15 = _get_val(s15_hp, "m")
m17 = _get_val(s17_hp, "m")

eM12 = _get_val(s12_hp, "e_M")
eM13 = _get_val(s13_hp, "e_M")
eM15 = _get_val(s15_hp, "e_M")
eM17 = _get_val(s17_hp, "e_M")

eT12 = _get_val(s12_hp, "e_T")
eT13 = _get_val(s13_hp, "e_T")
eT15 = _get_val(s15_hp, "e_T")
eT17 = _get_val(s17_hp, "e_T")

eCH12 = _get_val(s12_hp, "e_CH")
eCH13 = _get_val(s13_hp, "e_CH")
eCH15 = _get_val(s15_hp, "e_CH")
eCH17 = _get_val(s17_hp, "e_CH")

E34_tot = _total_exergy_ph_ch(s34_hp)
E33_tot = _total_exergy_ph_ch(s33_hp)

Ef_n2_loop_hp = None
Ef_druck_s13_hp = None
Ef_therm_s15_hp = None
Ef_hp = None

Ep_ch_hp = None
Ep_therm_hp = None
Ep_mech_hp = None
Ep_hp = None
Ed_hp_formel = None

# Fuel terms
if E34_tot is not None and E33_tot is not None:
    Ef_n2_loop_hp = E34_tot - E33_tot

if all(v is not None for v in [m13, eM12, eM13]):
    Ef_druck_s13_hp = float(m13) * (float(eM12) - float(eM13))

if all(v is not None for v in [m15, eT12, eT15]):
    Ef_therm_s15_hp = float(m15) * (float(eT12) - float(eT15))

if Ef_n2_loop_hp is not None and Ef_druck_s13_hp is not None and Ef_therm_s15_hp is not None:
    Ef_hp = Ef_n2_loop_hp + Ef_druck_s13_hp + Ef_therm_s15_hp

# Product terms
if all(v is not None for v in [m13, m15, m17, eCH12, eCH13, eCH15, eCH17]):
    Ep_ch_hp = (
        float(m13) * (float(eCH13) - float(eCH12))
        + float(m15) * (float(eCH15) - float(eCH12))
        + float(m17) * (float(eCH17) - float(eCH12))
    )

if all(v is not None for v in [m13, m17, eT12, eT13, eT17]):
    Ep_therm_hp = float(m13) * (float(eT13) - float(eT12)) + float(m17) * (float(eT17) - float(eT12))

if all(v is not None for v in [m15, m17, eM12, eM15, eM17]):
    Ep_mech_hp = float(m15) * (float(eM15) - float(eM12)) + float(m17) * (float(eM17) - float(eM12))

if Ep_ch_hp is not None and Ep_therm_hp is not None and Ep_mech_hp is not None:
    Ep_hp = Ep_ch_hp + Ep_therm_hp + Ep_mech_hp

if Ef_hp is not None and Ep_hp is not None:
    Ed_hp_formel = Ef_hp - Ep_hp

logging.info("\nKOLHP custom functional calculation (Tesch/SPECO):")
logging.info(f"  Ein  [12,34]         = {E_in_hp} W")
logging.info(f"  Aus  [13,15,17,33]   = {E_out_hp} W")
logging.info(f"  Ed_hp_bal = Ein - Aus= {Ed_hp_bal} W")
logging.info(f"  Ef_n2_loop (34->33)  = {Ef_n2_loop_hp} W")
logging.info(f"  Ef_druck_S13         = {Ef_druck_s13_hp} W")
logging.info(f"  Ef_therm_S15         = {Ef_therm_s15_hp} W")
logging.info(f"  Ef_hp                = {Ef_hp} W")
logging.info(f"  Ep_ch                = {Ep_ch_hp} W")
logging.info(f"  Ep_therm (13,17)     = {Ep_therm_hp} W")
logging.info(f"  Ep_mech  (15,17)     = {Ep_mech_hp} W")
logging.info(f"  Ep_hp                = {Ep_hp} W")
logging.info(f"  Ed_hp_formel=Ef-Ep   = {Ed_hp_formel} W")
if Ed_hp_bal is not None and Ed_hp_formel is not None:
    logging.info(f"  Delta (Ed_bal - Ed_formel) = {Ed_hp_bal - Ed_hp_formel} W")

if kolhp_comp is not None:
    try:
        kolhp_comp.E_F_custom = Ef_hp
        kolhp_comp.E_P_custom = Ep_hp
        kolhp_comp.E_D_custom = Ed_hp_formel
        kolhp_comp.epsilon_custom = (Ep_hp / Ef_hp) if (Ef_hp and Ef_hp != 0) else None
    except Exception:
        pass

# Compact comparison for KOLHP
_log_component_custom_compare('KOLHP', kolhp_comp)


# Log calculated exergy results for all components
logging.info("\n" + "="*100)
logging.info("COMPONENT EXERGY RESULTS")
logging.info("="*100)
for comp_name, component in ean.components.items():
    if component.__class__.__name__ != "CycleCloser":
        E_F = getattr(component, 'E_F', None)
        E_P = getattr(component, 'E_P', None)
        E_D = getattr(component, 'E_D', None)
        epsilon = getattr(component, 'epsilon', None)
        # Safe formatting for possibly-missing values
        def _fmt_w(v):
            return f"{v:.2f} W" if isinstance(v, (int, float)) else ("N/A" if v is None else str(v))

        epsilon_str = f"{epsilon:.4f}" if isinstance(epsilon, (int, float)) else "N/A"

        result_msg = (
            f"Component results | {comp_name} ({component.__class__.__name__}) | "
            f"E_F={_fmt_w(E_F)} | E_P={_fmt_w(E_P)} | E_D={_fmt_w(E_D)} | eps={epsilon_str}"
        )

        # Include custom user-defined exergy results when present on the component
        E_P_custom = getattr(component, 'E_P_custom', None)
        E_F_custom = getattr(component, 'E_F_custom', None)
        E_D_custom = getattr(component, 'E_D_custom', None)
        eps_custom = getattr(component, 'epsilon_custom', None)
        custom_parts = []
        if E_F_custom is not None or E_P_custom is not None or E_D_custom is not None or eps_custom is not None:
            custom_parts.append("[custom]")
            if E_F_custom is not None:
                custom_parts.append(f"E_F_custom={_fmt_w(E_F_custom)}")
            if E_P_custom is not None:
                custom_parts.append(f"E_P_custom={_fmt_w(E_P_custom)}")
            if E_D_custom is not None:
                custom_parts.append(f"E_D_custom={_fmt_w(E_D_custom)}")
            if eps_custom is not None:
                eps_c = f"{eps_custom:.6g}" if isinstance(eps_custom, (int, float)) else str(eps_custom)
                custom_parts.append(f"eps_custom={eps_c}")
            result_msg = result_msg + " | " + " ".join(custom_parts)

        logging.info(result_msg)

# No-mix overall aggregation: for each component use either full custom triplet
# (E_F_custom, E_P_custom, E_D_custom) or full standard triplet (E_F, E_P, E_D).
# E_L is handled as additional additive term (custom if available, else standard, else 0).
resolved_components = []
for comp_name, component in ean.components.items():
    if component.__class__.__name__ == "CycleCloser":
        continue
    if str(comp_name).strip().upper() == "RECON":
        continue

    E_F_std = getattr(component, 'E_F', None)
    E_P_std = getattr(component, 'E_P', None)
    E_D_std = getattr(component, 'E_D', None)
    E_L_std = getattr(component, 'E_L', None)
    E_F_custom = getattr(component, 'E_F_custom', None)
    E_P_custom = getattr(component, 'E_P_custom', None)
    E_D_custom = getattr(component, 'E_D_custom', None)
    E_L_custom = getattr(component, 'E_L_custom', None)

    use_custom = all(v is not None for v in (E_F_custom, E_P_custom, E_D_custom))
    if use_custom:
        source = "custom"
        E_F_sel, E_P_sel, E_D_sel = E_F_custom, E_P_custom, E_D_custom
        E_L_sel = E_L_custom if E_L_custom is not None else 0.0
    else:
        source = "standard"
        E_F_sel, E_P_sel, E_D_sel = E_F_std, E_P_std, E_D_std
        E_L_sel = E_L_std if E_L_std is not None else 0.0

    resolved_components.append((str(comp_name), source, E_F_sel, E_P_sel, E_D_sel, E_L_sel))

sum_E_F_sel = sum(v for _, _, v, _, _, _ in resolved_components if isinstance(v, (int, float)) and math.isfinite(v))
sum_E_P_sel = sum(v for _, _, _, v, _, _ in resolved_components if isinstance(v, (int, float)) and math.isfinite(v))
sum_E_D_sel = sum(v for _, _, _, _, v, _ in resolved_components if isinstance(v, (int, float)) and math.isfinite(v))
sum_E_L_sel = sum(v for _, _, _, _, _, v in resolved_components if isinstance(v, (int, float)) and math.isfinite(v))
closure_sel = sum_E_F_sel - sum_E_P_sel - sum_E_D_sel
closure_sel_with_losses = sum_E_F_sel - sum_E_P_sel - (sum_E_D_sel + sum_E_L_sel)

logging.info("\n" + "="*100)
logging.info("NO-MIX OVERALL (DISPLAY CONSISTENT)")
logging.info("="*100)
logging.info(
    "Rule: per component use CUSTOM iff (E_F_custom, E_P_custom, E_D_custom) all exist; otherwise STANDARD."
)
logging.info(f"Sum selected E_F = {sum_E_F_sel:.2f} W")
logging.info(f"Sum selected E_P = {sum_E_P_sel:.2f} W")
logging.info(f"Sum selected E_D = {sum_E_D_sel:.2f} W")
logging.info(f"Sum selected E_L = {sum_E_L_sel:.2f} W")
logging.info(f"Closure (Sum E_F - Sum E_P - Sum E_D) = {closure_sel:.2f} W")
logging.info(f"Closure (Sum E_F - Sum E_P - Sum(E_D+E_L)) = {closure_sel_with_losses:.2f} W")
sys_diff = None
if isinstance(E_F_tot_final, (int, float)) and isinstance(E_P_tot_final, (int, float)):
    sys_diff = E_F_tot_final - E_P_tot_final
    logging.info(f"System diff (E_F_tot_final - E_P_tot_final) = {sys_diff:.2f} W")
    logging.info(f"Check vs Sum(E_D+E_L): diff = {sys_diff - (sum_E_D_sel + sum_E_L_sel):.2f} W")
logging.info("="*100)

logging.info("\n" + "="*100)
logging.info("OVERALL SYSTEM RESULTS")
logging.info("="*100)
logging.info(f"Total E_F = {ean.E_F:.2f} W")
logging.info(f"Total E_F (custom final) = {E_F_tot_final:.2f} W" if isinstance(E_F_tot_final, (int, float)) else "Total E_F (custom final) = N/A")
logging.info(f"Total E_P (custom final) = {E_P_tot_final:.2f} W" if isinstance(E_P_tot_final, (int, float)) else "Total E_P (custom final) = N/A")
logging.info(f"Total E_L (custom final) = {E_L_tot_final:.2f} W" if isinstance(E_L_tot_final, (int, float)) else "Total E_L (custom final) = N/A")
logging.info(f"Total E_D (custom final) = {E_D_tot_final:.2f} W" if isinstance(E_D_tot_final, (int, float)) else "Total E_D (custom final) = N/A")
logging.info(f"Total E_P = {ean.E_P:.2f} W")
logging.info(f"Total E_D = {ean.E_D:.2f} W")
logging.info(f"Total E_L = {ean.E_L:.2f} W")
epsilon_total = f"{ean.epsilon:.4f}" if ean.epsilon is not None else "N/A"
logging.info(f"System Efficiency eps = {epsilon_total}")
logging.info("="*100 + "\n")

# --- Automatic validation check (requested residual closure) ---
logging.info("\n" + "="*100)
logging.info("VALIDIERUNG (RESIDUUM-CHECK)")
logging.info("="*100)

Summe_Teile = None
System_Diff = None
Residuum = None

if isinstance(sum_E_D_sel, (int, float)) and isinstance(sum_E_L_sel, (int, float)):
    Summe_Teile = sum_E_D_sel + sum_E_L_sel

if isinstance(E_F_tot_final, (int, float)) and isinstance(E_P_tot_final, (int, float)):
    System_Diff = E_F_tot_final - E_P_tot_final

if isinstance(Summe_Teile, (int, float)) and isinstance(System_Diff, (int, float)):
    Residuum = System_Diff - Summe_Teile

logging.info(f"Summe_Teile = sum(E_D_k) + sum(E_L_k) = {Summe_Teile} W")
logging.info(f"System_Diff = E_F_tot - E_P_tot = {System_Diff} W")
logging.info(f"Residuum = System_Diff - Summe_Teile = {Residuum} W")

if isinstance(Residuum, (int, float)):
    logging.info(f"|Residuum| = {abs(Residuum):.2f} W")
    if abs(Residuum) <= 1e5:
        logging.info("Bewertung: nahezu geschlossen (<= 0.1 MW).")
    else:
        logging.info("Bewertung: nicht geschlossen (> 0.1 MW).")
else:
    logging.info("Bewertung: nicht berechenbar (fehlende Groessen).")

logging.info("="*100 + "\n")

# Export JSON in the same structure as examples/json_example/example.json
output_path = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "examples", "json_example", "aspen_luftzerlegung.json")
)
os.makedirs(os.path.dirname(output_path), exist_ok=True)
export_data = ean._serialize()
json_payload = {
    "components": export_data.get("components", {}),
    "connections": export_data.get("connections", {}),
    "ambient_conditions": export_data.get("ambient_conditions", {}),
}

# Inject custom exergy results (from test calculations) into JSON export for traceability
custom_exergy = {}
for comp_name, comp in ean.components.items():
    E_F_custom = getattr(comp, 'E_F_custom', None)
    E_P_custom = getattr(comp, 'E_P_custom', None)
    E_D_custom = getattr(comp, 'E_D_custom', None)
    E_L_custom = getattr(comp, 'E_L_custom', None)
    eps_custom = getattr(comp, 'epsilon_custom', None)
    if any(v is not None for v in (E_F_custom, E_P_custom, E_D_custom, E_L_custom, eps_custom)):
        custom_exergy[str(comp_name)] = {
            "E_F_custom": E_F_custom,
            "E_P_custom": E_P_custom,
            "E_D_custom": E_D_custom,
            "E_L_custom": E_L_custom,
            "epsilon_custom": eps_custom,
        }

if custom_exergy:
    json_payload["custom_exergy"] = custom_exergy
with open(output_path, "w", encoding="utf-8") as json_file:
    json.dump(json_payload, json_file, indent=4)

# Export LaTeX table with all material stream data
def _latex_escape(value: str) -> str:
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    for key, repl in replacements.items():
        value = value.replace(key, repl)
    return value


def _format_value(value):
    if value is None:
        return "-"
    if isinstance(value, (int, float)):
        # Allow optional full-precision output when requested
        if globals().get("NO_ROUNDING", False):
            x = float(value)
            s = format(x, ".17g")
            return s.replace(".", ",")
        # Thesis table formatting: no scientific notation and at most two decimals.
        x = round(float(value), 2)
        if abs(x) < 1e-9:
            return "0"
        text = f"{x:.2f}".rstrip("0").rstrip(".")
        return text.replace(".", ",") if text else "0"
    return _latex_escape(str(value))


def _format_molfrac_value(value):
    if value is None:
        return "-"
    if isinstance(value, (int, float)):
        x = float(value)
        if abs(x) < 1e-12:
            return "0"
        if globals().get("NO_ROUNDING", False):
            s = format(x, ".17g")
            return s.replace(".", ",")
        # Composition formatting by magnitude for readable thesis tables.
        ax = abs(x)
        if ax >= 1e-2:
            text = f"{x:.4f}"
        elif ax >= 1e-4:
            text = f"{x:.6f}"
        else:
            return "<1e-6"

        # Remove trailing zeros for non-scientific notation.
        if "e" not in text and "E" not in text:
            text = text.rstrip("0").rstrip(".")
            if text in {"", "-0"}:
                text = "0"

        return text.replace(".", ",")
    return _latex_escape(str(value))


def _format_value_fixed(value, ndigits: int):
    """Format a numeric value with a fixed number of decimals (no scientific notation).

    Returns a string with a comma as decimal separator. Caller may pass None and
    should handle it if desired.
    """
    if value is None:
        return ""
    try:
        x = float(value)
        if not math.isfinite(x):
            return ""
        if globals().get("NO_ROUNDING", False):
            s = format(x, ".17g")
            # If caller expects fixed digits, still respect ndigits by trimming/padding
            if ndigits is not None:
                if "e" not in s and "E" not in s and "." in s:
                    # pad or trim fractional part to ndigits if desired
                    intpart, frac = s.split('.', 1) if '.' in s else (s, '')
                    frac = (frac + '0' * ndigits)[:ndigits]
                    s = intpart + ('.' + frac if ndigits > 0 else '')
            return s.replace('.', ',')
        fmt = f"{x:.{ndigits}f}"
        # Remove leading + sign if any, keep negative sign
        if fmt.startswith("+"):
            fmt = fmt[1:]
        return fmt.replace('.', ',')
    except Exception:
        return ""


def _build_streams_latex_table(connections: dict) -> str:
    columns = [
        ("name", "Stream", None),
        ("m", r"$\dot m$", "m_unit"),
        ("n", r"$\dot n$", "n_unit"),
        ("T", r"$T$", "T_unit"),
        ("p", r"$p$", "p_unit"),
        ("h", r"$h$", "h_unit"),
        ("s", r"$s$", "s_unit"),
        ("lfrac", r"$l_{frac}$", "lfrac_unit"),
        ("vfrac_out", r"$v_{frac}$", "vfrac_out_unit"),
        ("e_PH", r"$e_{PH}$", "e_PH_unit"),
        ("e_CH", r"$e_{CH}$", "e_CH_unit"),
        ("e_T", r"$e_T$", "e_T_unit"),
        ("e_M", r"$e_M$", "e_M_unit"),
    ]

    material_streams = [
        conn for conn in connections.values() if conn.get("kind") == "material"
    ]

    def _stream_value(conn: dict, key: str):
        # Aspen exports sometimes leave e_PH empty while e_T and e_M are available.
        # In this case, reconstruct e_PH = e_T + e_M for the LaTeX table output.
        val = conn.get(key)
        if key == "e_PH" and val is None:
            e_t = conn.get("e_T")
            e_m = conn.get("e_M")
            if isinstance(e_t, (int, float)) and isinstance(e_m, (int, float)):
                return float(e_t) + float(e_m)
        return val

    def _sort_key(conn):
        name = str(conn.get("name", ""))
        prefix = ""
        digits = ""
        for ch in name:
            if ch.isdigit():
                digits += ch
            else:
                prefix += ch
        if digits:
            return (prefix, int(digits), name)
        return (prefix, float("inf"), name)

    material_streams.sort(key=_sort_key)

    unit_lookup = {}
    for key, _, unit_key in columns:
        if not unit_key:
            unit_lookup[key] = ""
            continue
        unit = None
        for conn in material_streams:
            unit = conn.get(unit_key)
            if unit:
                break
        if key == "e_PH" and not unit:
            for conn in material_streams:
                unit = conn.get("e_T_unit")
                if unit:
                    break
        unit_lookup[key] = unit or ""

    header = " & ".join(label for _, label, _ in columns) + " \\\\"
    unit_row = " & ".join(
        f"({ _latex_escape(unit_lookup[key]) })" if unit_lookup[key] else ""
        for key, _, _ in columns
    ) + " \\\\"

    rows = []
    for conn in material_streams:
        values = []
        for key, _, _ in columns:
            val = _stream_value(conn, key)
            values.append(_format_value(val))
        rows.append(" & ".join(values) + r" \\")

    col_spec = "l" + "r" * (len(columns) - 1)
    lines = [
        f"\\begin{{longtable}}{{{col_spec}}}",
            r"\caption{Thermodynamische und exergetische Kenngrößen der simulierten Prozessströme des Doppelkolonnenmodells} \\",
        "\\hline",
        header,
        unit_row,
        "\\hline",
        *rows,
        "\\hline",
        "\\end{longtable}",
    ]
    return "\n".join(lines)


def _build_components_work_table(connections: dict, components: dict) -> str:
    # Build a simple table of components that have power connections (work streams).
    # connections: exported connections dict (keys -> conn dict)
    # components: mapping of component name -> component object (to get type)
    power_conns = [ (k, v) for k, v in connections.items() if isinstance(v, dict) and v.get("kind") == "power" ]
    # map component name -> summed energy flow (W)
    comp_power = {}
    for name, conn in power_conns:
        val = conn.get("energy_flow") or conn.get("E")
        if not isinstance(val, (int, float)):
            continue
        # associate to source_component if available, else target
        comp = conn.get("source_component") or conn.get("target_component")
        if not comp:
            continue
        comp_power[comp] = comp_power.get(comp, 0.0) + float(val)

    # Only include components that exist in the parsed components dict and have a non-zero power
    rows = []
    for comp_name, w_val in sorted(comp_power.items()):
        if comp_name not in components:
            # still allow if name matches ignoring case
            if not any(str(k) == str(comp_name) for k in components.keys()):
                continue
        comp_obj = components.get(comp_name) or next((c for n, c in components.items() if str(n) == str(comp_name)), None)
        comp_type = comp_obj.__class__.__name__ if comp_obj is not None else ""
        # For turbines, force negative display
        if "turbine" in comp_type.lower() or str(comp_name).upper().startswith("T"):
            display_val = -abs(w_val)
        else:
            display_val = w_val
        rows.append(" & ".join([
            _latex_escape(str(comp_name)),
            _latex_escape(comp_type),
            _format_value(display_val),
        ]) + r" \\")

    col_spec = "lrr"
    header = " & ".join(["Component", "Type", r"$\dot W$"]) + " " + r"\\"
    unit_row = " & ".join(["", "", "(W)"]) + " " + r"\\"
    lines = [
        f"\\begin{{longtable}}{{{col_spec}}}",
        r"\caption{Komponenten mit Arbeitsströmen (W)} \\",
        "\\hline",
        header,
        unit_row,
        "\\hline",
        *rows,
        "\\hline",
        "\\end{longtable}",
    ]
    return "\n".join(lines)


def _build_molar_fractions_table(connections: dict) -> str:
    columns = [
        ("name", "Stream", None),
        ("mfn2", r"$x_{N_2}$", "mfn2_unit"),
        ("mfo2", r"$x_{O_2}$", "mfo2_unit"),
        ("mfco", r"$x_{CO_2}$", "mfco_unit"),
        ("mfar", r"$x_{Ar}$", "mfar_unit"),
        ("mfho", r"$x_{H_2O}$", "mfho_unit"),
    ]

    material_streams = [
        conn for conn in connections.values() if conn.get("kind") == "material"
    ]

    def _sort_key(conn):
        name = str(conn.get("name", ""))
        prefix = ""
        digits = ""
        for ch in name:
            if ch.isdigit():
                digits += ch
            else:
                prefix += ch
        if digits:
            return (prefix, int(digits), name)
        return (prefix, float("inf"), name)

    material_streams.sort(key=_sort_key)

    unit_lookup = {}
    for key, _, unit_key in columns:
        if not unit_key:
            unit_lookup[key] = ""
            continue
        unit = None
        for conn in material_streams:
            unit = conn.get(unit_key)
            if unit:
                break
        unit_lookup[key] = unit or ""

    header = " & ".join(label for _, label, _ in columns) + " \\\\"
    unit_row = " & ".join(
        f"({ _latex_escape(unit_lookup[key]) })" if unit_lookup[key] else ""
        for key, _, _ in columns
    ) + " \\\\"

    rows = []
    for conn in material_streams:
        values = []
        for key, _, _ in columns:
            val = conn.get(key)
            values.append(_format_molfrac_value(val))
        rows.append(" & ".join(values) + r" \\")

    col_spec = "l" + "r" * (len(columns) - 1)
    lines = [
        f"\\begin{{longtable}}{{{col_spec}}}",
            r"\caption{Stoffliche Zusammensetzung der Prozessströme des Doppelkolonnenmodells} \\",
        "\\hline",
        header,
        unit_row,
        "\\hline",
        *rows,
        "\\hline",
        "\\end{longtable}",
    ]
    return "\n".join(lines)


def _build_component_results_table(components: dict) -> str:
    # keep original column layout; we'll inject custom values into the standard columns
    # compute E_F_tot from available power/material streams for y calculation
    W1 = _power_stream_abs("W1")
    W2 = _power_stream_abs("W2")
    E_S1 = _stream_total_exergy_from_table("S1")
    if all(isinstance(v, (int, float)) for v in [W1, W2, E_S1]):
        E_F_tot = W1 + W2 + E_S1
    else:
        E_F_tot = getattr(ean, "E_F", None)

    rows = []
    # Header and units for component results table (E_L removed)
    header = " & ".join([
        "Component",
        "Type",
        r"$\dot{E}_F$",
        r"$\dot{E}_P$",
        r"$\dot{E}_D$",
        r"$\varepsilon$",
        r"$y_{D,k}$",
        r"$y^*_{D,k}$",
    ]) + " \\\\"
    unit_row = " & ".join(["", "", "(W)", "(W)", "(W)", "(-)", "(-)", "(-)"]) + " \\\\"
    # Support two input formats:
    # - runtime component objects (component instances with attributes)
    # - exported component dicts (as produced by ean._serialize())
    # two-pass: collect display values first (need total absolute E_D for y* normalization)
    display_items = []
    for comp_name, component in components.items():
        # Skip CycleCloser/Splitter and RECON as before
        name_key = str(comp_name).strip()
        if name_key.upper() == "RECON":
            continue

        # Determine if this entry is an exported dict
        if isinstance(component, dict):
            comp_type = component.get("type") or component.get("__class__", "")
            ex = component.get("exergy_results", {}) or {}
            E_F = ex.get("E_F")
            E_P = ex.get("E_P")
            E_D = ex.get("E_D")
            epsilon = ex.get("epsilon")
            comp_class_name = comp_type
            # custom overrides (not present in exported dicts)
            E_F_custom = None
            E_P_custom = None
            E_D_custom = None
            E_L_custom = None
            epsilon_custom = None
        else:
            # runtime object path
            if component.__class__.__name__ in {"CycleCloser", "Splitter"}:
                continue
            comp_class_name = component.__class__.__name__
            E_F = getattr(component, "E_F", None)
            E_P = getattr(component, "E_P", None)
            E_D = getattr(component, "E_D", None)
            E_L = getattr(component, "E_L", None)
            epsilon = getattr(component, "epsilon", None)
            E_F_custom = getattr(component, "E_F_custom", None)
            E_P_custom = getattr(component, "E_P_custom", None)
            E_D_custom = getattr(component, "E_D_custom", None)
            E_L_custom = getattr(component, "E_L_custom", None)
            epsilon_custom = getattr(component, "epsilon_custom", None)

        # Use custom display values only when custom triplet is numeric and finite
        use_custom = all(isinstance(v, (int, float)) and math.isfinite(v) for v in (E_F_custom, E_P_custom, E_D_custom))
        # Special-case: for MIX enforce use of custom values if any custom value was computed
        try:
            name_up = str(comp_name).strip().upper()
        except Exception:
            name_up = ""
        if name_up == "MIX" and any(isinstance(v, (int, float)) and math.isfinite(v) for v in (E_F_custom, E_P_custom, E_D_custom)):
            use_custom = True
        if use_custom:
            display_E_F = E_F_custom
            display_E_P = E_P_custom
            display_E_D = E_D_custom
            display_E_L = E_L_custom if E_L_custom is not None else 0.0
            if epsilon_custom is not None:
                display_epsilon = epsilon_custom
            else:
                display_epsilon = (display_E_P / display_E_F) if (display_E_F not in (None, 0)) else None
        else:
            display_E_F = E_F
            display_E_P = E_P
            display_E_D = E_D
            display_E_L = E_L if 'E_L' in locals() and E_L is not None else 0.0
            display_epsilon = epsilon

        # collect for second pass (E_L omitted)
        display_items.append((comp_name, comp_class_name, display_E_F, display_E_P, display_E_D, display_epsilon))

    # compute total absolute E_D for y* normalization
    E_D_tot = sum(abs(v) for _, _, _, _, v, _ in display_items if isinstance(v, (int, float)))

    # Prefer the module-level custom overall total when available
    if not E_D_tot:
        if isinstance(E_D_tot_final, (int, float)) and math.isfinite(E_D_tot_final) and E_D_tot_final != 0:
            E_D_tot = abs(E_D_tot_final)

    # Fallback: if still zero or missing, compute total directly from the raw component objects/dicts
    if not E_D_tot:
        total_abs = 0.0
        for comp_name, component in components.items():
            if isinstance(component, dict):
                ex = component.get("exergy_results", {}) or {}
                v = ex.get("E_D")
            else:
                v = getattr(component, 'E_D', None)
            if isinstance(v, (int, float)) and math.isfinite(v):
                total_abs += abs(v)
        if total_abs:
            E_D_tot = total_abs

    # Debug: log totals used for normalization and per-component values
    try:
        logging.info(f"[DEBUG] Component table: E_F_tot={E_F_tot}, E_D_tot={E_D_tot}")
        # Also print a concise debug line to stdout to ensure visibility in captured logs
        print(f"[DEBUG-TABLE] E_F_tot={E_F_tot} E_D_tot={E_D_tot}")
        for idx, (comp_name, comp_class_name, display_E_F, display_E_P, display_E_D, display_epsilon) in enumerate(display_items):
            y_val = (display_E_D / E_F_tot) if (
                isinstance(display_E_D, (int, float)) and isinstance(E_F_tot, (int, float)) and E_F_tot != 0
            ) else None
            y_star_val = (abs(display_E_D) / E_D_tot) if (isinstance(display_E_D, (int, float)) and E_D_tot and E_D_tot != 0) else None
            logging.info(
                "[DEBUG] comp=%s type=%s E_F=%s E_P=%s E_D=%s eps=%s y=%s y*=%s",
                comp_name,
                comp_class_name,
                _format_value(display_E_F),
                _format_value(display_E_P),
                _format_value(display_E_D),
                (f"{display_epsilon:.6g}" if isinstance(display_epsilon, (int, float)) else str(display_epsilon)),
                _format_value_fixed(y_val, 6),
                _format_value_fixed(y_star_val, 6),
            )
            if idx >= 4:
                # limit stdout noise
                break
    except Exception:
        pass

    rows = []
    sum_E_D = 0.0
    sum_y = 0.0
    sum_y_star = 0.0
    for comp_name, comp_class_name, display_E_F, display_E_P, display_E_D, display_epsilon in display_items:
        y_D_k = (display_E_D / E_F_tot) if (
            isinstance(display_E_D, (int, float)) and isinstance(E_F_tot, (int, float)) and E_F_tot != 0
        ) else None
        y_D_k_star = (abs(display_E_D) / E_D_tot) if (isinstance(display_E_D, (int, float)) and E_D_tot and E_D_tot != 0) else None

        if isinstance(display_E_D, (int, float)):
            sum_E_D += display_E_D
        # E_L column removed; no accumulation here
        if isinstance(y_D_k, (int, float)):
            sum_y += y_D_k
        if isinstance(y_D_k_star, (int, float)):
            sum_y_star += y_D_k_star

        rows.append(
            " & ".join([
                _latex_escape(str(comp_name)),
                _latex_escape(str(comp_class_name)),
                _format_value(display_E_F),
                _format_value(display_E_P),
                _format_value(display_E_D),
                _format_value_fixed(display_epsilon, 4) if display_epsilon is not None else "",
                _format_value_fixed(y_D_k, 4),
                _format_value_fixed(y_D_k_star, 4),
            ]) + " \\\\"
        )
    # sum row (only E_D, y_D_k, y*_D_k) — E_L removed
    sum_row_cells = [r"\\textbf{Summe}", "", "", "", _format_value(sum_E_D), "", _format_value_fixed(sum_y, 4), _format_value_fixed(sum_y_star, 4)]

    col_spec = "l" + "l" + "r" * 6
    lines = [
        f"\\begin{{longtable}}{{{col_spec}}}",
        "\\caption{Berechnete exergetische Kennzahlen der Komponenten des Doppelkolonnenmodells} " + r"\\",
        "\\hline",
        header,
        unit_row,
        "\\hline",
        *rows,
        "\\hline",
        " & ".join(sum_row_cells) + r"\\",
        "\\hline",
        "\\end{longtable}",
    ]
    return "\n".join(lines)

    E_F_tot = E_F_tot_final if isinstance(E_F_tot_final, (int, float)) else getattr(ean, "E_F", None)

    # two-pass: collect display values so we can compute E_D total for y* normalization
    display_items = []
    for comp_name, component in components.items():
        if component.__class__.__name__ in {"CycleCloser", "Splitter"}:
            continue
        if str(comp_name).strip().upper() == "RECON":
            continue
        # standard values
        E_F = getattr(component, "E_F", None)
        E_P = getattr(component, "E_P", None)
        E_D = getattr(component, "E_D", None)
        E_L = getattr(component, "E_L", None)
        epsilon = getattr(component, "epsilon", None)

        # if this component has custom values (e.g. RC), use them for display in the standard columns
        E_F_custom = getattr(component, "E_F_custom", None)
        E_P_custom = getattr(component, "E_P_custom", None)
        E_D_custom = getattr(component, "E_D_custom", None)
        E_L_custom = getattr(component, "E_L_custom", None)
        epsilon_custom = getattr(component, "epsilon_custom", None)

        use_custom = all(v is not None for v in (E_F_custom, E_P_custom, E_D_custom))
        if use_custom:
            display_E_F = E_F_custom
            display_E_P = E_P_custom
            display_E_D = E_D_custom
            display_E_L = E_L_custom if E_L_custom is not None else 0.0
            if epsilon_custom is not None:
                display_epsilon = epsilon_custom
            else:
                display_epsilon = (display_E_P / display_E_F) if (display_E_F not in (None, 0)) else None
        else:
            display_E_F = E_F
            display_E_P = E_P
            display_E_D = E_D
            display_E_L = E_L if E_L is not None else 0.0
            display_epsilon = epsilon
            # If epsilon missing, compute from available E_P / E_F when possible
            if display_epsilon is None and isinstance(display_E_P, (int, float)) and isinstance(display_E_F, (int, float)) and display_E_F != 0:
                try:
                    display_epsilon = float(display_E_P) / float(display_E_F)
                except Exception:
                    display_epsilon = None
        # append to display list (E_L omitted from displayed table)
        display_items.append((comp_name, component.__class__.__name__, display_E_F, display_E_P, display_E_D, display_epsilon))

    # compute E_D total for y* normalization
    E_D_tot = sum(abs(v) for _, _, _, _, v, _ in display_items if isinstance(v, (int, float)))

    rows = []
    sum_E_D = 0.0
    sum_y = 0.0
    sum_y_star = 0.0
    for comp_name, comp_class_name, display_E_F, display_E_P, display_E_D, display_epsilon in display_items:
        y_D_k = (display_E_D / E_F_tot) if (
            isinstance(display_E_D, (int, float)) and isinstance(E_F_tot, (int, float)) and E_F_tot != 0
        ) else None
        y_D_k_star = (abs(display_E_D) / E_D_tot) if (isinstance(display_E_D, (int, float)) and E_D_tot and E_D_tot != 0) else None

        # accumulate sums for columns requested
        if isinstance(display_E_D, (int, float)):
            sum_E_D += display_E_D
        # E_L column removed from displayed table
        if isinstance(y_D_k, (int, float)):
            sum_y += y_D_k
        if isinstance(y_D_k_star, (int, float)):
            sum_y_star += y_D_k_star

        rows.append(
            " & ".join([
                _latex_escape(str(comp_name)),
                _latex_escape(comp_class_name),
                _format_value(display_E_F),
                _format_value(display_E_P),
                _format_value(display_E_D),
                _format_value_fixed(display_epsilon, 4) if display_epsilon is not None else "",
                _format_value_fixed(y_D_k, 4),
                _format_value_fixed(y_D_k_star, 4),
            ]) + " \\\\"
        )
    # build sum row: E_L omitted from displayed table
    sum_row_cells = [r"\textbf{Summe}", "", "", "", _format_value(sum_E_D), "", _format_value_fixed(sum_y, 4), _format_value_fixed(sum_y_star, 4)]

    col_spec = "l" + "l" + "r" * 6
    lines = [
        f"\\begin{{longtable}}{{{col_spec}}}",
        "\\caption{Berechnete exergetische Kennzahlen der Komponenten des Doppelkolonnenmodells} " + r"\\",
        "\\hline",
        header,
        unit_row,
        "\\hline",
        *rows,
        "\\hline",
        " & ".join(sum_row_cells) + r"\\",
        "\\hline",
        "\\end{longtable}",
    ]
    return "\n".join(lines)


def _build_global_check_table(components: dict) -> str:
    def _find_stream_conn(stream_name: str):
        conn_direct = ean.connections.get(stream_name)
        if isinstance(conn_direct, dict):
            return conn_direct
        for key, conn in ean.connections.items():
            if not isinstance(conn, dict):
                continue
            name = str(conn.get("name", key))
            if name == stream_name or str(key) == stream_name:
                return conn
        return None

    def _stream_total_exergy_from_table(stream_name: str):
        conn = _find_stream_conn(stream_name)
        if not isinstance(conn, dict):
            return None
        m_val = conn.get("m")
        e_ph = conn.get("e_PH")
        e_ch = conn.get("e_CH")
        if all(isinstance(v, (int, float)) for v in [m_val, e_ph, e_ch]):
            return m_val * (e_ph + e_ch)
        return None

    display_by_name = {}
    for comp_name, component in components.items():
        if component.__class__.__name__ in {"CycleCloser", "Splitter"}:
            continue
        if str(comp_name).strip().upper() == "RECON":
            continue

        E_F = getattr(component, "E_F", None)
        E_P = getattr(component, "E_P", None)
        E_D = getattr(component, "E_D", None)
        E_L = getattr(component, "E_L", None)

        E_F_custom = getattr(component, "E_F_custom", None)
        E_P_custom = getattr(component, "E_P_custom", None)
        E_D_custom = getattr(component, "E_D_custom", None)
        E_L_custom = getattr(component, "E_L_custom", None)

        use_custom = all(v is not None for v in (E_F_custom, E_P_custom, E_D_custom))
        if use_custom:
            display_E_F = E_F_custom
            display_E_P = E_P_custom
            display_E_D = E_D_custom
            display_E_L = E_L_custom if E_L_custom is not None else 0.0
        else:
            display_E_F = E_F
            display_E_P = E_P
            display_E_D = E_D
            display_E_L = E_L if E_L is not None else 0.0

        display_by_name[str(comp_name)] = {
            "E_F": display_E_F,
            "E_P": display_E_P,
            "E_D": display_E_D,
            "E_L": display_E_L,
        }

    discharge_streams = ["S7", "S9", "S10", "S25", "S28"]
    discharge_terms = [(_name, _stream_total_exergy_from_table(_name)) for _name in discharge_streams]
    discharge_total = sum(v for _, v in discharge_terms if isinstance(v, (int, float)))
    boundary_discharge_streams = ["S25", "S28"]
    boundary_discharge_terms = [(_name, _stream_total_exergy_from_table(_name)) for _name in boundary_discharge_streams]
    discharge_total_boundary = sum(v for _, v in boundary_discharge_terms if isinstance(v, (int, float)))

    sum_E_D_table = sum(
        data["E_D"] for data in display_by_name.values()
        if isinstance(data.get("E_D"), (int, float))
    )
    sum_E_L_components = sum(
        data["E_L"] for data in display_by_name.values()
        if isinstance(data.get("E_L"), (int, float))
    )
    sum_E_L_table = sum_E_L_components + discharge_total_boundary

    E_F_LK1 = (display_by_name.get("LK1") or {}).get("E_F")
    E_F_LK2 = (display_by_name.get("LK2") or {}).get("E_F")
    E_F_PK1 = (display_by_name.get("PK1") or {}).get("E_F")
    turbine_component = components.get("T") or next(
        (comp for name, comp in components.items() if str(name).strip().upper() == "T"),
        None,
    )
    W_T = None
    if turbine_component is not None:
        P_val = getattr(turbine_component, "P", None)
        if isinstance(P_val, (int, float)):
            W_T = abs(P_val)
    if W_T is None:
        W_T = (display_by_name.get("T") or {}).get("E_P")
    E_S1 = _stream_total_exergy_from_table("S1")
    E_S32 = _stream_total_exergy_from_table("S32")

    E_in = None
    if all(isinstance(v, (int, float)) for v in [E_F_LK1, E_F_LK2, E_F_PK1, E_S1]):
        E_in = E_F_LK1 + E_F_LK2 + E_F_PK1 + E_S1

    E_out = None
    if all(isinstance(v, (int, float)) for v in [E_S32, W_T]):
        E_out = E_S32 + W_T

    sum_losses_total = None
    if all(isinstance(v, (int, float)) for v in [sum_E_D_table, sum_E_L_table]):
        sum_losses_total = sum_E_D_table + sum_E_L_table

    balance_diff = None
    if all(isinstance(v, (int, float)) for v in [E_in, E_out, sum_losses_total]):
        balance_diff = E_in - (E_out + sum_losses_total)

    balance_diff_pct = None
    if isinstance(balance_diff, (int, float)) and isinstance(E_in, (int, float)) and E_in != 0:
        balance_diff_pct = 100.0 * balance_diff / E_in

    E_F_LKPK = None
    if all(isinstance(v, (int, float)) for v in [E_F_LK1, E_F_LK2, E_F_PK1]):
        E_F_LKPK = E_F_LK1 + E_F_LK2 + E_F_PK1

    sum_out = None
    if all(isinstance(v, (int, float)) for v in [E_out, sum_losses_total]):
        sum_out = E_out + sum_losses_total

    def _format_int_de(value):
        if not isinstance(value, (int, float)):
            return "-"
        if globals().get("NO_ROUNDING", False):
            s = format(float(value), ".17g")
            return s.replace(".", ",")
        return f"{int(round(value)):,}"

    def _format_pct_de(value):
        if not isinstance(value, (int, float)):
            return "-"
        if globals().get("NO_ROUNDING", False):
            s = format(float(value), ".17g")
            return s.replace(".", ",")
        return f"{value:.2f}".replace(".", ",")

    delta_text = "-"
    if isinstance(balance_diff, (int, float)) and isinstance(balance_diff_pct, (int, float)):
        delta_text = f"{_format_int_de(balance_diff)} ({_format_pct_de(balance_diff_pct)} \\%)"

    row_end = r"\\"
    lines = [
        r"\begin{longtable}{llr | llr}",
        r"\caption{Exergetische Bilanz des Gesamtsystems des Doppelkolonnenmodells} " + row_end,
        r"\hline",
        r"\multicolumn{3}{l|}{\textbf{Exergetischer Aufwand ($E_{in}$)}} & \multicolumn{3}{l}{\textbf{Exergetischer Verbleib}} " + row_end,
        r"\hline",
        r"Posten & Quelle & Wert (W) & Posten & Typ & Wert (W) " + row_end,
        r"\hline",
        f"Strom 1 & $\\dot{{E}}_{{S1}}$ & {_format_int_de(E_S1)} & Produkt N2 & $\\dot{{E}}_{{S32}}$ & {_format_int_de(E_S32)} " + row_end,
        f"Verdichtung & $E_{{F,LK+PK}}$ & {_format_int_de(E_F_LKPK)} & Turbinenarbeit & $\\dot{{W}}_{{T}}$ & {_format_int_de(W_T)} " + row_end,
        f" &  &  & Exerget. Vernichtung & $\\sum \\dot{{E}}_{{D,k}}$ & {_format_int_de(sum_E_D_table)} " + row_end,
        f" &  &  & Austrittsverluste & $\\sum \\dot{{E}}_{{L,ges}}$ & {_format_int_de(sum_E_L_table)} " + row_end,
        r"\hline",
        f"\\textbf{{Summe Ein}} &  & \\textbf{{{_format_int_de(E_in)}}} & \\textbf{{Summe Aus}} &  & \\textbf{{{_format_int_de(sum_out)}}} " + row_end,
        r"\hline",
        f"\\multicolumn{{3}}{{l}}{{}} & \\textbf{{Differenz ($\\Delta$)}} &  & \\textbf{{{delta_text}}} " + row_end,
        r"\hline",
        r"\end{longtable}",
    ]
    return "\n".join(lines)


def _get_block_map_double() -> dict:
    return {
        "gekuehlte Luftverdichtung": ["ZK1", "LK2"],
        "Luftverdichtung": ["LK1", "ZK1", "LK2"],
        "Gasaufbereitung": ["ZK2", "GW1", "GW2"],
        "Verdichtungs- und Reinigungsblock": ["LK1", "ZK1", "LK2", "ZK2", "GW1", "GW2"],
        "Hauptwaermeuebertrager": ["MW"],
        "Rektifikation": ["KOLHP", "KOLLP", "RC1", "RC2", "D1", "D2", "D3"],
        "Rest": ["T", "D4"],
    }


def _compute_block_ed_sums(components: dict, block_map: dict) -> dict:
    alias_map = {
        "MW": ["MW", "MH"],
        "MH": ["MH", "MW"],
        "RC": ["RC", "RECO"],
        "RC1": ["RC1", "RC"],
        "T": ["T", "TURB"],
        "TURB": ["TURB", "T"],
    }

    def _display_ed(comp_name: str):
        candidates = alias_map.get(comp_name, [comp_name])

        component = None
        for cand in candidates:
            component = components.get(cand)
            if component is not None:
                break

        if component is None:
            return 0.0

        E_D = getattr(component, "E_D", None)
        E_D_custom = getattr(component, "E_D_custom", None)
        if isinstance(E_D_custom, (int, float)):
            return float(E_D_custom)
        if isinstance(E_D, (int, float)):
            return float(E_D)
        return 0.0

    return {
        block_name: sum(_display_ed(name) for name in comp_list)
        for block_name, comp_list in block_map.items()
    }


def _build_block_ed_table(components: dict) -> str:
    block_map = _get_block_map_double()
    ed_sums = _compute_block_ed_sums(components, block_map)

    rows = []
    for block_name in block_map.keys():
        rows.append(" & ".join([block_name, _format_value(ed_sums.get(block_name, 0.0))]) + r" \\")

    lines = [
        r"\begin{longtable}{lr}",
        r"\caption{Summierte Exergievernichtung der Funktionsbloecke des Doppelkolonnenmodells} \\",
        r"\hline",
        r"Block & Summe $\dot{E}_D$ (W) \\",
        r"\hline",
        *rows,
        r"\hline",
        r"\end{longtable}",
    ]
    return "\n".join(lines)


def _read_block_ed_table(tex_path: str) -> dict:
    result = {}
    if not os.path.exists(tex_path):
        return result

    with open(tex_path, "r", encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line or line.startswith("\\"):
                continue
            if line.startswith("Block") or "&" not in line:
                continue

            parts = [p.strip() for p in line.replace("\\\\", "").split("&")]
            if len(parts) != 2:
                continue

            block_name, val_raw = parts
            try:
                val_norm = val_raw.strip()
                if "," in val_norm and "." in val_norm:
                    val_norm = val_norm.replace(".", "").replace(",", ".")
                elif "," in val_norm:
                    val_norm = val_norm.replace(",", ".")
                result[block_name] = float(val_norm)
            except ValueError:
                result[block_name] = 0.0

    return result


def _build_block_ed_comparison_table(single_sums: dict, double_sums: dict) -> str:
    ordered_blocks = list(_get_block_map_double().keys())
    rows = []
    for block_name in ordered_blocks:
        s_val = single_sums.get(block_name, 0.0)
        d_val = double_sums.get(block_name, 0.0)
        rows.append(" & ".join([block_name, _format_value(s_val), _format_value(d_val)]) + r" \\")

    lines = [
        r"\begin{longtable}{lrr}",
        r"\caption{Summierte Exergievernichtung der Funktionsbloecke fuer Single- und Doppelkolonnenmodell} \\",
        r"\hline",
        r"Block & Summe $\dot{E}_D$ Single (W) & Summe $\dot{E}_D$ Doppel (W) \\",
        r"\hline",
        *rows,
        r"\hline",
        r"\end{longtable}",
    ]
    return "\n".join(lines)


def _collect_components(connections: dict, composition_key: str) -> list[str]:
    components = set()
    for conn in connections.values():
        if conn.get("kind") != "material":
            continue
        comp = conn.get(composition_key) or {}
        components.update(comp.keys())
    return sorted(components)

def _build_composition_table(connections: dict, composition_key: str, caption: str, label: str) -> str:
    material_streams = [
        conn for conn in connections.values() if conn.get("kind") == "material"
    ]

    def _sort_key(conn):
        name = conn.get("name", "")
        try:
            return (0, int(str(name)))
        except (ValueError, TypeError):
            return (1, str(name))

    material_streams.sort(key=_sort_key)
    components = _collect_components(connections, composition_key)

    if not components:
        return ""

    header = " & ".join(["Stream", *components]) + r" \\\\"
    rows = []
    for conn in material_streams:
        values = [conn.get("name", "-")]
        comp = conn.get(composition_key) or {}
        for comp_name in components:
            values.append(_format_value(comp.get(comp_name)))
        rows.append(" & ".join(values) + r" \\")

    col_spec = "l" + "r" * len(components)
    lines = [
        r"\\begin{table}[ht]",
        r"\\centering",
        rf"\\begin{{tabular}}{{{col_spec}}}",
        r"\\hline",
        header,
        r"\\hline",
        *rows,
        r"\\hline",
        r"\\end{tabular}",
        rf"\\caption{{{caption}}}",
        rf"\\label{{{label}}}",
        r"\\end{table}",
        "",
    ]
    return "\n".join(lines)


latex_output_path = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "..",
        "Overleaf_LaTeX",
        "tabellen",
        "aspen_luftzerlegung_streams.tex",
    )
)
os.makedirs(os.path.dirname(latex_output_path), exist_ok=True)
connections_data = json_payload.get("connections", {})
latex_table = _build_streams_latex_table(connections_data)
with open(latex_output_path, "w", encoding="utf-8") as tex_file:
    tex_file.write(latex_table)

components_output_path = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "..",
        "Overleaf_LaTeX",
        "tabellen",
        "aspen_luftzerlegung_components.tex",
    )
)
components_table = _build_component_results_table(ean.components)
print("===COMPONENTS_TABLE_PREVIEW===")
print(components_table)
# Also write a preview file to ensure the generated table is persisted for inspection
preview_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "Overleaf_LaTeX", "tabellen", "aspen_luftzerlegung_components_preview.tex"))
with open(preview_path, "w", encoding="utf-8") as pf:
    pf.write(components_table)
with open(components_output_path, "w", encoding="utf-8") as tex_file:
    tex_file.write(components_table)

# Write components work (W) table
components_work_output_path = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "..",
        "Overleaf_LaTeX",
        "tabellen",
        "aspen_luftzerlegung_components_work.tex",
    )
)
components_work_table = _build_components_work_table(json_payload.get("connections", {}), ean.components)
with open(components_work_output_path, "w", encoding="utf-8") as tex_file:
    tex_file.write(components_work_table)

global_check_output_path = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "..",
        "Overleaf_LaTeX",
        "tabellen",
        # global double table removed per user request
    )
)
# global check table generation removed per user request

block_ed_output_path = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "..",
        "Overleaf_LaTeX",
        "tabellen",
        "aspen_luftzerlegung_blocks_ed.tex",
    )
)
block_ed_table = _build_block_ed_table(ean.components)
with open(block_ed_output_path, "w", encoding="utf-8") as tex_file:
    tex_file.write(block_ed_table)

block_ed_comparison_output_path = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "..",
        "Overleaf_LaTeX",
        "tabellen",
        "aspen_luftzerlegung_blocks_ed_comparison.tex",
    )
)
single_block_path = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "..",
        "Overleaf_LaTeX",
        "tabellen",
        "aspen_luftzerlegung_blocks_ed_single.tex",
    )
)
single_sums = _read_block_ed_table(single_block_path)
double_sums = _compute_block_ed_sums(ean.components, _get_block_map_double())
block_ed_comparison_table = _build_block_ed_comparison_table(single_sums, double_sums)
with open(block_ed_comparison_output_path, "w", encoding="utf-8") as tex_file:
    tex_file.write(block_ed_comparison_table)

molfractions_output_path = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "..",
        "Overleaf_LaTeX",
        "tabellen",
        "aspen_luftzerlegung_streams_molfrac.tex",
    )
)
molfractions_table = _build_molar_fractions_table(connections_data)
with open(molfractions_output_path, "w", encoding="utf-8") as tex_file:
    tex_file.write(molfractions_table)
