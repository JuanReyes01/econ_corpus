# Pipeline 2: the cleaned dataset

From the records and their reasons (pipeline 1) to the signed opinion articles and their
authors, as normalised tables, and their datasheet.

```bash
uv run python -m econ_corpus.clean
```

`__main__.py` holds the order. Each step can also be run alone (`make processed`, `make
review-cases`, `make datasheet-clean`).

| Step | File | What it does | Reads | Writes |
|---|---|---|---|---|
| 4 | `processed.py` | Writes the cleaned dataset: the articles kept, one row per author, every name variant of each author, the links between articles and authors, and the pairs of authors that look alike and were not merged | the records, the reasons, `data/review/` | `data/processed/clean/*.csv` |
| | `manifest.py` | Records next to the tables what they were built from; the later steps refuse tables built from other inputs | | `data/processed/clean/manifest.json` |
| 5 | `review_cases.py` | Lists the author cases that a rule cannot settle, with the evidence a reviewer needs | the cleaned tables, the records, the reasons, `data/review/` | `data/review/cases/*.csv` |
| | `author_cases.py` | The cases about whole authors: look-alike pairs not yet reviewed, merges of a name with a suffix and one without, variants of one author years apart, and judged pairs that apply to nothing any more | | |
| 6 | `datasheet_clean.py` | Fills `docs/datasheet_clean.template.md` with the numbers, tables and figure of the cleaned dataset | the cleaned tables, the records, the reasons, `data/review/` | `docs/datasheet_clean.md`, `reports/tables/clean_flow.csv`, `reports/figures/clean_flow.svg` |
| | `clean_tables.py` | The tables of that datasheet and of the overview: the exclusions from the raw table to the cleaned dataset (the full flow from the rows parsed is their base), and the counts of articles and authors by newspaper, year and decade | | |

After a round of manual review (new decisions in `data/review/`), run step 2 of pipeline 1
and then this pipeline again, until step 5 lists no case: `make cleaned`.
