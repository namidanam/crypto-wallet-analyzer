# Intermediate COCOMO (COCOMO'81) Estimation

This project includes a small helper script to compute **Intermediate COCOMO'81** using **only your source code** (excluding third‑party/vendor, generated artifacts, documentation, and configuration files).

## 1) Measure size (KLOC) correctly

COCOMO uses **KLOC** (thousand delivered source lines of code).

Recommended approach:
- Count only **tracked** source files (avoids `node_modules/`, `coverage/`, build outputs, etc.)
- Include only **code extensions** (e.g. `.py`, `.js`, `.ts`)
- Exclude documentation/config/lock files (`.md`, `.yml`, `package-lock.json`, etc.)

### Option A (recommended): use the repo script

From the repo root:

```bash
python3 scripts/cocomo_intermediate.py
```

Defaults:
- Counts tracked code files with extensions: `.py`, `.js`, `.ts`, `.jsx`, `.tsx`, `.mjs`, `.cjs`
- Excludes common vendor/generated/doc directories (e.g. `node_modules/`, `dist/`, `build/`, `coverage/`, `docs/`)
- Excludes tests by default (production-only); add `--include-tests` if you want tests included
- Excludes Python triple-quoted docstrings by default; add `--include-docstrings` to include them

### Halstead metrics (same filtered code set)

The same script can also compute **Halstead metrics** over the same filtered source set (so you don’t count `node_modules/`, generated files, docs, etc.):

```bash
python3 scripts/cocomo_intermediate.py --halstead
```

Notes:
- This is an **approximation** for mixed-language repos.
- Numeric/string literals are abstracted as `<num>` / `<str>` operands (instead of treating every literal value as a distinct operand).
- Python docstrings follow the same `--include-docstrings` behavior.

### Function Point Analysis (same script, manual inputs)

Function Points are **not derived from LOC** and are typically counted from requirements / user stories.
This script provides an **IFPUG-style** calculator so you can keep all estimation in one place.

Unadjusted FP (UFP) weights used:
- EI: 3 / 4 / 6 (low / avg / high)
- EO: 4 / 5 / 7
- EQ: 3 / 4 / 6
- ILF: 7 / 10 / 15
- EIF: 5 / 7 / 10

Example:

```bash
python3 scripts/cocomo_intermediate.py --fpa \
  --ei 3 2 1 \
  --eo 1 1 0 \
  --eq 2 0 0 \
  --ilf 1 1 0 \
  --eif 0 1 0
```

If you want “Adjusted FP” (AFP), pass either:
- `--gsc` (14 ratings, each 0..5), and the script applies `VAF = 0.65 + 0.01*TDI`
- or `--vaf` to override VAF directly

Optional FP → SLOC conversion (for rough cross-checking only):

```bash
python3 scripts/cocomo_intermediate.py --fpa \
  --ei 3 2 1 --eo 1 1 0 --eq 2 0 0 --ilf 1 1 0 --eif 0 1 0 \
  --gsc 3 2 2 3 2 1 2 2 3 2 1 2 1 2 \
  --sloc-per-fp 50
```

## 4) Cumulative Flow Diagram (CFD)

CFD is a **process metric** (not size/effort estimation). The repo script can generate a CFD SVG from a daily snapshot CSV:

```bash
python3 scripts/cocomo_intermediate.py --no-cocomo --cfd --cfd-input docs/cfd_sample.csv --cfd-output docs/cfd.svg
```

Details: `docs/CFD.md`

## 5) Throughput report

Throughput (items completed per day/week) is generated from the same snapshot CSV as the CFD:

```bash
python3 scripts/cocomo_intermediate.py --no-cocomo --throughput --tp-input docs/cfd_sample.csv --tp-output docs/throughput.md
```

Details: `docs/THROUGHPUT.md`

## 6) Sprint burndown chart

Generate a sprint burndown SVG from the same snapshot CSV:

```bash
python3 scripts/cocomo_intermediate.py --no-cocomo --burndown --bd-input docs/cfd_sample.csv --bd-output docs/burndown.svg --bd-done-stage Done
```

Details: `docs/BURNDOWN.md`

## 7) Sprint burnup chart

Generate a sprint burnup SVG from the same snapshot CSV:

```bash
python3 scripts/cocomo_intermediate.py --no-cocomo --burnup --bu-input docs/cfd_sample.csv --bu-output docs/burnup.svg --bu-done-stage Done
```

Details: `docs/BURNUP.md`

## 8) Comment density

Compute approximate comment density over the filtered source set:

```bash
python3 scripts/cocomo_intermediate.py --no-cocomo --comment-density
```

Details: `docs/COMMENT_DENSITY.md`

## 9) Design structure quality density (DSQD)

Compute approximate internal dependency density (import/require edges between files):

```bash
python3 scripts/cocomo_intermediate.py --no-cocomo --dsqd
```

Details: `docs/DSQD.md`

### Option B: use `cloc` (if installed)

```bash
cloc --vcs=git --include-ext=py,js,ts,jsx,tsx,mjs,cjs \
  --exclude-dir=node_modules,coverage,dist,build,docs
```

## 2) Intermediate COCOMO formulas

Intermediate COCOMO'81:
- **Effort (PM)** = `a * (KLOC ^ b) * EAF`
- **Schedule (months)** = `c * (Effort ^ d)`

Project modes (coefficients):
- `organic`: `a=2.4, b=1.05, c=2.5, d=0.38`
- `semidetached`: `a=3.0, b=1.12, c=2.5, d=0.35`
- `embedded`: `a=3.6, b=1.20, c=2.5, d=0.32`

## 3) Provide EAF (cost drivers)

Intermediate COCOMO adjusts effort using **EAF** (Effort Adjustment Factor), computed as the **product** of cost driver multipliers.

With the script, either:
- Provide EAF directly: `--eaf 1.18`
- Or provide drivers (repeatable), e.g.:

```bash
python3 scripts/cocomo_intermediate.py \
  --mode semidetached \
  --driver RELY=H \
  --driver CPLX=VH \
  --driver TOOL=H
```

Notes:
- Supported drivers in the script: `RELY, DATA, CPLX, TIME, STOR, VIRT, TURN, ACAP, AEXP, PCAP, VEXP, LEXP, MODP, TOOL, SCED`
- Ratings are abbreviated: `VL, L, N, H, VH, XH` (not all drivers support all ratings)
