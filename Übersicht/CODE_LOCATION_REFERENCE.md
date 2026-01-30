# Exact Code Reference: Component Input Before Calc Logging

## Source File: `src/exerpy/analyses.py`

### Method Context
```
Class:  ExergyAnalysis
Method: analyse(self, E_F, E_P, E_L=None)
Lines:  103-280+ (full method)
```

---

## The Logging Code Block (Exact)

### Location: Lines 254-259 (7 lines)

```python
215 |                                "e_PH": v.get("e_PH"),
216 |                                "e_T": v.get("e_T"),
217 |                                "e_M": v.get("e_M"),
218 |                            })
219 |                        except Exception:
220 |                            inl_summary.append({"name": k, "raw": str(v)})
221 |                except Exception:
222 |                    inl_summary = str(component.inl)
    |
    | [outlet summary construction - similar pattern, lines 224-240]
    |
241 |                # Also capture power/heat connections if present on the component object
242 |                power_info = {}
243 |                for idx, conn in getattr(component, "inl", {}).items():
244 |                    if conn is not None and conn.get("kind") == "power" and "energy_flow" in conn:
245 |                        power_info[f"in_{idx}"] = conn.get("energy_flow")
246 |                for idx, conn in getattr(component, "outl", {}).items():
247 |                    if conn is not None and conn.get("kind") == "power" and "energy_flow" in conn:
248 |                        power_info[f"out_{idx}"] = conn.get("energy_flow")
    |
┌───┴───────────────────────────────────────────────────────────────────────────┐
│ LOGGING POINT #2: COMPONENT INPUTS BEFORE CALCULATION                        │
│ Lines 254-259 (5 executable lines + 1 blank)                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│ 250 |                # Emit both print (guaranteed to appear in redirected   │
│     |                #  test log) and logging.info                           │
│ 251 |                msg = (                                                 │
│ 252 |                    f"Component inputs before calc | {component.name} " │
│ 253 |                    f"({component.__class__.__name__}) | "             │
│ 254 |                    f"inlets={inl_summary} | outlets={outl_summary} | "│
│ 255 |                    f"power={power_info}"                             │
│ 256 |                )                                                      │
│ 257 |                logging.info(msg)  ◄─ LOGGER OUTPUT                   │
│ 258 |                print(msg)         ◄─ STDOUT (pytest captures)         │
│                                                                             │
│ 259 |                # Calculate E_F, E_D, E_P                             │
│ 260 |                component.calc_exergy_balance(                         │
│     |                    self.Tamb, self.pamb,                             │
│     |                    self.split_physical_exergy)                       │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Build-Up: How inl_summary & outl_summary Are Constructed

### Inlet Summary (Lines 208-222)

```python
208 |                try:
209 |                    inl_summary = []                     ◄─ Start as empty list
210 |                    for k, v in component.inl.items():  ◄─ Iterate inlets
211 |                        try:
212 |                            inl_summary.append({
213 |                                "name": k,
214 |                                "T": v.get("T"),        ◄─ Temperature
215 |                                "p": v.get("p"),        ◄─ Pressure
216 |                                "m": v.get("m"),        ◄─ Mass flow
217 |                                "h": v.get("h"),        ◄─ Enthalpy
218 |                                "e_PH": v.get("e_PH"),  ◄─ Physical exergy
219 |                                "e_T": v.get("e_T"),    ◄─ Thermal exergy
220 |                                "e_M": v.get("e_M"),    ◄─ Mechanical exergy
221 |                            })
222 |                        except Exception:
223 |                            inl_summary.append({"name": k, "raw": str(v)})
224 |                except Exception:
225 |                    inl_summary = str(component.inl)     ◄─ Fallback: stringify
```

### Outlet Summary (Lines 224-240)

```python
224 |                try:
225 |                    outl_summary = []                    ◄─ Start as empty list
226 |                    for k, v in component.outl.items():  ◄─ Iterate outlets
227 |                        try:
228 |                            outl_summary.append({
229 |                                "name": k,
230 |                                "T": v.get("T"),
231 |                                "p": v.get("p"),
232 |                                "m": v.get("m"),
233 |                                "h": v.get("h"),
234 |                                "e_PH": v.get("e_PH"),
235 |                                "e_T": v.get("e_T"),
236 |                                "e_M": v.get("e_M"),
237 |                            })
238 |                        except Exception:
239 |                            outl_summary.append({"name": k, "raw": str(v)})
240 |                except Exception:
241 |                    outl_summary = str(component.outl)    ◄─ Fallback: stringify
```

### Power Connections (Lines 242-248)

```python
242 |                # Also capture power/heat connections if present on the component object
243 |                power_info = {}                          ◄─ Empty dict
244 |                for idx, conn in getattr(component, "inl", {}).items():
245 |                    if conn is not None and conn.get("kind") == "power" and "energy_flow" in conn:
246 |                        power_info[f"in_{idx}"] = conn.get("energy_flow")
247 |                for idx, conn in getattr(component, "outl", {}).items():
248 |                    if conn is not None and conn.get("kind") == "power" and "energy_flow" in conn:
249 |                        power_info[f"out_{idx}"] = conn.get("energy_flow")
```

---

## Full Context: Component Loop

```python
    def analyse(self, E_F, E_P, E_L=None) -> None:
        """Run the exergy analysis..."""
        
        # ... [initialization and exergy summation code, lines 104-205] ...
        
        # COMPONENT ITERATION LOOP BEGINS
