# econ_corpus

Build and audit a corpus of U.S. newspaper opinion articles (ProQuest US Newsstream) to study
how economists communicate. The repository holds code and documentation only; the data are
ProQuest-licensed and never committed.

Two datasets come out of it, each with a datasheet:

- **Raw table** (`docs/datasheet_raw.md`): every exported record with all its metadata and
  text, repeats removed.
- **Cleaned dataset** (`docs/datasheet_clean.md`): opinion articles from the ten queried
  newspapers signed by a person, with at least 30 words of English text written by the
  author (a drawing alone is not text), in
  separate article, author and link tables.

Every rule and its evidence are logged in `docs/decisions.md`.

## Setup

```bash
make requirements
```

Needs `uv`. `make pdf` also needs Google Chrome (`google-chrome`).

## Layout

```
econ_corpus/
├── raw/      pipeline 1: from the ProQuest exports to the raw table      (steps 1 to 3b)
├── clean/    pipeline 2: from the records to the cleaned dataset         (steps 4 to 6)
├── names/    reading bylines and deciding which names are one author     (used by both)
├── shared/   counts, tables, figures and PDF of the two datasheets
└── check.py  the last step: every output belongs to the current data     (step 7)
docs/         the two datasheets, their templates and the log of decisions
reports/      tables and figures of the datasheets, written by the pipeline
tests/        the tests, on synthetic records only (never ProQuest text)
data/         not in the repository (ProQuest licence): records, tables, review files
```

Each folder of `econ_corpus/` has a README that says what every file does, what it reads
and what it writes.

## Pipelines

```bash
uv run python -m econ_corpus.raw /path/to/exports   # pipeline 1 (without the folder: from step 2)
uv run python -m econ_corpus.clean                  # pipeline 2
make check                                          # step 7
```

The steps, in order. Each one reads the output of the ones before it and refuses to run on
inputs that do not belong together; `make <step>` runs one alone.

| Step | Command | Reads | Writes |
|---|---|---|---|
| 1 | `make parse` | the `.txt` exports in `RAW_DIR` | `data/interim/records.parquet` |
| 2 | `make exclusions` | step 1, `data/review/byline_parts.csv` | `data/interim/exclusions.parquet`, `reports/tables/exclusion_counts.csv`, `data/processed/econ_corpus_raw_reasons.csv` |
| 3a | `make export` | steps 1 and 2 | `data/processed/econ_corpus_raw.csv` |
| 3b | `make datasheet` | steps 1 and 2 | `docs/datasheet_raw.md`, raw tables and figures in `reports/` |
| 4 | `make processed` | steps 1 and 2, `data/review/` | `data/processed/clean/*.csv` and `manifest.json` |
| 5 | `make review-cases` | steps 1, 2 and 4, `data/review/` | `data/review/cases/*.csv` |
| 6 | `make datasheet-clean` | steps 1, 2 and 4, `data/review/` | `docs/datasheet_clean.md`, `clean_flow` table and figure |
| 7 | `make check` | every output above | nothing: it builds the datasheets, their tables and figures and the case lists again, and stops if any differs or the raw CSV or a cleaned table is stale |

After any change to the code in `econ_corpus/`, run the steps again from step 2: the
reasons carry a fingerprint of the code and are refused once it changes. After a change to
`raw/parse.py`, start from step 1: the table carries a fingerprint of the parser.

Steps 1 to 3b are pipeline 1 (`econ_corpus/raw`) and steps 4 to 6 are pipeline 2
(`econ_corpus/clean`). `make raw` runs steps 2 to 3b and `make cleaned` runs steps 2 and 4 to 6. `RAW_DIR` defaults
to the folder named in the Makefile: `make parse RAW_DIR=/path/to/exports`.

### Manual review of authors

Step 5 lists the author cases a rule cannot settle. Each case is decided by reading it, and
the decisions are appended to `data/review/byline_parts.csv` (how a byline part is read) and
`data/review/author_pairs.csv` (whether two names are one person). Because the decisions
change which articles have a person among their authors, steps 2 and 4 to 6 are run again
after every review round (`make cleaned`), until step 5 lists no case. `data/review/README.md`
records who reviewed what.

The review files are not in the repository (they hold names of private persons). A copy
travels with every delivery, in `3_clean/review/`: copy its contents to `data/review/`
(`mkdir -p data && cp -rT 3_clean/review data/review`) before running the pipeline on
another machine. The steps stop if `data/review/` does not exist; an empty
folder runs the pipeline with no review.

### What stops a step

| Check | Stops |
|---|---|
| A file of the exports has no footer, text before its first record, or a line that is almost a separator (59 to 61 underscores once spaces are removed) | step 1, before the table is replaced |
| The table of step 1 was written by another version of `raw/parse.py` | steps 2 to 7 |
| The reasons were computed from other records (a new parse) or by other code | steps 3a to 7 |
| The reasons were computed with another `byline_parts.csv` | steps 4 to 7 |
| The cleaned tables were built from other reasons, review files or code, or a table is not the file the build wrote (`manifest.json` holds a fingerprint of each) | steps 5 to 7 |
| `byline_parts.csv` repeats a case or holds an unreadable name | steps 2 and 4 to 7 |
| `author_pairs.csv` repeats a case or holds an unknown verdict | steps 4 to 7 |
| `data/review/` is missing, or holds files but not the two review files | steps 2 and 4 to 7 |
| The raw CSV, its file of reasons, a datasheet, a table or figure of `reports/`, or a list of review cases is not what the current data gives, or one of those folders holds a file that no step writes | step 7, and so the delivery |

The checks compare files with files. Step 1 cannot tell that an export file is missing from
`RAW_DIR`, and files named `.TXT` are not read: the datasheet states how many files were
parsed.

### Delivery

```bash
make delivery
```

`make delivery` runs step 7, renders the two datasheets as PDF and copies everything into
the folder named by `DELIVERY`: the exports, the raw CSV with its datasheet, and the cleaned tables with their
datasheet and the review files. The folder holds copies, so running the pipeline again does
not change a delivery; run `make delivery` again to replace it.

## Development

```bash
make test
make lint
```

One module per pipeline step, grouped by pipeline (`econ_corpus/README.md`), pure functions
with tests in `tests/`
(synthetic records only, never ProQuest text). A pre-commit hook runs format, lint and tests.
