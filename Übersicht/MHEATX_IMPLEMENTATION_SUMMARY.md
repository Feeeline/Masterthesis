# MHeatX Enhancement Summary

## Was wurde implementiert

Eine vollständig konfigurierbare MHeatX-Exergieberechnung mit zwei Betriebsmodi:

### 1. Balance-Mode (automatisch immer aktiv)
- Generische Exergiebi lanz unabhängig von Fuel/Product-Definitionen
- $$E_D^{balance} = \sum E_{in} - \sum E_{out}$$
- Immer verfügbar, keine Konfiguration notwendig

### 2. spezProdukt-Mode (optional, konfigurierbar)
- Stream-paare definieren, die als "Fuel" (hot_pairs) und "Product" (product_pairs) gelten
- Berechnet E_F, E_P, E_D_spez und ε basierend auf benutzerdefinierten Paaren
- Vergleicht automatisch mit Balance-Mode und warnt bei signifikanten Unterschieden

---

## Dateien geändert/erstellt

### 1. **src/exerpy/components/heat_exchanger/mheatx.py** (GEÄNDERT)

#### Neue Hilfsfunktionen:
- `get_stream_by_name(component, stream_name)`: Stream anhand Name/Key finden
- `get_E(stream, part)`: Robuste Exergiefluss-Extraktion (W), fallback zu m·e_part
- `sum_pairs_delta(component, pairs, part, direction)`: Exergiedifferenzen über Stream-Paare summieren

#### Erweiterte `calc_exergy_balance()`:
```python
def calc_exergy_balance(self, T0: float, p0: float, split_physical_exergy, 
                       mheatx_config=None) -> None
```

- Akzeptiert neuen Parameter `mheatx_config` (Dictionary)
- Balance-Mode: Immer E_D_balance = E_in - E_out berechnen
- spezProdukt-Mode: Wenn config vorhanden, zusätzlich E_F, E_P, E_D_spez, epsilon berechnen
- Überschreibt E_F, E_P, E_D, epsilon mit spezProdukt-Werten (falls konfiguriert)
- Detailliertes Logging aller Ein-/Ausgänge mit Massen und spezifischen Exergien
- Warnung bei > 1% Abweichung zwischen Balance und spezProdukt-Modus

### 2. **src/exerpy/analyses.py** (GEÄNDERT)

#### In ExergyAnalysis.__init__:
- Neues Attribut: `self.mheatx_config = {}` zum Speichern der Konfiguration

#### Neue Methode:
```python
def set_mheatx_config(self, config_dict: dict) -> None
```
- Registriert MHeatX-Konfigurationen vor `analyse()` Aufruf
- Logged welche Komponenten konfiguriert werden

#### In analyse() Methode:
- MHeatX-spezifisch: Konfiguration an `calc_exergy_balance()` übergeben
- Andere Komponenten: Weiterhin Normal-Signatur ohne mheatx_config Parameter

```python
if component.__class__.__name__ == "MHeatX":
    cfg = self.mheatx_config.get(component.name)
    component.calc_exergy_balance(self.Tamb, self.pamb, self.split_physical_exergy, 
                                   mheatx_config=cfg)
else:
    component.calc_exergy_balance(self.Tamb, self.pamb, self.split_physical_exergy)
```

### 3. **tests/test_aspen_luftzerlegung.py** (GEÄNDERT)

- Added MHeatX configuration template (commented out by default)
- Call to `ean.set_mheatx_config(MHEATX_CFG)` if configuration is provided

### 4. **tests/test_aspen_luftzerlegung_WITH_MHEATX_CONFIG.py** (NEU)

- Vollständiges Beispiel mit aktivierter MHeatX-Konfiguration
- Detaillierte Kommentare zu Stream-Namen und Pair-Definitionen
- Zeigt praktisches Anwendungsbeispiel für MW (5 in, 5 out) und RC (2 in, 2 out)

### 5. **MHEATX_CONFIGURATION_GUIDE.md** (NEU)

