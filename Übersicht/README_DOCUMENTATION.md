# Documentation Index: Analysis & Component Input Logging

## Overview

This folder contains comprehensive documentation of the exergy analysis pipeline, specifically focused on the **"Component inputs before calc"** logging feature added to capture input states before per-component exergy calculations.

---

## Documents in This Set

### 1. **VISUAL_SCHEMATIC.md** ⭐ Start Here
**Best for:** Quick visual understanding of the full pipeline  
**Contains:**
- High-level ASCII flow diagram (Parse → Calculate phases)
- Detailed breakdown of Lines 251-260 in `analyses.py`
- Log message content breakdown
- Step-by-step guide to reading the log
- Data flow diagrams
- Example log entries from `parser_run.log`

**Read this if you want to:** Understand the overall flow and see the exact location of logging in context

---

### 2. **ANALYSIS_FLOW_SCHEMATIC.md**
**Best for:** Understanding the complete workflow architecture  
**Contains:**
- High-level process flow from parsing through calculation
- Detailed code locations (files, methods, line ranges)
- Log entry timeline within `parser_run.log`
- Three main phases (PARSE, CALC-INIT, CALC-MAIN, CALC-COMP)
- Code changes summary table

**Read this if you want to:** Understand which files changed, which lines were modified, and how everything fits together

---

### 3. **COMPONENT_INPUT_LOG_LOCATION.md**
**Best for:** Understanding the exact location and diagnostic value  
**Contains:**
- Exact location of logging code with ASCII diagram
- Data flow from connection dict → log output
- How to read log entries and interpret fields
- Why the log is placed before calc
- Traceability: finding logs and errors in parser_run.log

**Read this if you want to:** Locate the logging code, understand what happens before it, and use it for debugging

---

### 4. **CODE_LOCATION_REFERENCE.md** 
**Best for:** Developers implementing changes or debugging  
**Contains:**
- Exact line numbers (251-260) with full source code context
- Build-up sections showing how inl_summary, outl_summary, power_info are constructed
- Full context of the analyse() method
- Variable types, sources, and data flow with line numbers
- Explanation of why both `logging.info()` and `print()` are used
- Code changes applied summary

**Read this if you want to:** Reference exact line numbers, understand variable types, or modify the logging code

---

### 5. **LOGGING_SUMMARY.md**
**Best for:** Quick reference and integration overview  
**Contains:**
- Quick reference of exact file, lines, and log message format
- The complete analysis flow (parsing → calculation)
- What data is logged and why
- Key observations about timing and data sources
- Diagnostic use cases (three scenarios)
- Next steps for further improvements

**Read this if you want to:** Get quick answers without reading full documents

---

## Quick Navigation

### "I want to..."

**...understand the overall flow**
→ Read: **VISUAL_SCHEMATIC.md** (Section: "EXERGY ANALYSIS: PARSE → CALCULATE")

**...find the exact logging code**
→ Read: **CODE_LOCATION_REFERENCE.md** (Lines 251-260)

**...understand what data is logged**
→ Read: **COMPONENT_INPUT_LOG_LOCATION.md** (Section: "Log Entry Timeline")

**...see where changes were made**
→ Read: **ANALYSIS_FLOW_SCHEMATIC.md** (Table: "Code Changes Summary")

**...diagnose a component failure**
→ Read: **COMPONENT_INPUT_LOG_LOCATION.md** (Section: "Diagnostic Use Cases")

**...integrate the logging into my code**
→ Read: **CODE_LOCATION_REFERENCE.md** (Full context of analyse() method)

**...understand the files affected**
→ Read: **ANALYSIS_FLOW_SCHEMATIC.md** (Detailed Code Locations section)

**...see actual parser_run.log examples**
→ Read: **VISUAL_SCHEMATIC.md** (Section: "EXAMPLE PARSER_RUN.LOG EXCERPT")

---

## The Logging Feature at a Glance

### Location
```
File: src/exerpy/analyses.py
Method: ExergyAnalysis.analyse()
Lines: 251-260 (inside main component loop at Line 200)
```

### What It Does
Emits a log entry showing the exact input state (inlet/outlet streams, power connections) 
**right before** each component's exergy calculation runs.

