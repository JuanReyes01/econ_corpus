# Pipeline 1: the raw table

From the `.txt` exports of ProQuest to one table with every record, and its datasheet.

```bash
uv run python -m econ_corpus.raw                    # steps 2 to 3b, from the records already parsed
uv run python -m econ_corpus.raw /path/to/exports   # step 1 first (about five minutes)
```

`__main__.py` holds the order. Each step can also be run alone (`make parse`, `make
exclusions`, `make export`, `make datasheet`).

| Step | File | What it does | Reads | Writes |
|---|---|---|---|---|
| 1 | `parse.py` | Reads the exports into one table, a row per record, with every metadata field and the text; adds a hash and the word and character counts of the text; checks every file before replacing the table | the folder of exports | `data/interim/records.parquet` |
| 2 | `exclusions.py` | Gives every row exactly one reason: file footer, repeated id, repeated text, publication not queried, not opinion, no text, no author, short or cartoon, not English, kept | the records, `data/review/byline_parts.csv` | `data/interim/exclusions.parquet`, `reports/tables/exclusion_counts.csv`, `data/processed/econ_corpus_raw_reasons.csv` |
| | `reasons.py` | The reasons as data (code, meaning, whether the row stays in the raw table, whether it leaves the cleaned dataset); the file of reasons and the fingerprints that tie it to its records and to the code | | |
| | `text_marks.py` | Reads the texts once and gives, per record, what the reasons take from them: the share of English words, whether the first line is the rubric of an opinion page, and the words written by the author | | |
| | `prose.py` | Counts the words of a text that its author wrote: the lines that the export and the newspaper add around it (credits, captions, notices, lists of links) are listed as data and left out | | |
| | `language.py` | Tells whether a text is in English, from the commonest English words at its start | | |
| 3a | `export.py` | Writes the raw table as a CSV: every row whose reason keeps it in the raw table | the records, the reasons | `data/processed/econ_corpus_raw.csv` and its stamp, `econ_corpus_raw.json` |
| 3b | `datasheet.py` | Fills `docs/datasheet_raw.template.md` with the numbers, tables and figures of the raw table | the records, the reasons | `docs/datasheet_raw.md`, `reports/tables/raw_*.csv`, `reports/figures/records_by_year.svg` and `repeats_by_year.svg` |

The reasons of step 2 serve both datasets: they say which rows leave the raw table and which
records the cleaned dataset keeps. Pipeline 2 starts from them.
