# Component Input Logging: Code Location Diagram

## Exact Location of "Component inputs before calc" Log

```
╔════════════════════════════════════════════════════════════════════════════╗
║                     src/exerpy/analyses.py                                 ║
║                  ExergyAnalysis.analyse() method                            ║
╚════════════════════════════════════════════════════════════════════════════╝

Line Range: 220-270 (within the main component loop)

                    ┌───────────────────────────────────┐
                    │  Line ~150                        │
                    │  def analyse(self, E_F, E_P, ...):│
                    │  ├─ Initialize E_F, E_P, E_L      │
                    │  ├─ Validate connections          │
                    │  ├─ Calculate system exergy flows │
                    │  │                                │
                    │  └─ FOR LOOP begins (Line ~220)   │
                    │     for component in             │
                    │         self.components.values(): │
                    └────────────────┬──────────────────┘
                                     │
                    ┌────────────────▼──────────────────┐
                    │  Line 220-240                     │
                    │  Component data extraction        │
                    │  ├─ Access component.inl (inlets) │
                    │  ├─ Access component.outl (outlets)
                    │  ├─ Extract T, p, m, h            │
                    │  ├─ Extract e_PH, e_T, e_M        │
                    │  └─ Build summary dicts           │
                    └────────────────┬──────────────────┘
                                     │
    ╔════════════════════════════════▼════════════════════════════════╗
    ║                   LOGGING POINT #2                              ║
    ║            Lines 254-260 in analyses.py                         ║
    ║                                                                  ║
    ║  ┌────────────────────────────────────────────────────────────┐ ║
    ║  │ # Emit both print & logging                               │ ║
    ║  │ msg = (                                                    │ ║
    ║  │     f"Component inputs before calc | "                    │ ║
    ║  │     f"{component.name} "                                  │ ║
    ║  │     f"({component.__class__.__name__}) | "               │ ║
    ║  │     f"inlets={inl_summary} | "                           │ ║
    ║  │     f"outlets={outl_summary} | "                         │ ║
    ║  │     f"power={power_info}"                                │ ║
    ║  │ )                                                         │ ║
    ║  │ logging.info(msg)      ← Python logging module          │ ║
    ║  │ print(msg)             ← Print to stdout                │ ║
    ║  └────────────────────────────────────────────────────────────┘ ║
    ║                                                                  ║
    ║  Output Example (from parser_run.log):                          ║
    ║  ┌────────────────────────────────────────────────────────────┐ ║
    ║  │ Component inputs before calc | LK1 (Compressor) |          │ ║
    ║  │ inlets=[{'name': 0, 'T': 288.15, 'p': 101325.0,            │ ║
    ║  │ 'm': 29.7656782, 'h': -100458.293, 'e_PH': None,           │ ║
    ║  │ 'e_T': None, 'e_M': None}] |                               │ ║
    ║  │ outlets=[{'name': 0, 'T': 388.964645, ...                  │ ║
    ║  │ 'e_PH': None, ...}] | power={'out_1': 3067539.11}         │ ║
    ║  └────────────────────────────────────────────────────────────┘ ║
    ╚════════════════════════════════════════════════════════════════╗

                                     │
                    ┌────────────────▼──────────────────┐
                    │  Line 263-265                     │
                    │  COMPONENT CALCULATION            │
                    │  component.calc_exergy_balance()  │
                    │  ├─ Each component determines     │
                    │  │  which exergy balance branch   │
                    │  │  to use (adiabatic/poly/etc)   │
                    │  │                                │
                    │  ├─ Uses inlet/outlet data        │
                    │  ├─ Computes E_F, E_P, E_D        │
                    │  │                                │
                    │  ├─ Emits per-component logs      │
                    │  │  (branch + intermediate terms) │
                    │  │                                │
                    │  └─ Returns (no print, uses log)  │
                    └────────────────┬──────────────────┘
                                     │
                    ┌────────────────▼──────────────────┐
                    │  Line 266-272                     │
                    │  Component efficiency calculation │
                    │  ├─ Calculate y = E_D / E_F       │
                    │  ├─ Calculate y* = E_D / E_D      │
                    │  └─ Sum total E_D                 │
                    └────────────────┬──────────────────┘
                                     │
                    ┌────────────────▼──────────────────┐
                    │  LOOP continues or exits          │
                    │  (next component or end)          │
                    └─────────────────────────────────────┘
```

---

## Data Flow: From Connection Dict to Log Output

```
┌──────────────────────────────────────────┐
│  connection_data (parsed by AspenParser) │
│  {                                       │
│    "0": {                                │
│      "name": "Stream-001",               │
│      "T": 288.15,          ◄─ Temperature
│      "p": 101325.0,        ◄─ Pressure
│      "m": 29.7656782,      ◄─ Mass flow
│      "h": -100458.293,     ◄─ Specific enthalpy
│      "e_PH": None,         ◄─ Exergy (physical)
│      "e_T": None,          ◄─ Exergy (thermal)
│      "e_M": None,          ◄─ Exergy (mechanical)
│      "e_CH": None          ◄─ Exergy (chemical)
│    },
│    "1": { ... },
│    ...
│  }
└──────────────────────────────────────────┘
          │
          │ (used to construct)
          ▼
┌──────────────────────────────────────────┐
│  component.inl & component.outl dicts    │
│  {0: {...}, 1: {...}}                    │
└──────────────────────────────────────────┘
          │
          │ (extracted in analyses.py:254-260)
          ▼
┌──────────────────────────────────────────┐
│  inl_summary, outl_summary lists         │
│  [{'name': 0, 'T': 288.15, ...}]         │
└──────────────────────────────────────────┘
          │
          │ (formatted into)
          ▼
┌──────────────────────────────────────────┐
│  msg string with full component state    │
│  "Component inputs before calc | LK1 ... │
└──────────────────────────────────────────┘
          │
    ┌─────┴─────┐
    │           │
    ▼           ▼
  logging.info() print()   ◄─ Both outputs
    │           │
    └─────┬─────┘
          │
          ▼
    ┌──────────────────┐
    │ parser_run.log   │
    │ (pytest redirect)│
    └──────────────────┘
```