### Log Output
```
Component inputs before calc | <ComponentName> (<ComponentType>) | 
inlets=[{stream_properties}] | outlets=[{stream_properties}] | 
power={power_connections}
```

### Purpose
Capture the raw input data for each component before calculation, enabling diagnosis of 
missing/None fields that cause calculation failures.

### Both Methods Used
```python
logging.info(msg)  # Logger module (standard approach)
print(msg)         # Stdout (guaranteed pytest capture)
```

Both are sent to `parser_run.log` when tests redirect output.

---

## Files Modified (Summary)

| File | Method | Lines | Change |
|------|--------|-------|--------|
| `src/exerpy/analyses.py` | `analyse()` | 251-260 | **✓ ADDED: Component input log** |
| `src/exerpy/parser/from_aspen/aspen_parser.py` | `parse()` | ~450-550 | Added parsing completion summary log |
| `src/exerpy/components/piping/valve.py` | `calc_exergy_balance()` | ~40-60 | Added branch + result logging |
| `src/exerpy/components/turbomachinery/compressor.py` | `calc_exergy_balance()` | ~40-80 | Added branch + power logging |
| `src/exerpy/components/turbomachinery/turbine.py` | `calc_exergy_balance()` | ~40-80 | Added branch logging |
| `src/exerpy/components/nodes/mixer.py` | `calc_exergy_balance()` | ~40-60 | Added inlet summary logging |
| `src/exerpy/components/nodes/splitter.py` | `calc_exergy_balance()` | ~40-60 | Added outlet summary logging |
| `src/exerpy/components/heat_exchanger/base.py` | `calc_exergy_balance()` | ~80-120 | Added 4-stream logging |

---

## Log Hierarchy

```
Parser Run Output (parser_run.log)

├─ PHASE 1: Parsing
│  ├─ Stream conversion traces (convert_to_SI)
│  ├─ Block parsing traces ("Parsed block D1...")
│  └─ ✓ Parsing completion log (#1)
│
├─ PHASE 2: Calculation
│  ├─ Component construction
│  └─ FOR each component:
│     ├─ ✓ Component inputs before calc log (#2)  ← YOU ARE HERE
│     └─ ✓ Per-component calc logs (#3)
│
└─ Final Results & Validation
   ├─ Exergy balance checks
   └─ Result summary
```

---

## Key Insights

### Timing
- **Before calc:** Lines 251-260 emit log showing raw input
- **During calc:** Component performs exergy balance (Lines 262-263)
- **After calc:** Component logs its calculation results

### Data Sources
| Field | Source | Value in Log |
|-------|--------|-------------|
| T, p, m, h | Aspen parser | Numeric (e.g., T=288.15 K) |
| e_PH, e_T, e_M | Not yet calculated | `None` (will be computed next) |
| Power | Connection dict | Numeric if power connection exists |

### Diagnostic Value
If a component fails during `calc_exergy_balance()`:
1. The error traceback shows the failing line
2. Scroll up to find "Component inputs before calc | <component_name>"
3. That log shows **exactly what inputs the component received**
4. If fields are None/unexpected, that's the root cause

---

## Integration in Pipeline

```
Aspen Model (.bkp)
    ↓
AspenModelParser.parse()
    ↓ [✓ "Parsing completed" log]
ExergyAnalysis.__init__()
    ↓
ExergyAnalysis.analyse()
    ↓
    FOR component in self.components:
        ↓ [✓ "Component inputs before calc" log] ← THIS DOCUMENT SET
        ↓ component.calc_exergy_balance()
        ↓ [✓ Per-component calc logs]
        ↓
parser_run.log (pytest captured output)
```

---

## How to Use These Documents

### First-Time Readers
1. Start with **VISUAL_SCHEMATIC.md** — get the big picture
2. Read **LOGGING_SUMMARY.md** — understand the key points
3. Dive into specific sections as needed

### Debuggers Troubleshooting Failures
1. Check **LOGGING_SUMMARY.md** → "Diagnostic Use Cases"
2. Reference **COMPONENT_INPUT_LOG_LOCATION.md** → "Reading the Log Entries"
3. Find the failing component's log in parser_run.log
4. Determine which fields are None/unexpected

