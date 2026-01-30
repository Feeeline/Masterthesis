# Exergy Analysis Flow Schematic

## High-Level Process Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                    EXERGY ANALYSIS WORKFLOW                          │
└─────────────────────────────────────────────────────────────────────┘
                                │
                    ┌───────────▼───────────┐
                    │    PARSE PHASE        │
                    │  (Load Model Data)    │
                    └───────────┬───────────┘
                                │
         ┌──────────────────────┼──────────────────────┐
         ▼                      ▼                      ▼
    ┌─────────┐        ┌──────────────┐        ┌──────────────┐
    │  TESPy  │        │ Aspen Parser │        │ JSON/Ebsilon │
    └────┬────┘        └──────┬───────┘        └──────┬───────┘
         │                    │                       │
         └────────────────────┼───────────────────────┘
                              │
                    ┌─────────▼──────────┐
                    │ Extract components │
                    │ Extract connections│
                    │ Parse stream data  │
                    │ (T, p, m, h, etc.)│
                    └──────────┬─────────┘
                              │
                 ┌────────────▼────────────┐
                 │   LOGGING POINT #1      │  ◄─── PARSER COMPLETION
                 │  "Parsing completed:    │      Log: Block count,
                 │   X blocks, Y connections,│     connections, components
                 │   Z component groups"   │
                 └────────────┬────────────┘
                              │
                    ┌─────────▼──────────┐
                    │  CALCULATION PHASE │
                    │  (ExergyAnalysis)  │
                    └──────────┬─────────┘
                              │
              ┌───────────────▼───────────────┐
              │ _construct_components()       │
              │ Build component objects       │
              │ from parsed data              │
              └───────────────┬───────────────┘
                              │
              ┌───────────────▼───────────────┐
              │ analyse() method              │
              │ For each component:           │
              └───────────────┬───────────────┘
                              │
        ┌─────────────────────▼──────────────────────┐
        │ LOGGING POINT #2: "Component inputs        │ ◄─── COMPONENT INPUT DUMP
        │ before calc" (for each component)          │
        │                                             │
        │ Logs:                                      │
        │ - Component name & type                    │
        │ - Inlet stream properties:                 │
        │   - T, p, m, h                            │
        │   - e_PH, e_T, e_M (exergy terms)        │
        │ - Outlet stream properties (same)          │
        │ - Power connections (if any)               │
        └──────────────────┬──────────────────────────┘
                           │
        ┌──────────────────▼──────────────────┐
        │ component.calc_exergy_balance()     │
        │ Calculate E_F, E_P, E_D per component
        │                                     │
        │ Per-component logging also emitted │ ◄─── COMPONENT CALC LOG
        │ (branch, intermediate values, etc.)│
        └──────────────────┬──────────────────┘
                           │
        ┌──────────────────▼──────────────────┐
        │ Calculate component efficiency (y) │
        │ Sum total system destruction        │
        └──────────────────┬──────────────────┘
                           │
              ┌────────────▼────────────┐
              │ Validation & Summary    │
              │ Check E_D matching      │
              │ Generate result tables  │
              └────────────┬────────────┘
                           │
              ┌────────────▼────────────┐
              │   OUTPUT RESULTS        │
              │ - Exergy flows (E_F, E_P, E_L)
              │ - Component efficiencies│
              │ - Destruction summary   │
              │ - Export to JSON/table  │
              └─────────────────────────┘
```

---

## Detailed Code Locations

### PHASE 1: PARSING

#### 1.1 Parser Initialization
**File:** `src/exerpy/parser/from_aspen/aspen_parser.py`  
**Class:** `AspenModelParser`

```python
def __init__(self, model_path, split_physical_exergy=True):
    # Line 20-30: Initialize parser, load model components
    self.components_data = {}
    self.connections_data = {}
```

#### 1.2 Parsing Logic & LOGGING POINT #1
**File:** `src/exerpy/parser/from_aspen/aspen_parser.py`  
**Method:** `parse()` or equivalent (via `from_aspen()` factory)

**Key flow:**
- Extracts component blocks (D1, LK1, ZK1, Splitter, etc.)
- Assigns connectors (inlets/outlets)
- Builds connections dictionary with stream properties

**LOGGING POINT #1: Parsing Completion Summary**
Located after all blocks are parsed and connectors assigned.

```python
# Pseudo-location in aspen_parser.py after all parsing:
logging.info(
    f"Parsing completed: parsed {len(block_names)} blocks, "
    f"connections={len(self.connections_data)} items, "
    f"component groups={len(self.components_data)}"
)
print(msg)  # Ensure output captured in pytest redirected logs
```

**Visible in parser_run.log as:**
```
Parsing completed: parsed 10 blocks, connections=35 items, component groups=12
```

---

### PHASE 2: CALCULATION

#### 2.1 ExergyAnalysis Initialization
**File:** `src/exerpy/analyses.py`  
**Class:** `ExergyAnalysis.__init__()`  
**Lines:** 73-94

```python
def __init__(self, component_data, connection_data, Tamb, pamb, 
             chemExLib=None, split_physical_exergy=True):
    self.Tamb = Tamb
    self.pamb = pamb
    self._component_data = component_data
    self._connection_data = connection_data
    
    # Build component objects from parsed data
    self.components = _construct_components(component_data, connection_data, Tamb)
    self.connections = connection_data
