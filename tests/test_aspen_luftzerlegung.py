from exerpy import ExergyAnalysis

model_path = r'C:\Users\Felin\Documents\Masterthesis\Code\Exerpy\exerpy\examples\asu_aspen\Doppelkolonne.bkp'

ean = ExergyAnalysis.from_aspen(model_path, chemExLib='Ahrendts', split_physical_exergy=False)

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
ean.exergy_results()