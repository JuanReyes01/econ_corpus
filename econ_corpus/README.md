# The package

Two pipelines, run one after the other, and what they share.

| Folder | What it is | Run it |
|---|---|---|
| `raw/` | Pipeline 1: from the ProQuest exports to the shared raw table and its datasheet | `uv run python -m econ_corpus.raw` |
| `clean/` | Pipeline 2: from the records and their reasons to the cleaned dataset and its datasheet | `uv run python -m econ_corpus.clean` |
| `names/` | Reading bylines and deciding which names are one author; used by both pipelines | |
| `shared/` | Counts, tables, figures and PDF for the datasheets | |
| `overview.py` | Step 6b: the overview datasheet of both pipelines, figures first (`docs/datasheet.md`) | `uv run python -m econ_corpus.overview` |
| `check.py` | The last step: stops if an output on disk does not belong to the current data | `uv run python -m econ_corpus.check` |

Each folder has a README that says what every file does, what it reads and what it writes.

A folder only uses the ones above it in this list: `names`, `shared`, `raw`, `clean`,
`overview`, `check`. Pipeline 1 needs `names` because whether a byline names a person is part of the
reason given to a record; pipeline 2 starts from what pipeline 1 wrote.
