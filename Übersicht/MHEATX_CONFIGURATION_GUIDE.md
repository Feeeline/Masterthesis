# MHeatX Konfigurationsanleitung

## Überblick

Die `MHeatX` (MultiHeatExchanger) Komponente in exerpy unterstützt zwei Betriebsmodi für die Exergieberechnung:

### 1. **Balance-Mode** (immer aktiv)

Eine generische Exergiebi lanz basierend auf allen Ein- und Ausgängen:

$$E_D^{balance} = \sum E_{in} - \sum E_{out}$$

Dieser Modus arbeitet völlig unabhängig von Product/Fuel-Definitionen.

### 2. **spezProdukt-Mode** (optional, konfigurierbar)

Wenn eine MHeatX-Konfiguration übergeben wird, berechnet die Komponente zusätzlich:
- **E_F** (Fuel exergy): Exergie der "heißen" Ströme, die Exergie abgeben
- **E_P** (Product exergy): Exergie der definierten Produktströme
- **E_D_spez**: Spezifische Exergievernichtung
- **eps_spez**: Spezifische exergiesche Effizienz

## Verwendung

### Schritt 1: Konfiguration definieren

In `test_aspen_luftzerlegung.py` (oder Ihrer Testdatei):

```python
MHEATX_CFG = {
    "MW": {
        "part": "E_PH",  # Exergiekomponente: E_PH, E_T, E_M
        "hot_pairs": [("inlet_0", "outlet_0"), ("inlet_2", "outlet_2")],
        "cold_pairs": [("inlet_1", "outlet_1"), ("inlet_3", "outlet_3")],
        "product_pairs": [("inlet_1", "outlet_1")],  # welche der cold_pairs sind "Produkt"
        "fuel_pairs": None,  # optional: Default = hot_pairs
    },
    "RC": {
        "part": "E_T",
        "hot_pairs": [("inlet_in", "outlet_out")],
        "cold_pairs": [],
        "product_pairs": [],
    }
}
```

### Schritt 2: Konfiguration registrieren

```python
ean = ExergyAnalysis.from_aspen(model_path, ...)

# Konfiguration anwenden
if MHEATX_CFG:
    ean.set_mheatx_config(MHEATX_CFG)

# Analyse starten
ean.analyse(E_F=fuel, E_P=product, E_L=loss)
```

### Schritt 3: Ergebnisse interpretieren

Im `parser_run.log` werden folgende Informationen ausgegeben:

**Balance-Mode:**
```
MHeatX MW - Stream Overview
==========================================================================
Inlets:
  inlet_0: m=24.8 kg/s, e_PH=150778.38 J/kg, E=3744706.73 W
  inlet_1: m=4.7 kg/s, e_PH=150778.38 J/kg, E=713003.53 W
  ...
Outlets:
  outlet_0: m=24.8 kg/s, e_PH=306948.31 J/kg, E=7626066.64 W
  ...

Balance-Mode Results:
  E_D_balance = sum(E_in) - sum(E_out) = 347223.27 W
```

**spezProdukt-Mode** (wenn konfiguriert):
```
spezProdukt-Mode Results (part=E_PH):
  Configuration:
    hot_pairs (fuel base): [("inlet_0", "outlet_0"), ("inlet_2", "outlet_2")]
    cold_pairs: [("inlet_1", "outlet_1"), ("inlet_3", "outlet_3")]
    product_pairs: [("inlet_1", "outlet_1")]

  E_F (fuel) = 2500000.00 W
  E_P (product) = 2200000.00 W
  E_D_spez = E_F - E_P = 300000.00 W
  eps_spez = E_P / E_F = 0.8800
```

## Konfigurationsparameter

| Parameter | Typ | Standard | Beschreibung |
|-----------|-----|---------|------------|
| `part` | str | "E_PH" | Exergiekomponente: "E_PH", "E_T", "E_M", optional "E_total" |
| `hot_pairs` | list | [] | Stream-Paare (inlet, outlet), die Exergie abgeben |
| `cold_pairs` | list | [] | Stream-Paare (inlet, outlet), die Exergie aufnehmen |
| `product_pairs` | list | [] | Stream-Paare, die als "Produkt" gelten (Teilmenge von cold_pairs) |
| `fuel_pairs` | list | None | Optional: überschreibt hot_pairs als Fuel-Basis |

## Thermodynamisches Modell

### Balance-Mode

$$E_D^{balance} = \sum_{\text{inlets}} m_i \cdot e_{part,i} - \sum_{\text{outlets}} m_j \cdot e_{part,j}$$

wobei $e_{part}$ die spezifische Exergie ist (E_PH, E_T oder E_M in J/kg).

### spezProdukt-Mode Fuel

$$E_F = \sum_{(\text{inlet, outlet}) \in \text{fuel\_pairs}} (E_{part,inlet} - E_{part,outlet})$$

Das ist typisch für "warme" Ströme, die gekühlt werden und deren Exergie-Differenz als Fuel bereitgestellt wird.

### spezProdukt-Mode Product

$$E_P = \sum_{(\text{inlet, outlet}) \in \text{product\_pairs}} (E_{part,outlet} - E_{part,inlet})$$

