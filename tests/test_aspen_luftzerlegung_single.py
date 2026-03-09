import json
import os
import logging
import sys
import math

from exerpy import ExergyAnalysis

# Get the log file path (single-column run)
log_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'parser_run_single.log'))

"""
Logging setup note:
- We avoid opening parser_run_single.log via FileHandler because shell redirection
    (e.g. `python tests/test_aspen_luftzerlegung_single.py > parser_run_single.log 2>&1`) already
    owns the file handle and causes PermissionError on Windows.
- Instead, emit logs to stdout only; the shell captures them into parser_run_single.log.
"""

# Reset existing handlers and configure stdout-only logging
for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)

console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(logging.Formatter('%(message)s'))
logging.root.addHandler(console_handler)
logging.root.setLevel(logging.INFO)

#model_path = r'C:\Users\Felin\Documents\Masterthesis\Code\Exerpy\exerpy\examples\asu_aspen\Singekolonne\Single_Column_Simulation_Final.bkp'
model_path = r"C:\Users\Felin\Documents\Masterthesis\Simulation_Code\GIT\examples\asu_aspen\Singekolonne\Single_Column_Simulation_Final.bkp"


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
E_D_chk = None
if all(isinstance(v, (int, float)) for v in [E_F_chk, E_P_chk, E_L_chk]):
    E_D_chk = E_F_chk - E_P_chk - E_L_chk

logging.info("\nOVERALL SYSTEM CONSISTENCY CHECK:")
logging.info(f"  ean.E_F={ean.E_F}, recomputed={E_F_chk}, diff={None if E_F_chk is None else ean.E_F - E_F_chk}")
logging.info(f"  ean.E_P={ean.E_P}, recomputed={E_P_chk}, diff={None if E_P_chk is None else ean.E_P - E_P_chk}")
logging.info(f"  ean.E_L={ean.E_L}, recomputed={E_L_chk}, diff={None if E_L_chk is None else ean.E_L - E_L_chk}")
logging.info(f"  ean.E_D={ean.E_D}, recomputed={E_D_chk}, diff={None if E_D_chk is None else ean.E_D - E_D_chk}")

# --- Additional RC re-calculation and comparison (sanity check) ---
export_now = ean._serialize()
connections_now = export_now.get("connections", {})

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

def _get_eph_effective(conn):
    if not conn:
        return None
    eph = conn.get("e_PH")
    if eph is not None:
        return eph
    e_t = conn.get("e_T")
    e_m = conn.get("e_M")
    if e_t is not None and e_m is not None:
        return e_t + e_m
    return None

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

# Helper: concise comparison log for a component and its custom values
def _log_component_custom_compare(name: str, comp):
    if comp is None:
        logging.info(f"{name}: component not found")
        return
    E_F = getattr(comp, 'E_F', None)
    E_P = getattr(comp, 'E_P', None)
    E_D = getattr(comp, 'E_D', None)
    E_F_c = getattr(comp, 'E_F_custom', None)
    E_P_c = getattr(comp, 'E_P_custom', None)
    E_D_c = getattr(comp, 'E_D_custom', None)
    eps = getattr(comp, 'epsilon', None)
    eps_c = getattr(comp, 'epsilon_custom', None)

    logging.info("\n--- Compact comparison for %s ---" % name)
    logging.info(f"component | E_F={E_F} W | E_P={E_P} W | E_D={E_D} W | eps={eps}")
    logging.info(f"custom    | E_F={E_F_c} W | E_P={E_P_c} W | E_D={E_D_c} W | eps={eps_c}")
    if E_D is not None and E_D_c is not None:
        logging.info("Ed equal: " + ("YES" if _cmp(E_D, E_D_c) else f"NO (diff={E_D - E_D_c:.6g})"))
    else:
        logging.info("Ed equal: N/A")


# Emit compact comparison block for RC
_log_component_custom_compare('RC', rc_comp)

# --- Custom calculation for MH/MW (MultiHeat) using provided formulas
# Ep = ET11
# Ef = EPH14 - EPH15 + EPH20 - EPH21 + EPH25 - EPH24 + EM8 - EM11 + ET8
mh_comp = (
    ean.components.get("MH")
    or ean.components.get("MW")
    or next((c for n, c in ean.components.items() if str(n).upper().startswith(("MH", "MW"))), None)
)

