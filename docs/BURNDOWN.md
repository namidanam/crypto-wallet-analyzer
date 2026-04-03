# Sprint Burndown Chart

A sprint **burndown chart** plots **remaining work** over the sprint timeline.

This repo generates a burndown **SVG** from the same daily snapshot CSV used for CFD/throughput.

## Input

Use the same CSV format as `docs/cfd_sample.csv`:
- `date` (`YYYY-MM-DD`)
- stage columns with counts `>= 0`

The script computes:
- `done = <DoneStage>`
- `remaining = total_items - done` (i.e., sum of all non-done stage counts)

By default, the **Done stage is the last column**.

## Generate burndown SVG

```bash
python3 scripts/cocomo_intermediate.py --no-cocomo --burndown \
  --bd-input docs/cfd_sample.csv \
  --bd-output docs/burndown.svg \
  --bd-done-stage Done
```

Optional:
- Hide ideal line: `--bd-no-ideal`
- Customize size: `--bd-width 1200 --bd-height 700`

## Related

- Sprint burnup: `docs/BURNUP.md`
- Cumulative Flow Diagram: `docs/CFD.md`
