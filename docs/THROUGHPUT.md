# Throughput Report

Throughput is a **delivery metric**: how many work items reach **Done** per period (day/week).

This repo generates a throughput report from the same **daily snapshot CSV** used for the CFD.

## Input

Use the same CSV format as `docs/cfd_sample.csv`:
- `date` column (`YYYY-MM-DD`)
- stage columns with counts `>= 0`

Throughput is computed from the **delta of the Done stage count** between snapshots.

## Generate the report

Daily throughput (default):

```bash
python3 scripts/cocomo_intermediate.py --no-cocomo --throughput \
  --tp-input docs/cfd_sample.csv \
  --tp-output docs/throughput.md
```

Weekly throughput:

```bash
python3 scripts/cocomo_intermediate.py --no-cocomo --throughput \
  --tp-input docs/cfd_sample.csv \
  --tp-output docs/throughput_weekly.md \
  --tp-period weekly
```

Choose which column is “Done” (default: last column):

```bash
python3 scripts/cocomo_intermediate.py --no-cocomo --throughput \
  --tp-input docs/cfd_sample.csv \
  --tp-stage Done
```

## Notes

- If your Done count decreases (reopens / scope changes), the script **clips negative deltas to 0** by default.
- To allow negatives in the report, add `--tp-allow-negative`.

## Related

- Cumulative Flow Diagram: `docs/CFD.md`
- Sprint burndown: `docs/BURNDOWN.md`
- Sprint burnup: `docs/BURNUP.md`