---

## Reading the Log Entries

### Example Compressor Entry (Line 742 in parser_run.log)

```
Component inputs before calc | LK1 (Compressor) | 
inlets=[
  {
    'name': 0,
    'T': 288.15,           ← K (Kelvin)
    'p': 101325.0,         ← Pa (Pascals)
    'm': 29.7656782,       ← kg/s (mass flow rate)
    'h': -100458.293,      ← J/kg (specific enthalpy)
    'e_PH': None,          ◄─ PROBLEM: Should have numeric value!
    'e_T': None,           ◄─ PROBLEM: Should have numeric value!
    'e_M': None            ◄─ PROBLEM: Should have numeric value!
  }
] | 
outlets=[
  {
    'name': 0,
    'T': 388.964645,
    'p': 250496.184,
    'e_PH': None,          ◄─ PROBLEM
    ...
  },
  {
    'name': 1,
    'T': None,             ◄─ Secondary outlet (not used)
    'p': None,
    'm': None,
    ...
  }
] | 
power={'out_1': 3067539.11}    ← Power out: 3.07 MW
```

### What Each Field Means

| Field | Unit | Source | Meaning |
|-------|------|--------|---------|
| `name` | – | Connection ID | Stream/port identifier |
| `T` | K | Aspen thermodynamic | Temperature |
| `p` | Pa | Aspen thermodynamic | Pressure |
| `m` | kg/s | Aspen mass balance | Mass flow rate |
| `h` | J/kg | Aspen property tables | Specific enthalpy |
| `e_PH` | J/kg | Calculated later | Physical exergy (**None here because not yet calculated**) |
| `e_T` | J/kg | Calculated later | Thermal exergy component |
| `e_M` | J/kg | Calculated later | Mechanical exergy component |

---

## Why This Log Is Placed Here (Before calc_exergy_balance)

```
TIMING DIAGRAM:

        ↓ Loop iteration N
        
  Line 254-260: Log component.inl / component.outl
        ↑
        │ At this point:
        │ ├─ Parser has populated T, p, m, h (from Aspen)
        │ ├─ exergy fields (e_PH, e_T, e_M) are NOT yet calculated
        │ │  (they're populated by component.calc_exergy_balance)
        │ ├─ We log the raw state (as it comes from parser)
        │ └─ This is the LAST chance to see original parsed values
        
  Line 263: component.calc_exergy_balance(Tamb, pamb, ...)
        ↑
        │ After this call:
        │ ├─ Component has calculated its exergy balance
        │ ├─ E_F, E_P, E_D are now populated
        │ └─ Exergy terms (e_PH, e_T, e_M) may have been used internally
        
        ↓ Result: E_F, E_P, E_D populated on component object
```

**Diagnostic insight:** The log shows exactly what each component "sees" as input—if it's None or has unexpected value, it's logged before the calc fails.

---

## How to Use This Log for Debugging

### Scenario: calc_exergy_balance() fails

```
parser_run.log contents:

Line 754:
Component inputs before calc | SPLIT1 (Splitter) | inlets=[{'name': 0, 'T': 308.15, 'p': 624000.0, 'm': 29.5600064, 'h': 8439.18602, 'e_PH': None, 'e_T': None, 'e_M': None}] | ...

Line 755:
Traceback (most recent call last):
  File "src/exerpy/components/nodes/splitter.py", line 63, in calc_exergy_balance
    E_in = sum(inlet.get("m", 0) * inlet.get("e_PH") for inlet in inlet_list)
TypeError: unsupported operand type(s) for *: 'float' and 'NoneType'
```

**Diagnosis:** 
- Line 754 shows SPLIT1's inlet has `e_PH: None`
- Line 755 shows calc fails trying to use that None value in math
- **Root cause:** Parser didn't populate `e_PH` (expected in connection dict)
- **Fix options:**
  1. Have parser calculate e_PH before passing to components
  2. Have component.calc_exergy_balance() handle None gracefully
  3. Have component raise clear error identifying missing field

---

## Traceability: Which Log Line Precedes Which Error?

```
Parser_run.log structure during component calculation:

[Block parsing phase]
...
"Parsed block LK1 ..."
"Parsed block ZK1 ..."
...
"Parsing completed: X blocks, Y connections, Z groups"

[Component analysis phase]
"Component inputs before calc | LK1 (Compressor) | ..."     ← Log before calc
[LK1 calc logs (branch, intermediate)]                      ← Per-component output
"Component inputs before calc | LK2 (Compressor) | ..."     ← Next component
[LK2 calc logs]
...
"Component inputs before calc | SPLIT1 (Splitter) | ..."    ← Problem component
Traceback (...)                                              ← Error occurs here!
  File "splitter.py", line 63, ...
  TypeError: unsupported operand type(s) for *: 'float' and 'NoneType'

ACTION: Look backward from error to find "Component inputs before calc | SPLIT1..."
        ↑ This log shows exactly what SPLIT1 received as input
```

