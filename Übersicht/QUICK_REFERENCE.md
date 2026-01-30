# Quick Reference Card: Component Input Logging

## 🎯 The Logging at a Glance

```
WHERE:    src/exerpy/analyses.py, Lines 251-260
WHEN:     Right before component.calc_exergy_balance() (line 262)
WHAT:     Component inlet/outlet streams + power connections
WHY:      Diagnose missing/None fields before calc fails
OUTPUT:   logging.info() + print() → parser_run.log
INSIDE:   Main loop: for component in self.components (line 200)
TIMING:   Shows data BEFORE exergy calculation (e_* fields are None)
COVERS:   All 12 components in the system
```

---

## 📍 Code Location

**File:** `src/exerpy/analyses.py`  
**Lines:** 251-260  
**Method:** `ExergyAnalysis.analyse()`

```python
msg = (
    f"Component inputs before calc | {component.name} "
    f"({component.__class__.__name__}) | "
    f"inlets={inl_summary} | outlets={outl_summary} | "
    f"power={power_info}"
)
logging.info(msg)  ← Logger
print(msg)         ← Stdout
```

---

## 📊 What Gets Logged

For **each component**, the log shows:

| Data | Example | Status |
|------|---------|--------|
| Component Name | `LK1` | From parser ✓ |
| Component Type | `Compressor` | From parser ✓ |
| Inlet Stream Count | 1 inlet | From parser ✓ |
| Inlet Properties | T=288.15K, p=101325Pa | From parser ✓ |
| Inlet Mass Flow | m=29.77 kg/s | From parser ✓ |
| Inlet Enthalpy | h=-100458 J/kg | From parser ✓ |
| Inlet Exergy Terms | e_PH=None, e_T=None, e_M=None | Not yet calculated |
| Outlet Stream Count | 2 outlets | From parser ✓ |
| Outlet Properties | (same as inlet) | From parser ✓ |
| Power Connections | out_1: 3067539 W | From parser ✓ |

---

## 📈 Log Entry Timeline

```
parser_run.log structure:

Line 1-100:    Stream conversion traces (convert_to_SI)
Line 100-600:  Aspen block extraction ("Parsed block D1...")
Line 600-750:  ✓ "Parsing completed: 10 blocks, 35 conns..."
               ↓
Line 750+:     Component analysis loop
               FOR component in self.components:
               ├─ ✓ "Component inputs before calc | LK1 ..."
               ├─ [LK1 calc logs]
               ├─ ✓ "Component inputs before calc | LK2 ..."
               ├─ [LK2 calc logs]
               └─ ... (repeats for all 12 components)
               ↓
Line 1000+:    Results & validation
               ├─ "Exergy destruction check passed..."
               └─ [Test pass/fail]
```

---

## 🔍 How to Read a Log Entry

```
Component inputs before calc | LK1 (Compressor) | 
inlets=[{'name': 0, 'T': 288.15, 'p': 101325.0, 
         'm': 29.7656782, 'h': -100458.293, 
         'e_PH': None, 'e_T': None, 'e_M': None}] | 
outlets=[{'name': 0, 'T': 388.964645, 'p': 250496.184, 
          'm': 29.7656782, 'h': 1567.39279, 
          'e_PH': None, 'e_T': None, 'e_M': None}, 
         {'name': 1, 'T': None, 'p': None, 'm': None, 
          'h': None, 'e_PH': None, 'e_T': None, 'e_M': None}] | 
power={'out_1': 3067539.11}

┌─────────────────────────────────────────────────────┐
│ Label: "Component inputs before calc |"             │
│ Component: LK1 (Compressor)                          │
│ Inlet 0: T=288.15 K, p=101325 Pa, m=29.77 kg/s     │
│ Outlet 0: T=388.96 K, p=250496 Pa (compressed)     │
│ Outlet 1: All None (secondary, unused)             │
│ Power: 3.07 MW out                                 │
│ Exergy: Not yet calculated (will run now)          │
└─────────────────────────────────────────────────────┘

✓ Component ready for calc_exergy_balance()
```

---

## 🐛 Debugging with This Log

### If Component Fails
1. Find error traceback in parser_run.log
2. Scroll UP to find `"Component inputs before calc | <component_name>..."`
3. Check which fields are `None` or unexpected
4. **Diagnosis:** That's what the component received from the parser

### If You Want to Know Exact Input Values
Search: `Component inputs before calc | <ComponentName>`
→ Exact T, p, m, h values used in calculation

### To Trace Execution Order
Look for sequential log entries:
```
Component inputs before calc | LK1 ...   ← 1st
Component inputs before calc | LK2 ...   ← 2nd
Component inputs before calc | PK1 ...   ← 3rd
...
Component inputs before calc | SPLIT1 ...← Last before error
Traceback (...)                          ← Error here!
```