```

#### 2.2 Main Analysis Loop: analyse() Method
**File:** `src/exerpy/analyses.py`  
**Method:** `ExergyAnalysis.analyse(E_F, E_P, E_L)`  
**Lines:** 103-280+

```python
def analyse(self, E_F, E_P, E_L=None):
    # Initialize system exergy values
    self.E_F = 0.0
    self.E_P = 0.0
    self.E_L = 0.0
    
    # Calculate fuel, product, loss exergy (sum across specified connections)
    # ... [exergy summation logic]
    
    # MAIN COMPONENT LOOP (Line ~220 onwards)
    for component in self.components.values():
        
        ╔════════════════════════════════════════════════════════════╗
        ║  LOGGING POINT #2: COMPONENT INPUTS BEFORE CALCULATION    ║
        ║  Lines 254-260 in analyses.py                             ║
        ╚════════════════════════════════════════════════════════════╝
        
        # Construct inlet summary
        inl_summary = []
        for idx, conn in component.inl.items():
            if conn:
                inl_summary.append({
                    'name': conn.get('name'),
                    'T': conn.get('T'),
                    'p': conn.get('p'),
                    'm': conn.get('m'),
                    'h': conn.get('h'),
                    'e_PH': conn.get('e_PH'),
                    'e_T': conn.get('e_T'),
                    'e_M': conn.get('e_M')
                })
        
        # Construct outlet summary (same structure)
        outl_summary = [...]
        
        # Collect power connections
        power_info = {}
        for idx, conn in component.inl.items():
            if conn and conn.get('kind') == 'power':
                power_info[f'in_{idx}'] = conn.get('energy_flow')
        for idx, conn in component.outl.items():
            if conn and conn.get('kind') == 'power':
                power_info[f'out_{idx}'] = conn.get('energy_flow')
        
        # EMIT LOGGING
        msg = (
            f"Component inputs before calc | {component.name} "
            f"({component.__class__.__name__}) | "
            f"inlets={inl_summary} | outlets={outl_summary} | power={power_info}"
        )
        logging.info(msg)  # ← Logger output
        print(msg)         # ← Prints to stdout (captured by pytest)
        
        # NOW CALCULATE (after inputs are logged)
        component.calc_exergy_balance(self.Tamb, self.pamb, self.split_physical_exergy)
```

**Visible in parser_run.log as:**
```
Component inputs before calc | LK1 (Compressor) | inlets=[{'name': 0, 'T': 288.15, 'p': 101325.0, 'm': 29.7656782, 'h': -100458.293, 'e_PH': None, 'e_T': None, 'e_M': None}] | outlets=[{'name': 0, 'T': 388.964645, 'p': 250496.184, 'm': 29.7656782, 'h': 1567.39279, 'e_PH': None, 'e_T': None, 'e_M': None}, ...] | power={'out_1': 3067539.11}
```

#### 2.3 Per-Component Calculation & Logging
**Files (Component-specific):**
- `src/exerpy/components/piping/valve.py` — `calc_exergy_balance()`
- `src/exerpy/components/turbomachinery/compressor.py` — `calc_exergy_balance()`
- `src/exerpy/components/turbomachinery/turbine.py` — `calc_exergy_balance()`
- `src/exerpy/components/nodes/mixer.py` — `calc_exergy_balance()`
- `src/exerpy/components/nodes/splitter.py` — `calc_exergy_balance()`
- `src/exerpy/components/heat_exchanger/base.py` — `calc_exergy_balance()`

Each component emits its own logging after calculations showing:
- Branch selected (which calc method used)
- Intermediate exergy terms (e_F, e_P, e_D per stream)
- Results (E_F, E_P, E_D, epsilon for component)

**Example from splitter.py:**
```python
# Inside calc_exergy_balance():
logging.info(
    f"[Splitter: {self.name}] Branch={branch_label} | "
    f"E_in={E_in} | E_out={E_out} | E_D={E_D}"
)
```

---

## Log Entry Timeline in parser_run.log

```
═══════════════════════════════════════════════════════════════════════
                        PARSER_RUN.LOG TIMELINE
═══════════════════════════════════════════════════════════════════════

Lines 1-100:
  ┌─────────────────────────────────────────┐
  │ ASPEN PARSER INITIALIZATION             │
  │ com_object setup, model loading         │
  └─────────────────────────────────────────┘

