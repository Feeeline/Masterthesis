# Summary: Component Input Logging Architecture

## Quick Reference

### **Where Is the Logging?**

**File:** `src/exerpy/analyses.py`  
**Lines:** 251-260 (inside the `analyse()` method)  
**Context:** In the main component iteration loop (Line 200: `for component in self.components.values()`)

```python
# Lines 251-260
msg = (
    f"Component inputs before calc | {component.name} ({component.__class__.__name__}) | "
    f"inlets={inl_summary} | outlets={outl_summary} | power={power_info}"
)
logging.info(msg)
print(msg)
```

---

## The Complete Analysis Flow

### **Phase 1: PARSING** (AspenParser → JSON)

```
Aspen .bkp File
        ↓
AspenModelParser.initialize_model()
        ↓
AspenModelParser.parse_blocks()     [Extracts components: D1, LK1, ZK1, etc.]
        ↓
AspenModelParser.assign_connectors() [Builds inlet/outlet connections]
        ↓
ExergyAnalysis.__init__()           [Receives component_data, connection_data]
        ↓
_construct_components()             [Builds Component objects from parsed data]
```

**Parsing Completion Log (Parser summary):**  
"Parsing completed: X blocks, Y connections, Z component groups"

---

### **Phase 2: CALCULATION** (Per-Component Exergy Analysis)

```
ExergyAnalysis.analyse(E_F, E_P, E_L)
    ↓
    [Calculate system-level fuel, product, loss exergy]
    ↓
    FOR component in self.components.values():
        ↓
        ┌─────────────────────────────────────────────┐
        │ Lines 208-248: BUILD SUMMARY DICTS          │
        │ ├─ inl_summary (extract T, p, m, h, e_*)   │
        │ ├─ outl_summary (extract T, p, m, h, e_*)  │
        │ └─ power_info (extract power connections)  │
        └──────────────┬──────────────────────────────┘
                       ↓
        ┌─────────────────────────────────────────────┐
        │ ✓ LOGGING POINT #2 (Lines 251-260)          │
        │ "Component inputs before calc | ..."        │
        │ ├─ logging.info(msg)                        │
        │ └─ print(msg)                               │
        └──────────────┬──────────────────────────────┘
                       ↓
        ┌─────────────────────────────────────────────┐
        │ Lines 262-263: COMPONENT CALCULATION        │
        │ component.calc_exergy_balance(...)          │
        │ ├─ Determines branch (adiabatic/poly/etc)   │
        │ ├─ Uses inlet/outlet properties             │
        │ ├─ Calculates E_F, E_P, E_D                 │
        │ └─ Emits per-component calc logs            │
        └──────────────┬──────────────────────────────┘
                       ↓
        ┌─────────────────────────────────────────────┐
        │ Lines 265-275: EFFICIENCY & ACCUMULATION    │
        │ ├─ Calculate y and y*                       │
        │ └─ Sum component exergy destructions        │
        └──────────────┬──────────────────────────────┘
                       ↓
    [Next component or end loop]
        ↓
    [Validation & result generation]
```

---

## What Data Is Logged?

At lines 251-260, the log captures **exactly what each component receives as input**, including:

```
Component inputs before calc | <NAME> (<TYPE>) | 
inlets=[
  {
    'name': <stream_id>,
    'T': <temperature_K>,
    'p': <pressure_Pa>,
    'm': <mass_flow_kg_s>,
    'h': <specific_enthalpy_J_kg>,
    'e_PH': <physical_exergy_J_kg_or_None>,
    'e_T': <thermal_exergy_J_kg_or_None>,
    'e_M': <mechanical_exergy_J_kg_or_None>
  },
  ...
] | 
outlets=[
  {
    'name': <stream_id>,
    'T': ..., 'p': ..., 'm': ..., 'h': ...,
    'e_PH': None, 'e_T': None, 'e_M': None
  },
  ...
] | 
power={
  'in_<idx>': <power_W>,
  'out_<idx>': <power_W>,
  ...
}
```

---

## Key Observations

### 1. **Timing: Before vs. After Calculation**
- **Log is emitted:** Right before `component.calc_exergy_balance()` is called
- **Exergy fields (e_PH, e_T, e_M):** Present in log as `None` (not yet calculated)
- **Why:** Log shows raw parsed data, **before** component math modifies it

### 2. **Data Sources**
| Field | From Where |
|-------|-----------|
| T, p, m, h | Aspen thermodynamic model |
| e_PH, e_T, e_M | Not yet calculated (will be during `calc_exergy_balance`) |
| Power | Connection dict (if kind="power") |

### 3. **Dual Output (logging + print)**
```python
logging.info(msg)  # For logger configuration (may or may not appear)
print(msg)         # For stdout (guaranteed in pytest redirected logs)
```
Both are sent to `parser_run.log` when tests redirect stdout/stderr.

---

## Diagnostic Use Cases

### Case 1: "My component calc failed"
**Step 1:** Open `parser_run.log`  
**Step 2:** Find the error traceback  
**Step 3:** Scroll UP to the line that starts with `"Component inputs before calc | <component_name>..."`  
**Step 4:** Check which fields are `None` or unexpected  
**Action:** If exergy fields are None, the component received unpopulated data from the parser