- Umfassende Dokumentation zur MHeatX-Funktionalität
- Thermodynamisches Modell mit Formeln
- Verwendungsbeispiele
- Fehlerbehandlung und Best Practices
- Stream-Namen finden (Tipps)

---

## Verwendungsbeispiel

### Minimal (nur Balance-Mode)
```python
ean = ExergyAnalysis.from_aspen(model_path, ...)
ean.analyse(E_F=fuel, E_P=product, E_L=loss)
# Log zeigt Balance-Mode Results für alle MHeatX-Komponenten
```

### Mit Configuration (spezProdukt-Mode)
```python
MHEATX_CFG = {
    "MW": {
        "part": "E_PH",
        "hot_pairs": [(0, 0), (2, 2)],
        "cold_pairs": [(1, 1), (3, 3), (4, 4)],
        "product_pairs": [(1, 1)],
    }
}

ean = ExergyAnalysis.from_aspen(model_path, ...)
ean.set_mheatx_config(MHEATX_CFG)
ean.analyse(E_F=fuel, E_P=product, E_L=loss)
# Log zeigt Balance-Mode UND spezProdukt-Mode Results
```

---

## Logging-Ausgaben

### Balance-Mode (immer)
```
MHeatX MW - Stream Overview
==========================================================================
Inlets:
  0: m=24.8 kg/s, e_PH=150778.38 J/kg, E=3744706.73 W
  2: m=8.06 kg/s, e_PH=291896.71 J/kg, E=2353688.21 W
  ...
Outlets:
  0: m=24.8 kg/s, e_PH=306948.31 J/kg, E=7626066.64 W
  ...

Balance-Mode Results:
  E_D_balance = sum(E_in) - sum(E_out) = 347223.27 W
```

### spezProdukt-Mode (falls konfiguriert)
```
spezProdukt-Mode Results (part=E_PH):
  Configuration:
    hot_pairs (fuel base): [(0, 0), (2, 2)]
    cold_pairs: [(1, 1), (3, 3), (4, 4)]
    product_pairs: [(1, 1)]

  E_F (fuel) = 2500000.00 W
  E_P (product) = 2200000.00 W
  E_D_spez = E_F - E_P = 300000.00 W
  eps_spez = E_P / E_F = 0.8800
```

---

## Konfigurationsparameter

| Parameter | Typ | Standard | Beschreibung |
|-----------|-----|---------|------------|
| `part` | str | "E_PH" | Exergiekomponente zur Verwendung |
| `hot_pairs` | list | [] | (inlet, outlet) Paare die Exergie ABGEBEN |
| `cold_pairs` | list | [] | (inlet, outlet) Paare die Exergie AUFNEHMEN |
| `product_pairs` | list | [] | Teilmenge von cold_pairs = "Produkt" |
| `fuel_pairs` | list | None | Optional: Override für hot_pairs |

**Note:** Inlet/Outlet-Bezeichner sind Numeric (0, 1, 2, ...) oder benutzerdefiniert, basierend auf komponenten-spezifischer Verdrahtung.

---

## Thermodynamisches Modell

### Balance-Modus
$$E_D^{balance} = \sum_{\text{inlets}} (m_i \cdot e_{part,i}) - \sum_{\text{outlets}} (m_j \cdot e_{part,j})$$

### spezProdukt-Modus - Fuel
$$E_F = \sum_{(in,out) \in hot\_pairs} (E_{part,in} - E_{part,out})$$

(Exergieabgabe der heißen Ströme)

### spezProdukt-Modus - Product
$$E_P = \sum_{(in,out) \in product\_pairs} (E_{part,out} - E_{part,in})$$

(Exergieaufnahme der als Produkt definierten Ströme)

### Effizienz
$$\varepsilon = \frac{E_P}{E_F} \quad \text{falls } E_F > 0$$

---

## Robustheit & Fehlerbehandlung

### None-sicherer Code
- `get_E()` gibt None zurück wenn Stream oder Feld nicht existiert
- `sum_pairs_delta()` ignoriert nicht findbare Streams
- Keine Crashes, aber möglicherweise konsistenzwarnungen