200 |        for component in self.components.values():    ◄─ FOR EACH COMPONENT
    |
201 |            try:                                      ◄─ Error handling
202 |                # Build inlet/outlet summaries for this component
203 |                try:
    |                    inl_summary = []
    |                    for k, v in component.inl.items():
    |                        try:
    |                            inl_summary.append({...})
    |                        except Exception:
    |                            inl_summary.append({...})
    |                except Exception:
    |                    inl_summary = str(component.inl)
    |
    |                try:
    |                    outl_summary = []
    |                    for k, v in component.outl.items():
    |                        try:
    |                            outl_summary.append({...})
    |                        except Exception:
    |                            outl_summary.append({...})
    |                except Exception:
    |                    outl_summary = str(component.outl)
    |
    |                power_info = {}
    |                for idx, conn in getattr(component, "inl", {}).items():
    |                    if conn is not None and conn.get("kind") == "power":
    |                        power_info[f"in_{idx}"] = conn.get("energy_flow")
    |                for idx, conn in getattr(component, "outl", {}).items():
    |                    if conn is not None and conn.get("kind") == "power":
    |                        power_info[f"out_{idx}"] = conn.get("energy_flow")
    |
        ╔═══════════════════════════════════════════════════╗
        ║    MAIN LOGGING STATEMENT (Lines 251-258)        ║
        ║                                                   ║
251 |            msg = (                                    ║
252 |                f"Component inputs before calc | "     ║
253 |                f"{component.name} "                   ║
254 |                f"({component.__class__.__name__}) | " ║
255 |                f"inlets={inl_summary} | "             ║
256 |                f"outlets={outl_summary} | "           ║
257 |                f"power={power_info}"                  ║
258 |            )                                          ║
259 |            logging.info(msg)                          ║
260 |            print(msg)                                 ║
        ╚═══════════════════════════════════════════════════╝
    |
261 |            # Calculate E_F, E_D, E_P                  ◄─ COMPONENT CALC
262 |            component.calc_exergy_balance(
263 |                self.Tamb, self.pamb, self.split_physical_exergy)
    |
264 |            # Safely calculate y and y* avoiding division by zero
265 |            if self.E_F != 0:
266 |                component.y = component.E_D / self.E_F
267 |                component.y_star = (component.E_D / self.E_D 
268 |                                     if component.E_D is not None else np.nan)
269 |            else:
270 |                component.y = np.nan
271 |                component.y_star = np.nan
272 |
273 |            # Sum component destruction if available
274 |            if component.E_D is not np.nan:
275 |                total_component_E_D += component.E_D
    |