### Developers Extending the Logging
1. Read **CODE_LOCATION_REFERENCE.md** — exact lines and context
2. Understand variable types and data sources
3. Modify per your requirements

### Architects Understanding Design
1. **ANALYSIS_FLOW_SCHEMATIC.md** → High-level flow
2. **CODE_LOCATION_REFERENCE.md** → Implementation details
3. Review files affected and understand the integration points

---

## References to Source Code

### Main Logging Location
[src/exerpy/analyses.py](src/exerpy/analyses.py#L251-L260) — Lines 251-260

### Component Loop Context
[src/exerpy/analyses.py](src/exerpy/analyses.py#L200) — Line 200 (for component in ...)

### Full analyse() Method
[src/exerpy/analyses.py](src/exerpy/analyses.py#L103-L280) — Lines 103-280+

### Component Examples
- [src/exerpy/components/piping/valve.py](src/exerpy/components/piping/valve.py)
- [src/exerpy/components/turbomachinery/compressor.py](src/exerpy/components/turbomachinery/compressor.py)
- [src/exerpy/components/nodes/splitter.py](src/exerpy/components/nodes/splitter.py)

---

## Test Output Example

### Running Tests
```bash
python -m pytest tests/test_aspen_luftzerlegung.py -q > parser_run.log 2>&1
```

### What You'll See in parser_run.log
```
...
Parsing completed: parsed 10 blocks, connections=35 items, component groups=12
...
Component inputs before calc | LK1 (Compressor) | inlets=[{'name': 0, 'T': 288.15, ...}] | ...
Component inputs before calc | LK2 (Compressor) | inlets=[{'name': 0, 'T': 308.15, ...}] | ...
...
Component inputs before calc | SPLIT1 (Splitter) | inlets=[...] | outlets=[...] | power={}
...
```

---

## Feedback & Further Improvements

### If You Want to Add More Logging
- See **CODE_LOCATION_REFERENCE.md** for exact implementation patterns
- Add logging at similar points (before/after calculations)
- Use both `logging.info()` and `print()` for pytest capture

### If You Find Issues
- Check whether fields are None when they shouldn't be
- Refer to **COMPONENT_INPUT_LOG_LOCATION.md** → "Diagnostic Use Cases"
- Consider upstream parser fixes or downstream component defensive checks

### If You Modify the Code
- Keep logging statements compact (one line or block)
- Include component name/type for traceability
- Log both inputs (before) and results (after) for completeness

---

## Document Maintenance

| Document | Last Updated | Covers Lines | Accuracy |
|----------|-------------|-------------|----------|
| VISUAL_SCHEMATIC.md | Current | 251-260 + flow | ✓ Current |
| ANALYSIS_FLOW_SCHEMATIC.md | Current | Full pipeline | ✓ Current |
| COMPONENT_INPUT_LOG_LOCATION.md | Current | 251-260 + diagnostic | ✓ Current |
| CODE_LOCATION_REFERENCE.md | Current | 251-260 + context | ✓ Current |
| LOGGING_SUMMARY.md | Current | Quick ref | ✓ Current |

All documents reference the same code locations and are cross-consistent.

---

## Summary

These five documents provide **complete documentation** of the "Component inputs before calc" logging feature:

1. **Visual understanding** → VISUAL_SCHEMATIC.md
2. **Workflow architecture** → ANALYSIS_FLOW_SCHEMATIC.md
3. **Exact code location** → COMPONENT_INPUT_LOG_LOCATION.md
4. **Implementation details** → CODE_LOCATION_REFERENCE.md
5. **Quick reference** → LOGGING_SUMMARY.md

**Together, they answer:**
- ✓ Where is the logging? (Lines 251-260 in analyses.py)
- ✓ What does it log? (Component input state: T, p, m, h, e_*, power)
- ✓ When does it run? (Right before component.calc_exergy_balance)
- ✓ Why is it there? (Diagnose missing/None fields before calc fails)
- ✓ How do I read it? (Look in parser_run.log, find "Component inputs before calc")
- ✓ How do I use it? (Reference logs when debugging component failures)