# find required streams
s8 = _find_conn_by_suffix("8")
s11 = _find_conn_by_suffix("11")
s14 = _find_conn_by_suffix("14")
s15 = _find_conn_by_suffix("15")
s20 = _find_conn_by_suffix("20")
s21 = _find_conn_by_suffix("21")
s24 = _find_conn_by_suffix("24")
s25 = _find_conn_by_suffix("25")

def _total_eph_effective(conn):
    if not conn:
        return None
    eph_tot = _total_from_permass(conn, "e_PH")
    if eph_tot is not None:
        return eph_tot
    et_tot = _total_from_permass(conn, "e_T")
    em_tot = _total_from_permass(conn, "e_M")
    if et_tot is not None and em_tot is not None:
        return et_tot + em_tot
    return None

et8_tot = _total_from_permass(s8, "e_T")
et11_tot = _total_from_permass(s11, "e_T")

eph14_tot = _total_eph_effective(s14)
eph15_tot = _total_eph_effective(s15)
eph20_tot = _total_eph_effective(s20)
eph21_tot = _total_eph_effective(s21)
eph24_tot = _total_eph_effective(s24)
eph25_tot = _total_eph_effective(s25)

em8_tot = _total_from_permass(s8, "e_M")
em11_tot = _total_from_permass(s11, "e_M")

ep_mh = None
ef_mh = None
ed_mh = None

if et11_tot is not None:
    ep_mh = et11_tot

required_ef_terms = [
    eph14_tot,
    eph15_tot,
    eph20_tot,
    eph21_tot,
    eph25_tot,
    eph24_tot,
    em8_tot,
    em11_tot,
    et8_tot,
]
if all(v is not None for v in required_ef_terms):
    ef_mh = (
        (eph14_tot - eph15_tot)
        + (eph20_tot - eph21_tot)
        + (eph25_tot - eph24_tot)
        + (em8_tot - em11_tot)
        + et8_tot
    )

if ef_mh is not None and ep_mh is not None:
    ed_mh = ef_mh - ep_mh

logging.info("\nMH custom calculation (user total balance):")
logging.info(f"  ET11={et11_tot} -> Ep_mh={ep_mh}")
logging.info(
    f"  Ef terms: (EPH14-EPH15)=({eph14_tot}-{eph15_tot}), "
    f"(EPH20-EPH21)=({eph20_tot}-{eph21_tot}), "
    f"(EPH25-EPH24)=({eph25_tot}-{eph24_tot}), "
    f"(EM8-EM11)=({em8_tot}-{em11_tot}), ET8={et8_tot}"
)
logging.info(f"  Ef_mh = {ef_mh}")
logging.info(f"  Ed_mh = Ef_mh - Ep_mh = {ed_mh}")

if mh_comp is not None:
    comp_ed = getattr(mh_comp, "E_D", None)
    if comp_ed is not None and ed_mh is not None:
        logging.info(
            "  Ed match (component vs custom): "
            + ("YES" if _cmp(comp_ed, ed_mh) else f"NO (diff={comp_ed - ed_mh:.6g})")
        )
    else:
        logging.info("  Ed match (component vs custom): N/A")

# Attach to MH component for display/export
if mh_comp is not None:
    try:
        mh_comp.E_P_custom = ep_mh
        mh_comp.E_F_custom = ef_mh
        mh_comp.E_D_custom = ed_mh
        mh_comp.epsilon_custom = (ep_mh / ef_mh) if (ef_mh and ef_mh != 0) else None
    except Exception:
        pass

# Compact comparison for MH
_log_component_custom_compare('MH', mh_comp)

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
# Ef = m5*ePH5 - m6*ePH6 - m7*ePH7 + m7*(eCH5 - eCH7)  -- complete balance
# Ed = Ef - Ep

m5 = _get_val(s5, "m")
m6 = _get_val(s6, "m")
m7 = _get_val(s7, "m")
eph5 = _get_eph_effective(s5)
eph6 = _get_eph_effective(s6)
eph7 = _get_eph_effective(s7)
ech5 = _get_val(s5, "e_CH")
ech6 = _get_val(s6, "e_CH")
ech7 = _get_val(s7, "e_CH")

ep_gw1 = None
ef_gw1 = None
ed_gw1 = None

# Ep = product (chemical exergy increase in gas stream)
if m6 is not None and ech6 is not None and ech5 is not None:
    ep_gw1 = m6 * (ech6 - ech5)

