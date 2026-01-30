# Visual Schematic: Analysis & Logging Flow

## ╔════════════════════════════════════════════════════════════════════════════╗
## ║                   EXERGY ANALYSIS: PARSE → CALCULATE                       ║
## ╚════════════════════════════════════════════════════════════════════════════╝

```
                              ┏━━━━━━━━━━━━━┓
                              ┃   INPUT     ┃
                              ┃  Aspen.bkp  ┃
                              ┗━━━━━┳━━━━━━┛
                                    │
                    ╔═══════════════▼═══════════════╗
                    ║                               ║
                    ║   PHASE 1: PARSING            ║
                    ║   (AspenModelParser)          ║
                    ║                               ║
                    ║ ┌─────────────────────────┐  ║
                    ║ │ • Extract 10 blocks     │  ║
                    ║ │ • Build connections     │  ║
                    ║ │ • Parse streams         │  ║
                    ║ │ • Convert to SI units   │  ║
                    ║ └─────────────────────────┘  ║
                    ║           ↓                  ║
                    ║ ✓ LOG #1: "Parsing          ║
                    ║   completed: 10 blocks,    ║
                    ║   35 connections"           ║
                    ║                               ║
                    ╚═══════════════╤═══════════════╝
                                    │
                    ╔═══════════════▼═══════════════╗
                    ║                               ║
                    ║   PHASE 2: CALCULATION        ║
                    ║   (ExergyAnalysis)            ║
                    ║                               ║
                    ║ ┌─────────────────────────┐  ║
                    ║ │ construct_components()  │  ║
                    ║ │ • Build 12 components   │  ║
                    ║ │ • Assign inlets/outlets │  ║
                    ║ └─────────────────────────┘  ║
                    ║           ↓                  ║
                    ║ ┌─────────────────────────┐  ║
                    ║ │ analyse(E_F, E_P, E_L) │  ║
                    ║ │ • Sum fuel exergy       │  ║
                    ║ │ • Sum product exergy    │  ║
                    ║ │ • Sum loss exergy       │  ║
                    ║ └────────────┬────────────┘  ║
                    ║              ↓               ║
                    ║  FOR component in components: ║
                    ║              ↓               ║
                    ║ ╔───────────────────────────╗║
                    ║ ║                           ║║
                    ║ ║ ✓ LOG #2: "Component     ║║ ← YOU ARE HERE
                    ║ ║   inputs before calc"    ║║   (Lines 251-260)
                    ║ ║                           ║║
                    ║ ║ Lines 208-248:            ║║
                    ║ ║ • Extract inl_summary     ║║
                    ║ ║ • Extract outl_summary    ║║
                    ║ ║ • Extract power_info      ║║
                    ║ ║                           ║║
                    ║ ║ Lines 251-260:            ║║
                    ║ ║ • Build msg with all data║║
                    ║ ║ • logging.info(msg)       ║║
                    ║ ║ • print(msg)              ║║
                    ║ ║                           ║║
                    ║ ║ OUTPUT:                   ║║
                    ║ ║ "Component inputs        ║║
                    ║ ║  before calc | LK1       ║║
                    ║ ║  (Compressor) | inlets=  ║║
                    ║ ║  [{T: 288.15, p: 101325..║║
                    ║ ║                           ║║
                    ║ ╚─────────────┬─────────────╝║
                    ║               ↓              ║
                    ║  Line 262-263:               ║
                    ║  component.calc_exergy_balance()
                    ║               ↓              ║
                    ║ ✓ LOG #3: Per-component     ║
                    ║   calc logs (branch +       ║
                    ║   intermediate values)      ║
                    ║               ↓              ║
                    ║  Lines 265-275:             ║
                    ║  • Calculate efficiency (y) ║
                    ║  • Sum component E_D        ║
                    ║               ↓              ║
                    ║  (Next component)           ║
                    ║                               ║
                    ║ ┌─────────────────────────┐  ║
                    ║ │ Validation               │  ║
                    ║ │ • Check E_D balance      │  ║
                    ║ │ • Generate result tables │  ║
                    ║ └─────────────────────────┘  ║
                    ║                               ║
                    ╚═══════════════╤═══════════════╝
                                    │
                    ╔═══════════════▼═══════════════╗
                    ║   OUTPUT                      ║
                    ║   (parser_run.log)            ║
                    ║                               ║
                    ║ • Parsing traces              ║
                    ║ • All "Component inputs       ║
                    ║   before calc" entries        ║
                    ║ • Per-component calc logs     ║
                    ║ • Error traces (if any)       ║
                    ║ • Result summary              ║
                    ║                               ║
                    ╚═══════════════╧═══════════════╝
```

