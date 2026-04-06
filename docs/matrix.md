COCOMO: python3 scripts/cocomo_intermediate.py --mode semidetached --driver RELY=H --driver CPLX=VH --driver TOOL=H
HALSTEAD: python3 scripts/cocomo_intermediate.py --halstead
FPA (example): python3 scripts/cocomo_intermediate.py --fpa --ei 3 2 1 --eo 1 1 0 --eq 2 0 0 --ilf 1 1 0 --eif 0 1 0 --gsc 3 2 2 3 2 1 2 2 3 2 1 2 1 2
CFD (SVG): python3 scripts/cocomo_intermediate.py --no-cocomo --cfd --cfd-input docs/cfd_sample.csv --cfd-output docs/cfd.svg
THROUGHPUT (MD): python3 scripts/cocomo_intermediate.py --no-cocomo --throughput --tp-input docs/cfd_sample.csv --tp-output docs/throughput.md --tp-period weekly
BURNDOWN (SVG): python3 scripts/cocomo_intermediate.py --no-cocomo --burndown --bd-input docs/cfd_sample.csv --bd-output docs/burndown.svg --bd-done-stage Done
BURNUP (SVG): python3 scripts/cocomo_intermediate.py --no-cocomo --burnup --bu-input docs/cfd_sample.csv --bu-output docs/burnup.svg --bu-done-stage Done
COMMENT DENSITY: python3 scripts/cocomo_intermediate.py --no-cocomo --comment-density
DSQD: python3 scripts/cocomo_intermediate.py --no-cocomo --dsqd
