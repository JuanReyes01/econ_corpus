# econ_corpus

Build and audit a corpus of U.S. newspaper opinion articles (ProQuest) to study how economists communicate. Phase 1 is a data-quality audit of the raw downloads, not modeling.

## Code rules (the owner wants to understand every change)

1. One module per pipeline stage in `econ_corpus/` (for example `parse`, `audit`, `exclusions`). Aim for under 200 lines each. Pure functions, with tests.
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

## Known facts about the raw data (from the legacy audit)

- ProQuest export inserts stray spaces inside metadata values ('En glish', 'Per iódicos', 'Aug 29, 202 2'). The body text is clean. Normalize before comparing categories and re-parse dates, years and ids.
- The "newspapers only" filter never worked: 30% of records are blogs/podcasts/websites, almost all from the '(Online)' editions of NYT, Washington Post, Chicago Tribune, LA Times, Tampa Bay Times.
- Search query had no publication qualifier: about 494 unrelated publications slipped in.
- Duplicate `id_proQuest` come from overlapping download rounds across files (none inside one file). The 2014 spike is this artifact.
- Old converter flaws: 27.6% of records have no 'Materia' line so the text absorbs the metadata block; each file footer became an empty row; 5 files from 2024-12-04 have no body; the 3 files of 2025-01-26 never made it into the CSV.
- About 51% of records have no author (anonymous, editorial boards, unsigned).

## Intended inclusion criteria (to confirm)

Opinion pieces (Commentary, Editorial, Opinions) signed by a person, in English, from the 11 target newspapers.