276 |            except Exception as e:                      ◄─ Error handling
277 |                logging.error(
278 |                    f"Error processing component {component.name}: {str(e)}"
279 |                )
280 |                raise
    |
    | # Continue with validation and results...
```

---

## Data Flow Diagram with Line Numbers

```
                  ┌────────────────────────────────┐
                  │  analyse() method starts       │
                  │  (Line 103)                    │
                  └────────────┬───────────────────┘
                               │
                    ┌──────────▼────────────┐
                    │ Initialize E_F, E_P, │
                    │ E_L (Lines 113-124)   │
                    └──────────┬────────────┘
                               │
                    ┌──────────▼────────────┐
                    │ Sum exergy from       │
                    │ connections           │
                    │ (Lines 140-180)       │
                    └──────────┬────────────┘
                               │
         ┌─────────────────────▼─────────────────────┐
         │ FOR EACH COMPONENT                        │
         │ (Line 200: for component in              │
         │            self.components.values())     │
         └──────────────────┬──────────────────────┘
                            │
         ┌──────────────────▼──────────────────┐
         │ BUILD SUMMARY DICTS                 │
         │                                     │
         │ Lines 201-248:                      │
         │ ├─ inl_summary (208-225)            │
         │ ├─ outl_summary (224-240)           │
         │ └─ power_info (242-248)             │
         └──────────────────┬──────────────────┘
                            │
         ╔═══════════════════▼═══════════════════╗
         ║ LOGGING BLOCK (Lines 251-260)        ║
         ║                                      ║
         ║ Lines 251-258: Build msg string      ║
         ║ Line 259: logging.info(msg)          ║
         ║ Line 260: print(msg)                 ║
         ║                                      ║
         ║ OUTPUT:                              ║
         ║ "Component inputs before calc | ..." ║
         ╚═══════════════════╤═══════════════════╝
                            │
         ┌──────────────────▼──────────────────┐
         │ COMPONENT CALCULATION               │
         │                                     │
         │ Lines 262-263:                      │
         │ component.calc_exergy_balance(...)  │
         │                                     │
         │ ✓ Determines branch (adiabatic/etc)│
         │ ✓ Uses inl/outl data                │
         │ ✓ Computes E_F, E_P, E_D            │
         │ ✓ Emits per-component logs          │
         └──────────────────┬──────────────────┘
                            │
         ┌──────────────────▼──────────────────┐
         │ CALCULATE COMPONENT EFFICIENCY      │
         │                                     │
         │ Lines 265-271:                      │
         │ ├─ y = E_D / E_F                    │
         │ ├─ y* = E_D / E_D                   │
         │ └─ Handle division by zero          │
         └──────────────────┬──────────────────┘
                            │
         ┌──────────────────▼──────────────────┐
         │ ACCUMULATE TOTALS                   │
         │                                     │
         │ Lines 274-275:                      │
         │ total_component_E_D += component.E_D│
         └──────────────────┬──────────────────┘
                            │
         └─────────────────────────────────────┘
              (next iteration or loop exit)