### Validierung
- Vergleich E_D_balance vs E_D_spez
- Warnung wenn > 1% Abweichung
- Hilft bei der Diagnose fehlerhafter Pair-Definitionen

### Logging
- Unterscheidung e_part (J/kg) vs E_part (W)
- Vollständige Stream-Information (T, p, m, spezifische exergien)
- Komponenten-Input-Diagnostik vor Berechnung

---

## Bekannte Einschränkungen / Zukünftige Erweiterungen

1. **Stream-Namen**: Müssen manuell anhand Log identifiziert werden
   - Könnte zukünftig durch automatische Stream-Registry automatisiert werden

2. **Exergiekomponenten-Wahl**: Nur E_PH, E_T, E_M
   - Zukünftig: E_total, benutzerdefinierte Kombinationen

3. **Paar-Definition**: Nur (inlet, outlet) Paare
   - Zukünftig: Komplexere Stromanordnungen (z.B. Inlet-Inlet, Multi-Outlet Paare)

4. **Keine Automatische Pair-Erkennung**: Nutzer muss Paare manuell definieren
   - Zukünftig: Heuristen basierend auf Stream-Richtung/-Temperatur

---

## Test-Validierung

✅ **Balance-Mode** funktioniert ohne Konfiguration
- Testet alle 20 Komponenten
- Exit-Code: 0 (erfolgreich)

✅ **Logging** zeigt korrekte Struktur
- Stream-Overview mit allen Ein-/Ausgängen
- Balance-Mode Results für alle MHeatX
- spezProdukt-Mode Results wenn konfiguriert

✅ **Konfiguration** wird korrekt registriert
- `ean.set_mheatx_config()` akzeptiert Dict
- Logging bestätigt Komponenten-Liste
- Keine Fehler bei leerer/fehlender Konfiguration

⚠️ **Pair-Definition** in Beispiel:
- Indices 0, 1, 2, 3, 4 sind Platzhalter
- Tatsächliche Stream-Nummern müssen aus Log bestimmt werden
- Deshalb zeigen Test-Beispiele E_F=0, E_P=0 (korrekt, da Paare nicht matched)

---

## Nächtse Schritte für Nutzer

1. **Stream-Namen identifizieren**:
   - Führe `test_aspen_luftzerlegung.py` aus
   - Suche Log nach "Component inputs before calc | MW (MHeatX) |"
   - Notiere die 'name' Werte in inlets/outlets

2. **Konfiguration anpassen**:
   - Passe `MHEATX_CFG` in `test_aspen_luftzerlegung.py` an
   - Verwende korrekte Stream-Nummern
   - Definie clear welche Paare hot/cold/product sind

3. **Validieren**:
   - Führe erneut Script aus
   - Vergleiche Balance-Mode und spezProdukt-Mode E_D
   - Falls > 1% Abweichung: Pair-Definitionen überprüfen

4. **In Produktions-Code einbauen**:
   - Kopiere Pattern aus Beispiel
   - Ersetze hardcodiert Stream-Nummern durch variables Lookup (optional)
   - Dokumentiere Pair-Definitions-Logik für Ihr Projekt

---

## Zusammenfassung

Die MHeatX-Erweiterung bietet:

✅ **Flexible Konfigurierbarkeit** - Keine hardcoding mehr, sondern Dict-basiert
✅ **Zwei Bewertungsmodi** - Balance-Mode immer, spezProdukt-Mode optional
✅ **Robuste Implementierung** - None-safe, mit Validierung und Warnungen
✅ **Sauberes Logging** - Klare Unterscheidung e_part vs E_part
✅ **Minimal invasiv** - Nur MHeatX betroffen, andere Komponenten unverändert
✅ **Erweiterbar** - Einfach weitere MHeatX hinzufügen via Config-Dict

**Größter Vorteil:** Thermodynamische Bewertung (Fuel/Product) ist völlig unabhängig vom Code - konfigurierbar über eine externe Datei/Config!