---

## ╔════════════════════════════════════════════════════════════════════════════╗
## ║              DETAILED: COMPONENT INPUTS BEFORE CALC LOG                    ║
## ╚════════════════════════════════════════════════════════════════════════════╝

```
┌────────────────────────────────────────────────────────────────────────────┐
│                                                                             │
│  FILE: src/exerpy/analyses.py                                              │
│  METHOD: ExergyAnalysis.analyse(self, E_F, E_P, E_L)                       │
│  LINES: 251-260 (inside the main component loop)                           │
│                                                                             │
│  ┌──────────────────────────────────────────────────────────────────────┐ │
│  │ Line 200:  for component in self.components.values():               │ │
│  │              ┌─────────────────────────────────┐                    │ │
│  │ Line 208:    │ Extract inlet summary           │                    │ │
│  │ Line 210:    │ for k, v in component.inl.items()                    │ │
│  │ Line 212-221 │   append {'name', 'T', 'p', 'm', 'h', ...}          │ │
│  │              └─────────────────────────────────┘                    │ │
│  │                                                                     │ │
│  │              ┌─────────────────────────────────┐                    │ │
│  │ Line 224:    │ Extract outlet summary (same)   │                    │ │
│  │ Line 226:    │ for k, v in component.outl.items()                   │ │
│  │ Line 228-237 │   append {'name', 'T', 'p', 'm', 'h', ...}          │ │
│  │              └─────────────────────────────────┘                    │ │
│  │                                                                     │ │
│  │              ┌─────────────────────────────────┐                    │ │
│  │ Line 242:    │ Extract power connections      │                    │ │
│  │ Line 244-249 │ for in/out power (kind='power')│                    │ │
│  │              └─────────────────────────────────┘                    │ │
│  │                ↓                                                   │ │
│  │  ╔═══════════════════════════════════════════════════════════════╗ │ │
│  │  ║                                                               ║ │ │
│  │  ║  Line 251-258: BUILD MESSAGE STRING                          ║ │ │
│  │  ║  ┌───────────────────────────────────────────────────────┐  ║ │ │
│  │  ║  │ msg = (                                               │  ║ │ │
│  │  ║  │   f"Component inputs before calc | "                 │  ║ │ │
│  │  ║  │   f"{component.name} "                               │  ║ │ │
│  │  ║  │   f"({component.__class__.__name__}) | "             │  ║ │ │
│  │  ║  │   f"inlets={inl_summary} | "                         │  ║ │ │
│  │  ║  │   f"outlets={outl_summary} | "                       │  ║ │ │
│  │  ║  │   f"power={power_info}"                              │  ║ │ │
│  │  ║  │ )                                                     │  ║ │ │
│  │  ║  └───────────────────────────────────────────────────────┘  ║ │ │
│  │  ║                ↓                                            ║ │ │
│  │  ║  Line 259: logging.info(msg)   ◄─ Log to logging module    ║ │ │
│  │  ║  Line 260: print(msg)          ◄─ Print to stdout           ║ │ │
│  │  ║                                                               ║ │ │
│  │  ║  → Both captured in parser_run.log (pytest redirect)         ║ │ │
│  │  ║                                                               ║ │ │
│  │  ╚═══════════════════════════════════════════════════════════════╝ │ │
│  │                ↓                                                   │ │
│  │ Line 262-263: component.calc_exergy_balance(Tamb, pamb, ...)      │ │
│  │              (Component performs exergy calculation)              │ │
│  │                ↓                                                   │ │
│  │ Line 265-275: Efficiency calculation & accumulation               │ │
│  │                ↓                                                   │ │
│  │              (Next component or end loop)                         │ │
│  │                                                                     │ │
│  └─────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## ╔════════════════════════════════════════════════════════════════════════════╗
## ║                    LOG MESSAGE CONTENT BREAKDOWN                           ║
## ╚════════════════════════════════════════════════════════════════════════════╝

```
FULL LOG ENTRY:
┌─────────────────────────────────────────────────────────────────────────────┐
│ Component inputs before calc | LK1 (Compressor) | inlets=[...] | outlets=...│
│                                                                              │
│ ┌──────────────────────────────────────────────────────────────────────────┐│
│ │ Part 1: "Component inputs before calc |"                                 ││
│ │         ↑ Fixed label to identify log type                              ││
│ └──────────────────────────────────────────────────────────────────────────┘│
│                                                                              │
│ ┌──────────────────────────────────────────────────────────────────────────┐│
│ │ Part 2: "LK1 (Compressor) |"                                             ││
│ │         ↑ Component name and type from component object                 ││
│ │         (component.name, component.__class__.__name__)                  ││
│ └──────────────────────────────────────────────────────────────────────────┘│
│                                                                              │
│ ┌──────────────────────────────────────────────────────────────────────────┐│
│ │ Part 3: "inlets=[{'name': 0, 'T': 288.15, ...}, ...] |"                 ││
│ │         ↑ List of inlet stream dicts from component.inl                 ││
│ │         Each inlet has: name, T, p, m, h, e_PH, e_T, e_M               ││
│ │         e_* fields are None (not yet calculated)                        ││
│ └──────────────────────────────────────────────────────────────────────────┘│
│                                                                              │
│ ┌──────────────────────────────────────────────────────────────────────────┐│
│ │ Part 4: "outlets=[{'name': 0, 'T': 388.96, ...}, ...] |"                ││
│ │         ↑ List of outlet stream dicts (same structure as inlets)        ││
│ │         Multiple outlets show split/mixing components                   ││
│ └──────────────────────────────────────────────────────────────────────────┘│
│                                                                              │
│ ┌──────────────────────────────────────────────────────────────────────────┐│
│ │ Part 5: "power={'out_1': 3067539.11}"                                    ││
│ │         ↑ Power connections (work/heat flows) if present                ││
│ │         Key: in_<idx> / out_<idx>                                       ││
│ │         Value: power in Watts                                           ││
│ └──────────────────────────────────────────────────────────────────────────┘│
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## ╔════════════════════════════════════════════════════════════════════════════╗
## ║                        READING THE LOG STEP-BY-STEP                        ║
## ╚════════════════════════════════════════════════════════════════════════════╝