```

---

## Key Variables at Logging Point

| Variable | Type | Populated By | Visible in Log? |
|----------|------|--------------|-----------------|
| `component.name` | str | Parser | ✓ YES |
| `component.__class__.__name__` | str | Python object | ✓ YES |
| `component.inl` | dict | `_construct_components()` | ✓ YES (summarized) |
| `component.outl` | dict | `_construct_components()` | ✓ YES (summarized) |
| `inl_summary` | list[dict] | Lines 208-222 | ✓ YES (formatted) |
| `outl_summary` | list[dict] | Lines 224-240 | ✓ YES (formatted) |
| `power_info` | dict | Lines 242-248 | ✓ YES |
| `msg` | str | Lines 251-258 | ✓ YES (logged + printed) |

---

## Why Both logging.info() AND print()?

### Line 259: `logging.info(msg)`
- **Purpose:** Send to Python logging module
- **Output:** Captured in `.log` files (if configured)
- **Risk:** pytest may not redirect logger output properly

### Line 260: `print(msg)`
- **Purpose:** Send to stdout
- **Output:** Guaranteed capture by pytest stdout redirection (`> parser_run.log 2>&1`)
- **Reason:** Ensures log appears even if logger is misconfigured

**Result:** Both outputs appear in `parser_run.log` under `pytest` execution.

---

## Code Changes Applied

### What Was Changed
✓ Added lines 251-260 (logging block) in the main component loop  
✓ Modified lines 208-248 to support summary construction (was already present, no change needed)

### What Was NOT Changed
- Lines 262-263: `component.calc_exergy_balance()` call (original logic unchanged)
- Lines 265-275: Efficiency/total calculation (original logic unchanged)
- No changes to parser or components themselves

### Why This Location?
- **Before calc:** Shows exact input state before calculation runs
- **Inside loop:** Captures all components
- **After data extraction:** Shows what each component will receive
- **Before error:** If calc fails, the preceding log shows the problematic input

---

## Reading parser_run.log

### Example 1: Successful Component
```
Component inputs before calc | LK1 (Compressor) | inlets=[{'name': 0, 'T': 288.15, 'p': 101325.0, 'm': 29.7656782, 'h': -100458.293, 'e_PH': None, 'e_T': None, 'e_M': None}] | outlets=[{'name': 0, 'T': 388.964645, 'p': 250496.184, 'm': 29.7656782, 'h': 1567.39279, 'e_PH': None, 'e_T': None, 'e_M': None}, {'name': 1, 'T': None, 'p': None, 'm': None, 'h': None, 'e_PH': None, 'e_T': None, 'e_M': None}] | power={'out_1': 3067539.11}

✓ Inlet stream: T=288.15 K, p=101325 Pa, m=29.77 kg/s
✓ Outlet stream 0: T=388.96 K, p=250496 Pa (compressed)
✓ Outlet stream 1: All None (secondary, not used)
✓ Power out: 3.07 MW
✓ calc_exergy_balance() will now use these values

[LK1 then calculates successfully...]

[Next component log...]
```

### Example 2: Component with Missing Field
```
Component inputs before calc | SPLIT1 (Splitter) | inlets=[{'name': 0, 'T': 308.15, 'p': 624000.0, 'm': 29.5600064, 'h': 8439.18602, 'e_PH': None, 'e_T': None, 'e_M': None}] | outlets=[{'name': 1, 'T': 308.15, 'p': 624000.0, 'm': 24.8304054, 'h': 8439.18602, 'e_PH': None, 'e_T': None, 'e_M': None}, ...]  | power={}

⚠ Inlet: e_PH=None (OK, not yet calculated)
⚠ Outlet: e_PH=None (OK, not yet calculated)
⚠ Power: {} (no power connections)

Traceback (most recent call last):
  File "src/exerpy/components/nodes/splitter.py", line 63, in calc_exergy_balance
    E_in = sum(inlet.get("m", 0) * inlet.get("e_PH") for inlet in inlet_list)
TypeError: unsupported operand type(s) for *: 'float' and 'NoneType'

✗ PROBLEM: calc tried to use e_PH (which is None) in math
✗ The log shows why: component received None for exergy field
```

---

## Summary

| Aspect | Details |
|--------|---------|
| **File** | `src/exerpy/analyses.py` |
| **Method** | `ExergyAnalysis.analyse()` |
| **Lines** | 251-260 (logging block) |
| **Log Message** | "Component inputs before calc \| {name} ({type}) \| inlets={...} \| outlets={...} \| power={...}" |
| **Timing** | Immediately before `component.calc_exergy_balance()` (line 262) |
| **Output** | `logging.info()` + `print()` (both captured in pytest-redirected logs) |
| **Purpose** | Snapshot of each component's input state before calculation |
| **Diagnostic Value** | Identifies missing/None fields that cause calc errors |
| **Captured In** | `parser_run.log` (pytest output redirection) |

