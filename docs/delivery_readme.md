# econ_corpus: deliverables

U.S. newspaper opinion articles from ProQuest US Newsstream. Internal use only (ProQuest license).

- `1_raw_txt/`: the 2,801 ProQuest `.txt` exports, untouched.
- `2_raw_csv/`: `econ_corpus_raw.csv` (one row per record, article text and every metadata
  field, repeats removed) and `datasheet_raw.pdf`, which describes the table and every change
  made to the exports.
- `3_clean/`: the cleaned dataset. `articles.csv` (signed opinion articles), `authors.csv`,
  `author_names.csv`, `article_authors.csv` (the link between articles and authors),
  `author_candidates.csv` (look-alike authors not merged) and `datasheet_clean.pdf`.
  `review/` holds the manual review of authors, done by a language model: the decisions, the
  cases as they were shown to the reviewers, and a README.

This folder is written by `make delivery` in the repository, from the current outputs.

Code: https://github.com/JuanReyes01/econ_corpus (private).