```
STEP 1: Open parser_run.log
   ↓
STEP 2: Search for "Component inputs before calc | <component_name>"
   ↓
STEP 3: Read the inlet data:
   • Check T (temperature in K)
   • Check p (pressure in Pa)
   • Check m (mass flow in kg/s)
   • Check h (specific enthalpy in J/kg)
   • Check e_PH, e_T, e_M (exergy components — likely None)
   ↓
STEP 4: Read the outlet data (same structure):
   • Multiple outlets? Component is a splitter/mixer
   • Some outlets None? Component has unused ports
   ↓
STEP 5: Check power_info:
   • Empty {}? No power connections (e.g., splitter)
   • Values? Component has power input/output (e.g., compressor)
   ↓
STEP 6: Look for error immediately after:
   • If calc succeeds: Next log line is per-component calc log
   • If calc fails: Next line is Traceback (...)
     → The "Component inputs before calc" log shows WHY it failed!
```

---

## ╔════════════════════════════════════════════════════════════════════════════╗
## ║                        DATA FLOW DIAGRAM                                   ║
## ╚════════════════════════════════════════════════════════════════════════════╝

```
                 ┌──────────────────────────┐
                 │  Aspen Parser            │
                 │  (extracts from .bkp)    │
                 └────────────┬─────────────┘
                              │
         ┌────────────────────▼────────────────────┐
         │ connection_data dict                     │
         │ {                                        │
         │   "stream_0": {                          │
         │     "T": 288.15,                         │
         │     "p": 101325,                         │
         │     "m": 29.77,                          │
         │     "h": -100458,                        │
         │     "e_PH": None,  ← Not yet calculated │
         │     ...                                  │
         │   },                                     │
         │   ...                                    │
         │ }                                        │
         └────────────────────┬────────────────────┘
                              │
         ┌────────────────────▼────────────────────┐
         │ _construct_components()                  │
         │ Builds Component objects                │
         │ Assigns component.inl & component.outl  │
         └────────────────────┬────────────────────┘
                              │
         ┌────────────────────▼────────────────────┐
         │ ExergyAnalysis.analyse()                │
         │ FOR component in self.components:       │
         │   ↓                                     │
         │   Extract inl_summary from component.inl
         │   Extract outl_summary from component.outl
         │   Extract power_info from connections   │
         │   ↓                                     │
         └────────────────────┬────────────────────┘
                              │
                   ┌──────────▼──────────┐
                   │ Lines 251-260:      │
                   │                     │
                   │ Build msg string    │
                   │ logging.info(msg)   │
                   │ print(msg)          │
                   │                     │
                   │ Output:             │
                   │ "Component inputs   │
                   │  before calc | ..." │
                   └──────────┬──────────┘
                              │
                   ┌──────────▼──────────┐
                   │ parser_run.log      │
                   │ (pytest captured)   │
                   └─────────────────────┘
```