# Ef = fuel (complete exergy balance formula)
if all(v is not None for v in [m5, m6, m7, eph5, eph6, eph7, ech5, ech7]):
    ef_gw1 = m5*eph5 - m6*eph6 - m7*eph7 + m7*(ech5 - ech7)

# Ed = destruction
if ef_gw1 is not None and ep_gw1 is not None:
    ed_gw1 = ef_gw1 - ep_gw1

logging.info("\nGW1 custom calculation (complete exergy balance):")
logging.info(f"  Streams: m5={m5}, m6={m6}, m7={m7} kg/s")
logging.info(f"  Physical: eph5={eph5}, eph6={eph6}, eph7={eph7} J/kg")
logging.info(f"  Chemical: ech5={ech5}, ech6={ech6}, ech7={ech7} J/kg")
logging.info(f"  Ep_gw1 = m6*(ech6-ech5) = {ep_gw1} W")
logging.info(f"  Ef_gw1 = m5*eph5 - m6*eph6 - m7*eph7 + m7*(ech5-ech7) = {ef_gw1} W")
logging.info(f"  Ed_gw1 = Ef - Ep = {ed_gw1} W")

# Attach to GW1 component for display/export
if gw1_comp is not None:
    try:
        gw1_comp.E_P_custom = ep_gw1
        gw1_comp.E_F_custom = ef_gw1
        gw1_comp.E_D_custom = ed_gw1
        gw1_comp.epsilon_custom = (ep_gw1 / ef_gw1) if (ef_gw1 and ef_gw1 != 0) else None
    except Exception:
        pass

# Compact comparison for GW1
_log_component_custom_compare('GW1', gw1_comp)


# --- GW2 custom calculations using streams 6, 8, 9, 10
# GW2 Separator: Complete exergy balance
# Ep = m8 * (ech8 - ech6)  -- chemical exergy gain in product stream 8
# Ef = E6 - E9 - E10 - Eph8 - m8*ech6  -- fuel exergy consistent with product definition
# Ed = Ef - Ep

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

eph6 = _get_eph_effective(s6)
eph8 = _get_eph_effective(s8)
eph9 = _get_eph_effective(s9)
eph10 = _get_eph_effective(s10)

ech6 = _get_val(s6, "e_CH")
ech8 = _get_val(s8, "e_CH")
ech9 = _get_val(s9, "e_CH")
ech10 = _get_val(s10, "e_CH")

ep_gw2 = None
ef_gw2 = None
ed_gw2 = None

# Ep = product (chemical exergy gain in main product stream S8)
if m8 is not None and ech8 is not None and ech6 is not None:
    ep_gw2 = m8 * (ech8 - ech6)

# Ef = fuel (complete balance formula)
# E6, E9, E10 are total exergies (physical + chemical)
# Eph8 is only physical part of S8
if all(v is not None for v in [m6, m8, m9, m10, eph6, eph8, eph9, eph10, ech6, ech8, ech9, ech10]):
    E6_total = m6 * (eph6 + ech6)
    E9_total = m9 * (eph9 + ech9)
    E10_total = m10 * (eph10 + ech10)
    Eph8 = m8 * eph8
    ef_gw2 = E6_total - E9_total - E10_total - Eph8 - m8*ech6

# Ed = destruction
if ef_gw2 is not None and ep_gw2 is not None:
    ed_gw2 = ef_gw2 - ep_gw2

logging.info("\nGW2 custom calculation (complete exergy balance):")
logging.info(f"  Streams: m6={m6}, m8={m8}, m9={m9}, m10={m10} kg/s")
logging.info(f"  Physical [J/kg]: eph6={eph6}, eph8={eph8}, eph9={eph9}, eph10={eph10}")
logging.info(f"  Chemical [J/kg]: ech6={ech6}, ech8={ech8}, ech9={ech9}, ech10={ech10}")
logging.info(f"  Ep_gw2 = m8*(ech8-ech6) = {ep_gw2} W")
logging.info(f"  Ef_gw2 = E6 - E9 - E10 - Eph8 - m8*ech6 = {ef_gw2} W")
logging.info(f"  Ed_gw2 = Ef - Ep = {ed_gw2} W")

