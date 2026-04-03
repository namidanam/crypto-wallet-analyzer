# Design Structure Quality Density (DSQD)

This repo computes an **approximate Design Structure Quality Density** based on internal file-to-file dependencies:

- **Nodes**: source files
- **Edges**: internal dependencies detected from imports/requires
- **Density**: `edges / (n * (n - 1))`

Lower density typically indicates **less coupling** (fewer cross-file dependencies).

## How dependencies are detected (approx.)

- Python: `import ...` / `from ... import ...` resolved to internal modules (best-effort)
- JS/TS: relative `import ... from './x'`, `import('./x')`, `require('./x')` resolved to internal files (best-effort)

## Run

Default scope (if directories exist):
- `python-server/app`
- `node-server/src`
- `frontend/src`

```bash
python3 scripts/cocomo_intermediate.py --no-cocomo --dsqd
```

Limit DSQD scope to specific directories:

```bash
python3 scripts/cocomo_intermediate.py --no-cocomo --dsqd \
  --dsqd-dir node-server/src \
  --dsqd-dir python-server/app
```

Output includes:
- nodes, edges, density
- average out-degree
- number of cycles (SCCs) and the largest cycle size