---

## ╔════════════════════════════════════════════════════════════════════════════╗
## ║                           KEY TAKEAWAYS                                    ║
## ╚════════════════════════════════════════════════════════════════════════════╝

```
✓ WHERE:     src/exerpy/analyses.py, Lines 251-260
✓ WHEN:      Right before each component.calc_exergy_balance() call
✓ WHAT:      Snapshot of component's input streams (T, p, m, h, e_*)
✓ WHY:       Diagnose missing/None fields before calc fails
✓ OUTPUT:    Captured in parser_run.log (pytest stdout redirect)
✓ BOTH:      logging.info() + print() ensure log appears
✓ INSIDE:    Main component iteration loop (Line 200: for component in ...)
✓ BEFORE:    component.calc_exergy_balance() (Line 262)
✓ SHOWS:     Exact data each component receives from parser
✓ IF ERROR:  Look backward from traceback to find this log entry
             ↓ Shows which field was None/missing
```

---

## ╔════════════════════════════════════════════════════════════════════════════╗
## ║                     EXAMPLE PARSER_RUN.LOG EXCERPT                        ║
## ╚════════════════════════════════════════════════════════════════════════════╝

```
[Lines 740-755 from actual parser_run.log]

Component inputs before calc | LK1 (Compressor) | 
inlets=[{'name': 0, 'T': 288.15, 'p': 101325.0, 'm': 29.7656782, 
         'h': -100458.293, 'e_PH': None, 'e_T': None, 'e_M': None}] | 
outlets=[{'name': 0, 'T': 388.964645, 'p': 250496.184, 'm': 29.7656782, 
          'h': 1567.39279, 'e_PH': None, 'e_T': None, 'e_M': None}, 
         {'name': 1, 'T': None, 'p': None, 'm': None, 'h': None, 
          'e_PH': None, 'e_T': None, 'e_M': None}] | 
power={'out_1': 3067539.11}

Component inputs before calc | LK2 (Compressor) | 
inlets=[{'name': 0, 'T': 308.15, 'p': 240496.184, 'm': 29.7656782, 
         'h': -80601.4373, 'e_PH': None, 'e_T': None, 'e_M': None}] | 
outlets=[{'name': 1, 'T': None, 'p': None, 'm': None, 'h': None, 
          'e_PH': None, 'e_T': None, 'e_M': None}, 
         {'name': 0, 'T': 426.593398, 'p': 644000.0, 'm': 29.7656782, 
          'h': 39546.3909, 'e_PH': None, 'e_T': None, 'e_M': None}] | 
power={'out_1': 3612405.65}

...

Component inputs before calc | SPLIT1 (Splitter) | 
inlets=[{'name': 0, 'T': 308.15, 'p': 624000.0, 'm': 29.5600064, 
         'h': 8439.18602, 'e_PH': None, 'e_T': None, 'e_M': None}] | 
outlets=[{'name': 1, 'T': 308.15, 'p': 624000.0, 'm': 24.8304054, 
          'h': 8439.18602, 'e_PH': None, 'e_T': None, 'e_M': None}, 
         {'name': 0, 'T': 308.15, 'p': 624000.0, 'm': 4.72960103, 
          'h': 8439.18602, 'e_PH': None, 'e_T': None, 'e_M': None}] | 
power={}
```

**What this shows:**
- Components processed in order: LK1, LK2, ..., SPLIT1
- Each has proper thermodynamic data (T, p, m, h)
- Exergy fields (e_PH, e_T, e_M) are None (not yet calculated)
- Power connections captured (compressors have power out)
- Splitter has one inlet, two outlets (correct flow structure)

