# econ_corpus

Build and audit a corpus of U.S. newspaper opinion articles (ProQuest US Newsstream) to study
how economists communicate. The repository holds code and documentation only; the data are
ProQuest-licensed and never committed.

Two datasets come out of it, each with a datasheet:

- **Raw table** (`docs/datasheet_raw.md`): every exported record with all its metadata and
  text, repeats removed.
- **Cleaned dataset** (`docs/datasheet_clean.md`): opinion articles from the ten queried
  newspapers signed by a person, with separate article, author and link tables.

Every rule and its evidence are logged in `docs/decisions.md`.

## Setup

```bash
make requirements
```

Needs `uv`. `make pdf` also needs Google Chrome (`google-chrome`).

## Pipeline

Run the steps in this order. Each one reads the output of the ones before it and refuses to
run on inputs that do not belong together.

| Step | Command | Reads | Writes |
|---|---|---|---|
| 1 | `make parse` | the `.txt` exports in `RAW_DIR` | `data/interim/records.parquet` |
| 2 | `make exclusions` | step 1, `data/review/byline_parts.csv` | `data/interim/exclusions.parquet`, `reports/tables/exclusion_counts.csv` |
| 3a | `make export` | steps 1 and 2 | `data/processed/econ_corpus_raw.csv` |
| 3b | `make datasheet` | steps 1 and 2 | `docs/datasheet_raw.md`, raw tables and figures in `reports/` |
| 4 | `make processed` | steps 1 and 2, `data/review/` | `data/processed/clean/*.csv` |
| 5 | `make review-cases` | steps 1, 2 and 4, `data/review/` | `data/review/cases/*.csv` |
| 6 | `make datasheet-clean` | steps 1, 2 and 4, `data/review/` | `docs/datasheet_clean.md`, `clean_flow` table and figure |

`make raw` runs steps 2 to 3b and `make cleaned` runs steps 2 and 4 to 6. `RAW_DIR` defaults
to the folder named in the Makefile: `make parse RAW_DIR=/path/to/exports`.

### Manual review of authors

Step 5 lists the author cases a rule cannot settle. Each case is decided by reading it, and
the decisions are appended to `data/review/byline_parts.csv` (how a byline part is read) and
`data/review/author_pairs.csv` (whether two names are one person). Because the decisions
change which articles have a person among their authors, steps 2 and 4 to 6 are run again
after every review round (`make cleaned`), until step 5 lists no case. Step 4 stops if the
reasons were computed with other review files. `data/review/README.md` records who reviewed
what.

### Delivery

```bash
make pdf
make delivery
```

`make delivery` writes the folder named by `DELIVERY`: the exports, the raw CSV with its
datasheet, and the cleaned tables with their datasheet and the review files.

## Development

```bash
make test
make lint
```

One module per pipeline stage in `econ_corpus/`, pure functions with tests in `tests/`
(synthetic records only, never ProQuest text). A pre-commit hook runs format, lint and tests.
