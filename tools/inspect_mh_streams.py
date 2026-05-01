import os, sys
from exerpy import ExergyAnalysis

# use same default model path as test
default_model_path = r"C:\Users\Felin\Documents\Masterthesis\Simulation_Code\GIT\examples\asu_aspen\Singekolonne_klein\Single_Column_Simulation_Final.bkp"
model_path = os.environ.get('MODEL_PATH') or (sys.argv[1] if len(sys.argv) > 1 else default_model_path)
print('Using model_path=', model_path)

ean = ExergyAnalysis.from_aspen(model_path, chemExLib='Ahrendts', split_physical_exergy=True)
conns = ean.connections

suffixes = ['8','11','23','24']

def total_from_permass(conn, key_permass, key_mass='m'):
    if not conn:
        return None
    val = conn.get(key_permass)
    m = conn.get(key_mass)
    try:
        if val is None or m is None:
            return None
        return float(val) * float(m)
    except Exception:
        return None

for suf in suffixes:
    candidates = [k for k in conns.keys() if str(k).endswith(suf)]
    print('\n--- suffix', suf, 'matches:', candidates)
    for k in candidates:
        c = conns[k]
        m = c.get('m')
        eT = c.get('e_T')
        eM = c.get('e_M')
        ePH = c.get('e_PH')
        et_tot = total_from_permass(c, 'e_T')
        em_tot = total_from_permass(c, 'e_M')
        eph_tot = total_from_permass(c, 'e_PH')
        print(f"{k}: m={m}, e_T={eT}, e_M={eM}, e_PH={ePH}")
        print(f"  totals -> E_T={et_tot}, E_M={em_tot}, E_PH={eph_tot}")

print('\nDone')