# Attach to GW2 component for display/export
if gw2_comp is not None:
    try:
        gw2_comp.E_P_custom = ep_gw2
        gw2_comp.E_F_custom = ef_gw2
        gw2_comp.E_D_custom = ed_gw2
        gw2_comp.epsilon_custom = (ep_gw2 / ef_gw2) if (ef_gw2 and ef_gw2 != 0) else None
    except Exception:
        pass

# Compact comparison for GW2
_log_component_custom_compare('GW2', gw2_comp)


# --- RECO custom calculations using streams SZ25, SZ26, SZ27, SZ28
# Ep = ETSZ26 - ETSZ25
# Ef = EPHSZ27 - EPHSZ28 + EMSZ25 - EMSZ26

reco_comp = ean.components.get("RECO") or next((c for n, c in ean.components.items() if str(n).upper().startswith("RECO")), None)

sz25 = _find_exact_stream("SZ25")
sz26 = _find_exact_stream("SZ26")
sz27 = _find_exact_stream("SZ27")
sz28 = _find_exact_stream("SZ28")

etsz25 = _total_from_permass(sz25, "e_T")
etsz26 = _total_from_permass(sz26, "e_T")
ephsz27 = _total_eph_effective(sz27)
ephsz28 = _total_eph_effective(sz28)
emsz25 = _total_from_permass(sz25, "e_M")
emsz26 = _total_from_permass(sz26, "e_M")

ep_reco = None
ef_reco = None
ed_reco = None

if etsz26 is not None and etsz25 is not None:
    ep_reco = etsz26 - etsz25

if all(v is not None for v in [ephsz27, ephsz28, emsz25, emsz26]):
    ef_reco = ephsz27 - ephsz28 + emsz25 - emsz26

if ef_reco is not None and ep_reco is not None:
    ed_reco = ef_reco - ep_reco

logging.info("\nRECO custom calculation (user formula):")
logging.info(f"  Ep_reco = ETSZ26 - ETSZ25 = {etsz26} - {etsz25} = {ep_reco} W")
logging.info(
    f"  Ef_reco = EPHSZ27 - EPHSZ28 + EMSZ25 - EMSZ26 = "
    f"{ephsz27} - {ephsz28} + {emsz25} - {emsz26} = {ef_reco} W"
)
logging.info(f"  Ed_reco = Ef - Ep = {ed_reco} W")

if reco_comp is not None:
    try:
        reco_comp.E_P_custom = ep_reco
        reco_comp.E_F_custom = ef_reco
        reco_comp.E_D_custom = ed_reco
        reco_comp.epsilon_custom = (ep_reco / ef_reco) if (ef_reco and ef_reco != 0) else None
    except Exception:
        pass

_log_component_custom_compare('RECO', reco_comp)


# --- KOL custom calculations (single column) using user formulas
# Produkt:
#   Ep = sum_{i in [23,12]} m_i*(e_CH,i - e_CH,11) + sum_{i in [23,12]} m_i*(e_T,i - e_T,11)
# Brennstoff:
#   Ef = (E_SZ26,liq - E_SZ26,gas) + sum_{i in [23,12]} m_i*(e_M,11 - e_M,i)
# Hinweis: im vorliegenden Modell wird der gasfoermige Kondensatorzweig als SZ25 gefuehrt,
#          daher: E_SZ26,gas -> E_SZ25.

kol_comp = ean.components.get("KOL") or next((c for n, c in ean.components.items() if str(n).strip().upper() == "KOL"), None)

s11_kol = _find_exact_stream("S11")
s12_kol = _find_exact_stream("S12")
s23_kol = _find_exact_stream("S23")
sz25_kol = _find_exact_stream("SZ25")
sz26_kol = _find_exact_stream("SZ26")

m12_kol = _get_val(s12_kol, "m")
m23_kol = _get_val(s23_kol, "m")

ech11_kol = _get_val(s11_kol, "e_CH")
ech12_kol = _get_val(s12_kol, "e_CH")
ech23_kol = _get_val(s23_kol, "e_CH")

et11_kol = _get_val(s11_kol, "e_T")
et12_kol = _get_val(s12_kol, "e_T")
et23_kol = _get_val(s23_kol, "e_T")

em11_kol = _get_val(s11_kol, "e_M")
em12_kol = _get_val(s12_kol, "e_M")
em23_kol = _get_val(s23_kol, "e_M")

esz26_liq = _total_eph_effective(sz26_kol)
esz26_gas = _total_eph_effective(sz25_kol)

