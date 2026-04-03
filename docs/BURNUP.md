# Sprint Burnup Chart

A sprint **burnup chart** plots:
- **Done** (completed work) over time
- **Scope** (total work) over time

This repo generates a burnup **SVG** from the same daily snapshot CSV used for CFD/throughput.

## Input

Use the same CSV format as `docs/cfd_sample.csv`:
- `date` (`YYYY-MM-DD`)
- stage columns with counts `>= 0`

The script computes:
- `done = <DoneStage>`
- `scope = sum(all stage counts)`

By default, the **Done stage is the last column**.

## Generate burnup SVG

```bash
python3 scripts/cocomo_intermediate.py --no-cocomo --burnup \
  --bu-input docs/cfd_sample.csv \
  --bu-output docs/burnup.svg \
  --bu-done-stage Done
```

Optional:
- Hide ideal line: `--bu-no-ideal`
- Hide scope line: `--bu-no-scope`
- Customize size: `--bu-width 1200 --bu-height 700`

