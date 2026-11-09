# Tables and figures of the datasheets

Everything in `tables/` and `figures/` is written by the pipeline (steps 2, 3b and 6) and
shown in the two datasheets of `docs/`. Nothing here is edited by hand: `make check` stops
if a file differs from what the current data gives, or if a file is written by no step.