ep_ch_kol = None
ep_t_kol = None
ep_kol = None
ef_kond_kol = None
ef_mech_kol = None
ef_kol = None
ed_kol = None

if all(v is not None for v in [m12_kol, m23_kol, ech11_kol, ech12_kol, ech23_kol]):
    ep_ch_kol = float(m12_kol) * (float(ech12_kol) - float(ech11_kol)) + float(m23_kol) * (float(ech23_kol) - float(ech11_kol))

if all(v is not None for v in [m12_kol, m23_kol, et11_kol, et12_kol, et23_kol]):
    ep_t_kol = float(m12_kol) * (float(et12_kol) - float(et11_kol)) + float(m23_kol) * (float(et23_kol) - float(et11_kol))

if ep_ch_kol is not None and ep_t_kol is not None:
    ep_kol = ep_ch_kol + ep_t_kol

if esz26_liq is not None and esz26_gas is not None:
    ef_kond_kol = esz26_liq - esz26_gas

if all(v is not None for v in [m12_kol, m23_kol, em11_kol, em12_kol, em23_kol]):
    ef_mech_kol = float(m12_kol) * (float(em11_kol) - float(em12_kol)) + float(m23_kol) * (float(em11_kol) - float(em23_kol))

if ef_kond_kol is not None and ef_mech_kol is not None:
    ef_kol = ef_kond_kol + ef_mech_kol

if ef_kol is not None and ep_kol is not None:
    ed_kol = ef_kol - ep_kol

e11_tot_kol = None
e12_tot_kol = None
e23_tot_kol = None
e25_tot_kol = None
e26_tot_kol = None
ed_kol_bal = None

if all(v is not None for v in [s11_kol, _get_val(s11_kol, "m"), _get_eph_effective(s11_kol), _get_val(s11_kol, "e_CH")]):
    e11_tot_kol = float(_get_val(s11_kol, "m")) * (float(_get_eph_effective(s11_kol)) + float(_get_val(s11_kol, "e_CH")))

if all(v is not None for v in [s12_kol, _get_val(s12_kol, "m"), _get_eph_effective(s12_kol), _get_val(s12_kol, "e_CH")]):
    e12_tot_kol = float(_get_val(s12_kol, "m")) * (float(_get_eph_effective(s12_kol)) + float(_get_val(s12_kol, "e_CH")))

if all(v is not None for v in [s23_kol, _get_val(s23_kol, "m"), _get_eph_effective(s23_kol), _get_val(s23_kol, "e_CH")]):
    e23_tot_kol = float(_get_val(s23_kol, "m")) * (float(_get_eph_effective(s23_kol)) + float(_get_val(s23_kol, "e_CH")))

if all(v is not None for v in [sz25_kol, _get_val(sz25_kol, "m"), _get_eph_effective(sz25_kol), _get_val(sz25_kol, "e_CH")]):
    e25_tot_kol = float(_get_val(sz25_kol, "m")) * (float(_get_eph_effective(sz25_kol)) + float(_get_val(sz25_kol, "e_CH")))

if all(v is not None for v in [sz26_kol, _get_val(sz26_kol, "m"), _get_eph_effective(sz26_kol), _get_val(sz26_kol, "e_CH")]):
    e26_tot_kol = float(_get_val(sz26_kol, "m")) * (float(_get_eph_effective(sz26_kol)) + float(_get_val(sz26_kol, "e_CH")))

if all(v is not None for v in [e11_tot_kol, e12_tot_kol, e23_tot_kol, e25_tot_kol, e26_tot_kol]):
    ed_kol_bal = (e11_tot_kol + e26_tot_kol) - (e12_tot_kol + e23_tot_kol + e25_tot_kol)