### Case 2: "How is the flow of execution?"
**Step 1:** Open `parser_run.log`  
**Step 2:** Look for `"Parsing completed: ..."` ← Marks end of parsing  
**Step 3:** Look for `"Component inputs before calc | LK1 ..."`  ← Start of component loop
**Step 4:** Look for per-component calc logs (after each "Component inputs...")  
**Step 5:** Identify which component stopped execution

### Case 3: "What were the exact values used in calc?"
**Step 1:** Find the component in `parser_run.log`  
**Step 2:** The "Component inputs before calc" line shows exact T, p, m, h values parsed  
**Step 3:** The per-component calc log (lines below it) shows branch chosen and intermediate terms

---

## Files Generated (Documentation)

These three markdown files explain the logging from different perspectives:

1. **`ANALYSIS_FLOW_SCHEMATIC.md`**
   - High-level workflow diagram (parse → calculate)
   - Log entry timeline
   - Code changes summary table

2. **`COMPONENT_INPUT_LOG_LOCATION.md`**
   - Exact code location with ASCII art diagram
   - Data flow from connection dict → log output
   - How to read log entries

3. **`CODE_LOCATION_REFERENCE.md`**
   - Exact line numbers (251-260) and full context
   - Variable types and sources at logging point
   - Why both `logging.info()` and `print()` are used

---

## Log Output Example

```
[From parser_run.log, Lines 742-754]

Component inputs before calc | LK1 (Compressor) | inlets=[{'name': 0, 'T': 288.15, 'p': 101325.0, 'm': 29.7656782, 'h': -100458.293, 'e_PH': None, 'e_T': None, 'e_M': None}] | outlets=[{'name': 0, 'T': 388.964645, 'p': 250496.184, 'm': 29.7656782, 'h': 1567.39279, 'e_PH': None, 'e_T': None, 'e_M': None}, {'name': 1, 'T': None, 'p': None, 'm': None, 'h': None, 'e_PH': None, 'e_T': None, 'e_M': None}] | power={'out_1': 3067539.11}

Component inputs before calc | LK2 (Compressor) | inlets=[{'name': 0, 'T': 308.15, 'p': 240496.184, 'm': 29.7656782, 'h': -80601.4373, 'e_PH': None, 'e_T': None, 'e_M': None}] | outlets=[{'name': 1, 'T': None, 'p': None, 'm': None, 'h': None, 'e_PH': None, 'e_T': None, 'e_M': None}, {'name': 0, 'T': 426.593398, 'p': 644000.0, 'm': 29.7656782, 'h': 39546.3909, 'e_PH': None, 'e_T': None, 'e_M': None}] | power={'out_1': 3612405.65}

...

Component inputs before calc | SPLIT1 (Splitter) | inlets=[{'name': 0, 'T': 308.15, 'p': 624000.0, 'm': 29.5600064, 'h': 8439.18602, 'e_PH': None, 'e_T': None, 'e_M': None}] | outlets=[{'name': 1, 'T': 308.15, 'p': 624000.0, 'm': 24.8304054, 'h': 8439.18602, 'e_PH': None, 'e_T': None, 'e_M': None}, {'name': 0, 'T': 308.15, 'p': 624000.0, 'm': 4.72960103, 'h': 8439.18602, 'e_PH': None, 'e_T': None, 'e_M': None}] | power={}
```

**Key observations from this output:**
- ✓ Components are processed in order (LK1 → LK2 → ... → SPLIT1)
- ✓ Inlet/outlet streams have proper T, p, m, h from Aspen
- ✓ Exergy fields are `None` (not yet calculated—component will compute)
- ✓ Power flows are captured (e.g., `out_1: 3067539.11` W for LK1)
- ✓ Splitter has one inlet and two outlets (split flow)

---

## Integration Summary

### **Where the Logging Sits in the Pipeline**

```
┌──────────────────┐
│ Aspen Model      │
└────────┬─────────┘
         │
┌────────▼──────────────────────────┐
│ AspenParser.parse()                │
│ • Extracts components              │
│ • Extracts connections             │
│ ✓ "Parsing completed..." (summary) │
└────────┬──────────────────────────┘
         │
┌────────▼──────────────────────────┐
│ ExergyAnalysis.__init__()          │
│ • Builds component objects         │
└────────┬──────────────────────────┘
         │
┌────────▼──────────────────────────┐
│ ExergyAnalysis.analyse()           │
│                                    │
│ FOR each component:                │
│   ✓ "Component inputs before calc" │ ← YOU ARE HERE (Lines 251-260)
│   ↓ calc_exergy_balance()          │
│   ✓ Per-component calc logs        │
│                                    │
│ • Validation & results             │
└────────────────────────────────────┘
         │
┌────────▼──────────────────────────┐
│ Output (parser_run.log)            │
│ • Exergy tables                    │
│ • Result summary                   │
└────────────────────────────────────┘
```

---

## Next Steps

If you need to:
1. **Understand the exact failure point:** Look in `parser_run.log` for the "Component inputs before calc" line immediately before any error traceback
2. **Add more detailed logging:** Insert additional logging inside `component.calc_exergy_balance()` methods (components files)
3. **Fix missing fields:** Either (a) improve parser to populate all fields, or (b) add defensive checks in components to handle None gracefully

