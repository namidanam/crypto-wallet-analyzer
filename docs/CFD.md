# Cumulative Flow Diagram (CFD)

A **Cumulative Flow Diagram** visualizes how many work items exist in each workflow state over time (e.g. `Backlog`, `In Progress`, `Review`, `Done`). It’s commonly used for Kanban/Scrum reporting to show:
- WIP growth/shrinkage
- bottlenecks (bands widening)
- throughput stability

This repo can generate a CFD **SVG** using the same script used for other metrics.

## Input format (CSV daily snapshot)

Provide a CSV where each row is a date snapshot and each column is the **count of items currently in that state**.

Header rules:
- First column must be `date`
- Remaining columns are stage names (in the order you want stacked)
- Dates must be ISO: `YYYY-MM-DD`
- Counts must be integers `>= 0`

Example: `docs/cfd_sample.csv`

## Generate the diagram

From the repo root:

```bash
python3 scripts/cocomo_intermediate.py --cfd --cfd-input docs/cfd_sample.csv --cfd-output docs/cfd.svg
```

Open `docs/cfd.svg` in your browser and include it in your report.

## Related

- Throughput report: `docs/THROUGHPUT.md`
- Sprint burndown: `docs/BURNDOWN.md`
- Sprint burnup: `docs/BURNUP.md`

## Tips

- Use consistent stage names for your board (e.g. `Todo, In Progress, Review, Done`).
- Snapshot once per day (or per sprint day) at the same time.
- If you export from Jira/Trello/GitHub Projects, transform it into this snapshot CSV format.