logging.info("\nKOL custom calculation (user formula):")
logging.info(f"  Ep_ch = m12*(eCH12-eCH11) + m23*(eCH23-eCH11) = {ep_ch_kol} W")
logging.info(f"  Ep_T  = m12*(eT12-eT11) + m23*(eT23-eT11) = {ep_t_kol} W")
logging.info(f"  Ep_kol = Ep_ch + Ep_T = {ep_kol} W")
logging.info(f"  Ef_kond = E_SZ26_liq - E_SZ26_gas(=SZ25) = {esz26_liq} - {esz26_gas} = {ef_kond_kol} W")
logging.info(f"  Ef_mech = m12*(eM11-eM12) + m23*(eM11-eM23) = {ef_mech_kol} W")
logging.info(f"  Ef_kol = Ef_kond + Ef_mech = {ef_kol} W")
logging.info(f"  Ed_kol = Ef - Ep = {ed_kol} W")
logging.info(f"  Gesamtbilanz Ed_kol_bal = (E11 + E26) - (E12 + E23 + E25) = {ed_kol_bal} W")
if ed_kol is not None and ed_kol_bal is not None:
    logging.info(f"  Delta (Ed_formel - Ed_bal) = {ed_kol - ed_kol_bal} W")

if kol_comp is not None:
    comp_ed = getattr(kol_comp, "E_D", None)
    if comp_ed is not None and ed_kol is not None:
        logging.info(
            "  Ed match (component vs custom): "
            + ("YES" if _cmp(comp_ed, ed_kol) else f"NO (diff={comp_ed - ed_kol:.6g})")
        )
    else:
        logging.info("  Ed match (component vs custom): N/A")

if kol_comp is not None:
    try:
        kol_comp.E_P_custom = ep_kol
        kol_comp.E_F_custom = ef_kol
        kol_comp.E_D_custom = ed_kol
        kol_comp.epsilon_custom = (ep_kol / ef_kol) if (ef_kol and ef_kol != 0) else None
    except Exception:
        pass

_log_component_custom_compare('KOL', kol_comp)


# KOLLP, KOLHP and RC2 custom blocks are intentionally omitted for single-column mode.


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
resolved_components = []
for comp_name, component in ean.components.items():
    if component.__class__.__name__ == "CycleCloser":
        continue

    E_F_std = getattr(component, 'E_F', None)
    E_P_std = getattr(component, 'E_P', None)
    E_D_std = getattr(component, 'E_D', None)
    E_F_custom = getattr(component, 'E_F_custom', None)
    E_P_custom = getattr(component, 'E_P_custom', None)
    E_D_custom = getattr(component, 'E_D_custom', None)

    use_custom = all(v is not None for v in (E_F_custom, E_P_custom, E_D_custom))
    if use_custom:
        source = "custom"
        E_F_sel, E_P_sel, E_D_sel = E_F_custom, E_P_custom, E_D_custom
    else:
        source = "standard"
        E_F_sel, E_P_sel, E_D_sel = E_F_std, E_P_std, E_D_std

    resolved_components.append((str(comp_name), source, E_F_sel, E_P_sel, E_D_sel))

sum_E_F_sel = sum(v for _, _, v, _, _ in resolved_components if isinstance(v, (int, float)) and math.isfinite(v))
sum_E_P_sel = sum(v for _, _, _, v, _ in resolved_components if isinstance(v, (int, float)) and math.isfinite(v))
sum_E_D_sel = sum(v for _, _, _, _, v in resolved_components if isinstance(v, (int, float)) and math.isfinite(v))
closure_sel = sum_E_F_sel - sum_E_P_sel - sum_E_D_sel

logging.info("\n" + "="*100)
logging.info("NO-MIX OVERALL (DISPLAY CONSISTENT)")
logging.info("="*100)
logging.info(
    "Rule: per component use CUSTOM iff (E_F_custom, E_P_custom, E_D_custom) all exist; otherwise STANDARD."
)
logging.info(f"Sum selected E_F = {sum_E_F_sel:.2f} W")
logging.info(f"Sum selected E_P = {sum_E_P_sel:.2f} W")
logging.info(f"Sum selected E_D = {sum_E_D_sel:.2f} W")
logging.info(f"Closure (Sum E_F - Sum E_P - Sum E_D) = {closure_sel:.2f} W")
logging.info("="*100)

logging.info("\n" + "="*100)
logging.info("OVERALL SYSTEM RESULTS")
logging.info("="*100)
logging.info(f"Total E_F = {ean.E_F:.2f} W")
logging.info(f"Total E_P = {ean.E_P:.2f} W")
logging.info(f"Total E_D = {ean.E_D:.2f} W")
logging.info(f"Total E_L = {ean.E_L:.2f} W")
epsilon_total = f"{ean.epsilon:.4f}" if ean.epsilon is not None else "N/A"
logging.info(f"System Efficiency eps = {epsilon_total}")
logging.info("="*100 + "\n")