---

## 🔧 Data Flow Diagram

```
Aspen Model
    ↓
AspenParser.parse()
    ├─ Extract T, p, m, h for each stream
    └─ Build connection_data dict
    ↓
ExergyAnalysis.__init__()
    ├─ Receive component_data, connection_data
    └─ Build component objects with inl/outl
    ↓
ExergyAnalysis.analyse()
    ├─ FOR component in self.components:
    │   ├─ Extract inl_summary from component.inl
    │   ├─ Extract outl_summary from component.outl
    │   ├─ Extract power_info from connections
    │   ↓
    │   ✓ Lines 251-260: Log component inputs
    │   ↓
    │   ├─ logging.info(msg) [Python logger]
    │   └─ print(msg) [Stdout, captured by pytest]
    │   ↓
    │   ├─ component.calc_exergy_balance()
    │   │  ├─ Determine which branch (adiabatic/poly/etc)
    │   │  ├─ Use logged data to compute E_F, E_P, E_D
    │   │  └─ Log per-component results
    │   │
    │   └─ [Next component]
    │
parser_run.log (pytest captured output)
```

---

## 📋 Quick Checklist

### When reviewing logs:
- [ ] Did "Parsing completed" appear? (Parser done)
- [ ] Do "Component inputs before calc" entries appear? (About to calculate)
- [ ] Do all inlets have T, p, m, h values? (Check for None)
- [ ] Do exergy fields (e_*) show None? (Expected — not yet calculated)
- [ ] Do power values appear correct? (Check magnitude)
- [ ] Does error appear right after a "Component inputs" log? (That component failed)

### When debugging a failure:
- [ ] Find the component name from error message
- [ ] Search parser_run.log for `Component inputs before calc | <name>`
- [ ] Check which inlet/outlet fields are None/unexpected
- [ ] Compare with working components (see nearby log entries)
- [ ] Trace back to parser to fix data population

---

## 🎯 Key Takeaways

| Question | Answer |
|----------|--------|
| **Where is it?** | Lines 251-260 in `src/exerpy/analyses.py` |
| **Why is it there?** | To capture raw input before calculation |
| **What does it show?** | T, p, m, h, power for inlets/outlets |
| **Why are e_* None?** | They're calculated DURING calc_exergy_balance, not before |
| **Where is the output?** | `parser_run.log` (pytest captured) |
| **When does it run?** | Right before `component.calc_exergy_balance()` |
| **Why both logging + print?** | Ensure output appears in pytest-redirected logs |
| **How do I use it?** | Find component logs in parser_run.log, check input values |
| **What if fields are None?** | Parser didn't populate them; that's the root cause |
| **How many times?** | Once per component (12 times in full run) |

---

## 📚 Documentation Files

| File | Best For |
|------|----------|
| **README_DOCUMENTATION.md** | Navigation & overview |
| **VISUAL_SCHEMATIC.md** | Visual understanding (ASCII diagrams) |
| **ANALYSIS_FLOW_SCHEMATIC.md** | Architecture & workflow |
| **COMPONENT_INPUT_LOG_LOCATION.md** | Exact location & diagnostics |
| **CODE_LOCATION_REFERENCE.md** | Developer reference (line-by-line) |
| **LOGGING_SUMMARY.md** | One-page summary |
| **WHAT_WAS_CREATED.md** | Summary of all changes |
| **THIS FILE** | Quick reference card |

---

## 🚀 Common Tasks

### "How do I see the logs?"
```bash
# Run tests (output redirected to parser_run.log)
python -m pytest tests/test_aspen_luftzerlegung.py -q > parser_run.log 2>&1

# Search for component logs
grep "Component inputs before calc" parser_run.log
```

### "How do I find a specific component?"
```bash
grep "Component inputs before calc | LK1" parser_run.log
```

### "How do I see all components in order?"
```bash
grep "Component inputs before calc" parser_run.log | cut -d'|' -f2
```

### "How do I debug a failure?"
1. Run tests and capture parser_run.log
2. Find error traceback at end of log
3. Scroll up to find "Component inputs before calc | <component_name>"
4. Check which fields are None (that's the problem)

---

## 💡 Key Insight

The **timing is critical**: This log runs **right before** `component.calc_exergy_balance()` 
and shows the **raw input state**. If the component fails, this log shows **exactly what it received**. 
If fields are None, the parser didn't populate them — that's your root cause.

**Use this log as a bridge between:**
- Parser output ← What data gets extracted
- **← THIS LOG (Component inputs before calc) →**  
- Component calculation → What happens with that data