Lines 100-600:
  ┌─────────────────────────────────────────┐
  │ STREAM CONVERSION TRACES                 │
  │ convert_to_SI() calls for each stream:   │
  │ "Stream N001: T=288.15 K, p=101325 Pa"  │
  │ (SI unit conversion details)            │
  └─────────────────────────────────────────┘

Lines 600-750:
  ┌─────────────────────────────────────────┐
  │ BLOCK PARSING TRACES                    │
  │ "Parsed block D1 (Compressor)"          │
  │ "Parsed block LK1 (Compressor)"         │
  │ "Parsed block ZK1 (SimpleHeatExchanger)"│
  │ ... (one per component)                 │
  │                                         │
  │ THEN:                                   │
  │ ✓ LOGGING POINT #1 (parser summary)     │
  │ "Parsing completed: X blocks, Y conns" │
  └─────────────────────────────────────────┘

Lines 750-760:
  ┌─────────────────────────────────────────┐
  │ COMPONENT CONSTRUCTION                  │
  │ _construct_components() called          │
  │ Component objects instantiated          │
  └─────────────────────────────────────────┘

Lines 760-1000:
  ┌─────────────────────────────────────────┐
  │ COMPONENT ANALYSIS LOOP                 │
  │                                         │
  │ FOR EACH COMPONENT:                     │
  │ ✓ LOGGING POINT #2 per component        │
  │   "Component inputs before calc | LK1   │
  │    (Compressor) | inlets=[...] | ..."   │
  │                                         │
  │   ↓ calc_exergy_balance() called        │
  │                                         │
  │ ✓ PER-COMPONENT CALC LOGS               │
  │   "[Compressor: LK1] Branch=adia_in..."│
  │   (intermediate results)                │
  └─────────────────────────────────────────┘

Lines 1000+:
  ┌─────────────────────────────────────────┐
  │ RESULTS & VALIDATION                    │
  │ "Exergy destruction check passed"       │
  │ [Test output or error trace]            │
  └─────────────────────────────────────────┘
```

---

## Key Log Sections

### Section A: LOGGING POINT #1 (Parser Completion)
**Location:** Parser_run.log, after all "Parsed block..." lines  
**Indicates:** Parsing phase complete, ready for calculation  
**Captures:** Block count, connection count, component group count

### Section B: LOGGING POINT #2 (Component Inputs)
**Location:** Parser_run.log, immediately before each component's calc  
**Repeats:** Once per component in analysis loop  
**Captures:**
- Component name (e.g., "LK1")
- Component type (e.g., "Compressor")
- Inlet streams: T, p, m, h, e_PH, e_T, e_M
- Outlet streams: (same structure)
- Power connections: in/out power values

**Critical insight:** Shows whether streams have None values for required fields (e.g., e_PH=None) **before** calc runs.

### Section C: Per-Component Calc Logs
**Location:** Parser_run.log, immediately after LOGGING POINT #2  
**Repeats:** Once per component  
**Example branches:**
- Compressor: "adiabatic_inlet" / "adiabatic_outlet"
- Turbine: "adiabatic" / "polytropic"
- Valve: "isenthalpic"
- HeatExchanger: "heating" / "cooling"

---

## Code Changes Summary

| Phase | File | Method | Lines | Change Type |
|-------|------|--------|-------|-------------|
| **PARSE** | `aspen_parser.py` | `parse()` | ~450-550 | Added summary log after connector assignment |
| **CALC-INIT** | `analyses.py` | `__init__()` | 73-94 | No change (baseline) |
| **CALC-MAIN** | `analyses.py` | `analyse()` | 254-260 | **✓ ADDED: Component input dump logging** |
| **CALC-COMP** | `valve.py` | `calc_exergy_balance()` | ~40-60 | Added branch & result logging |
| **CALC-COMP** | `compressor.py` | `calc_exergy_balance()` | ~40-80 | Added branch & power logging |
| **CALC-COMP** | `turbine.py` | `calc_exergy_balance()` | ~40-80 | Added branch & outlet sum logging |
| **CALC-COMP** | `mixer.py` | `calc_exergy_balance()` | ~40-60 | Added inlet summary logging |
| **CALC-COMP** | `splitter.py` | `calc_exergy_balance()` | ~40-60 | Added outlet summary logging |
| **CALC-COMP** | `heat_exchanger/base.py` | `calc_exergy_balance()` | ~80-120 | Added 4-stream branch logging |

---

## Diagnostic Value

The logging hierarchy provides **end-to-end traceability**:

1. **Parser logs** confirm all blocks extracted and connections built
2. **Component input logs** (POINT #2) show raw inlet/outlet state **before math**
   - Reveals if required fields are None (e.g., `e_PH: None`)
   - Pinpoints which stream lacks data
3. **Per-component calc logs** show which branch executed and what results computed
4. **System validation logs** verify energy balance closure

**If calc fails:** The component input log immediately preceding the error traceback tells you exactly which stream had which None fields.