# Export JSON in the same structure as examples/json_example/example.json
output_path = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "examples", "json_example", "aspen_luftzerlegung_single.json")
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
    eps_custom = getattr(comp, 'epsilon_custom', None)
    if any(v is not None for v in (E_F_custom, E_P_custom, E_D_custom, eps_custom)):
        custom_exergy[str(comp_name)] = {
            "E_F_custom": E_F_custom,
            "E_P_custom": E_P_custom,
            "E_D_custom": E_D_custom,
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
        return f"{value:.6g}"
    return _latex_escape(str(value))


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
            values.append(_format_value(val))
        rows.append(" & ".join(values) + r" \\")

    col_spec = "l" + "r" * (len(columns) - 1)
    lines = [
        f"\\begin{{longtable}}{{{col_spec}}}",
            r"\caption{Thermodynamische und exergetische Kenngrößen der simulierten Prozessströme} \\",
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
            values.append(_format_value(val))
        rows.append(" & ".join(values) + r" \\")

    col_spec = "l" + "r" * (len(columns) - 1)
    lines = [
        f"\\begin{{longtable}}{{{col_spec}}}",
            r"\caption{Stoffliche Zusammensetzung der Prozessströme} \\",
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
    header = " & ".join([
        "Component",
        "Type",
        r"$\dot{E}_F$",
        r"$\dot{E}_P$",
        r"$\dot{E}_D$",
        r"$\varepsilon$",
        r"$y_{D,k}$",
    ]) + " \\\\"
    unit_row = " & ".join(["", "", "(W)", "(W)", "(W)", "(-)", "(-)"]) + " \\\\" 

    E_F_tot = getattr(ean, "E_F", None)

    rows = []
    for comp_name, component in components.items():
        if component.__class__.__name__ in {"CycleCloser", "Mixer", "Splitter"}:
            continue
        # standard values
        E_F = getattr(component, "E_F", None)
        E_P = getattr(component, "E_P", None)
        E_D = getattr(component, "E_D", None)
        epsilon = getattr(component, "epsilon", None)

        # if this component has custom values (e.g. RC), use them for display in the standard columns
        E_F_custom = getattr(component, "E_F_custom", None)
        E_P_custom = getattr(component, "E_P_custom", None)
        E_D_custom = getattr(component, "E_D_custom", None)
        epsilon_custom = getattr(component, "epsilon_custom", None)

        use_custom = all(v is not None for v in (E_F_custom, E_P_custom, E_D_custom))
        if use_custom:
            display_E_F = E_F_custom
            display_E_P = E_P_custom
            display_E_D = E_D_custom
            if epsilon_custom is not None:
                display_epsilon = epsilon_custom
            else:
                display_epsilon = (display_E_P / display_E_F) if (display_E_F not in (None, 0)) else None
        else:
            display_E_F = E_F
            display_E_P = E_P
            display_E_D = E_D
            display_epsilon = epsilon
        y_D_k = (display_E_D / E_F_tot) if (
            isinstance(display_E_D, (int, float))
            and isinstance(E_F_tot, (int, float))
            and E_F_tot != 0
        ) else None

        rows.append(
            " & ".join([
                _latex_escape(str(comp_name)),
                _latex_escape(component.__class__.__name__),
                _format_value(display_E_F),
                _format_value(display_E_P),
                _format_value(display_E_D),
                _format_value(display_epsilon),
                _format_value(y_D_k),
            ]) + r" \\\\" )

    col_spec = "l" + "l" + "r" * 5
    lines = [
        f"\\begin{{tabular}}{{{col_spec}}}",
        "\\hline",
        header,
        unit_row,
        "\\hline",
        *rows,
        "\\hline",
        "\\end{tabular}",
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
        "aspen_luftzerlegung_streams_single.tex",
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
        "aspen_luftzerlegung_components_single.tex",
    )
)
components_table = _build_component_results_table(ean.components)
with open(components_output_path, "w", encoding="utf-8") as tex_file:
    tex_file.write(components_table)

molfractions_output_path = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "..",
        "Overleaf_LaTeX",
        "tabellen",
        "aspen_luftzerlegung_streams_molfrac_single.tex",
    )
)
molfractions_table = _build_molar_fractions_table(connections_data)
with open(molfractions_output_path, "w", encoding="utf-8") as tex_file:
    tex_file.write(molfractions_table)
