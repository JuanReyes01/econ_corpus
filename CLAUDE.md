# econ_corpus

Build and audit a corpus of U.S. newspaper opinion articles (ProQuest) to study how economists communicate. The pipeline produces a raw table and a cleaned dataset, each with a datasheet; no modeling yet.

## Code rules (the owner wants to understand every change)

1. One module per pipeline step, grouped by pipeline: `econ_corpus/raw` (exports to raw table) and `econ_corpus/clean` (records to cleaned dataset), with what they share in `econ_corpus/names` and `econ_corpus/shared`; each folder has a README that lists its files. Aim for under 200 lines each. Pure functions, with tests.
2. Notebooks only call package functions and show results. No logic in notebooks.
3. Exclusion reasons live in one place, as data (a reasons table), not scattered across code. Each article gets exactly one reason, so counts add up.
4. Every filter or rule is recorded in `docs/decisions.md` with its reason.
5. Small commits, conventional commit style, no AI attribution lines. Explain the diff to the owner before committing.
6. Test first (pytest). Run with `make test`, lint with `make lint`. Use `uv run`, never bare `python`.

## Data (never copy into the repo, ProQuest license)

- Source of truth: 2,801 ProQuest `.txt` exports in `/home/juanc/data/econ_corpus/raw/ProQuestDownloads` (about 7.5 GB, dated 2024-11-22 to 2025-01-26).
- Legacy 14 GB CSV (damaged by the old converter, use only for comparison): `/home/juanc/data/econ_corpus/legacy/articulos_proquest_raw.csv`.
- Old converter code: `/home/juanc/data/econ_corpus/legacy/CreateDatabase.ipynb`.
- Legacy repo with EDA and slim-table code to reuse selectively: `/home/juanc/code/econ/econ_comm_analysis` (see `src/article_processing_pipeline/eda.py`, `slim.py`).

## Known facts about the raw data (see docs/datasheet_raw.md for the numbers)

- ProQuest export inserts stray spaces inside metadata values ('En glish', 'Per iódicos', 'Aug 29, 202 2'), titles and author names included. The body text is clean. Normalize before comparing categories and re-parse dates, years and ids.
- 30% of records are labelled blog/podcast/website: they are the '(Online)' editions of NYT, Washington Post, Chicago Tribune, LA Times and Tampa Bay Times, added on purpose. The label belongs to the edition, not to the article.
- About 296 publications outside the ten queried newspapers appear (reason `not_queried_newspaper`).
- Duplicate ProQuest ids come from overlapping download rounds across files (none inside one file). The 2014 spike is this artifact.
- 27.6% of records have no 'Materia' line; 5 files from 2024-12-04 have no body.
- About 51% of records have no author (anonymous, editorial boards, unsigned).

## Inclusion criteria of the cleaned dataset (settled, see docs/decisions.md)

Opinion pieces (by document type, section or title), from the 10 queried newspapers, with at least 30 words of English text written by the author (a drawing alone is not text), signed by at least one person; production credits are not authors. The pipeline order and commands are in README.md.