Das ist typisch für "kalte" Ströme, die erwärmt werden und deren Exergie-Zunahme als Produkt zählt.

### Effizienz

$$\varepsilon_{\text{spez}} = \frac{E_P}{E_F} \quad \text{(falls } E_F > 0\text{)}$$

## Stream-Namen finden

Die Ein- und Ausgangs-Ströme haben Schlüssel wie:
- Nummern: `0`, `1`, `2`, ...
- Oder benutzerdefinierte Namen: `"inlet_feed"`, `"outlet_product"`, ...

Um die verfügbaren Ströme für MW zu sehen:

1. Aktivieren Sie die Komponenten-Diagnostik in der `analyse()` Phase
2. Im Log suchen Sie nach: `Component inputs before calc | MW (MHeatX) | ...`
3. Die `inlets=[...]` und `outlets=[...]` Listen zeigen die Schlüssel und deren Eigenschaften

Beispiel aus dem Log:
```
inlets=[
  {'name': 0, 'T': 308.15, ...},
  {'name': 2, 'T': 96.71, ...},
  ...
]
outlets=[
  {'name': 0, 'T': 100.73, ...},
  ...
]
```

Stream-Namen sind hier die `'name'` Werte: `0`, `2`, etc.

## Sauberes Logging

Die Implementierung unterscheidet streng:
- **e_part** (Kleinbuchstabe): Spezifische Exergie in J/kg
- **E_part** (Großbuchstabe): Exergiefluss in W (m·e_part)

Im Log werden Variablen mit beschreibenden Einheiten ausgegeben:
```
e_PH=150778.38 J/kg, E=3744706.73 W, m=24.8 kg/s
```

## Fehlerbehandlung

### Warnung: E_D_balance vs. E_D_spez stimmen nicht überein

Falls die Balance-Exergievernichtung und die spezifische Exergievernichtung um mehr als 1% abweichen:

```
[WARN] MHeatX MW: E_D_balance and E_D_spez differ by 5.2% 
       (balance=347223.27 W, spez=329300.52 W). 
       Check stream pair definitions.
```

**Ursachen:**
- Fehlerhaft zugeordnete Strom-Paare
- Nicht alle Ströme in den Pairs erfasst
- Numerische Fehler bei der Datenverarbeitung

**Lösung:**
- Überprüfen Sie die `hot_pairs`, `cold_pairs`, `product_pairs` auf Vollständigkeit
- Verwenden Sie die Komponenten-Diagnostik um die tatsächlichen Stream-Schlüssel zu verifizieren

### Fehler: Stream nicht gefunden

Falls ein Stream-Name nicht existiert, wird er bei der Summation ignoriert (nicht null):

```python
E = get_E(get_stream_by_name(component, stream_name), part)
# Returns None if stream_name not found
```

Das ist sicher, aber logisch falsch. Überprüfen Sie die Stream-Namen in der Konfiguration!

## Beispiel aus der Praxis

**Szenario:** Wärmewechsler mit 2 heißen und 3 kalten Strömen

```python
MHEATX_CFG = {
    "MW": {
        "part": "E_PH",
        "hot_pairs": [
            ("inlet_0", "outlet_0"),  # Warmer Luftstrom kühlt sich ab
            ("inlet_2", "outlet_2")   # Warmer Prozessfluid kühlt sich ab
        ],
        "cold_pairs": [
            ("inlet_1", "outlet_1"),  # Kalter Luftstrom erwärmt sich
            ("inlet_3", "outlet_3"),  # Kalter Kühlwasserstrom erwärmt sich
            ("inlet_4", "outlet_4")   # Sonstiger kalter Strom
        ],
        "product_pairs": [
            ("inlet_1", "outlet_1"),  # Nur dieser kalte Strom ist "Produkt"
        ]
    }
}
```

**Balance-Modus zeigt:**
- E_D_balance = 347.2 kW (Gesamt Exergievernichtung)

**spezProdukt-Modus zeigt zusätzlich:**
- E_F = 2500.0 kW (Exergieabgabe der heißen Ströme)
- E_P = 2200.0 kW (Exergieaufnahme des Produktstroms inlet_1→outlet_1)
- ε = 88% (Effizienz dieser Produkterzeugung)

## Erweiterung auf weitere MHeatX-Blöcke

Fügen Sie einfach weitere Einträge zum `MHEATX_CFG`-Dict hinzu:

```python
MHEATX_CFG = {
    "MW": { ... },
    "RC": { ... },
    "HX_aux": {
        "part": "E_T",
        "hot_pairs": [...],
        ...
    }
}
```

Die Konfiguration wird automatisch zur Laufzeit auf alle MHeatX-Komponenten angewendet.

## Best Practices

1. **Balance-Modus immer nutzen** für Diagnosezwecke
2. **spezProdukt-Modus optional**, nur wenn klar ist, welche Ströme "Produkt" sind
3. **Stream-Namen verifizieren** über die Komponenten-Diagnostik im Log
4. **Energiebilanzen checken**: E_D_balance sollte konsistent mit der Wärmeübertragung sein
5. **Dokumentation aktualisieren**, wenn neue MHeatX-Blöcke hinzukommen
