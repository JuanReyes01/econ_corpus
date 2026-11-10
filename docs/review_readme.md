# Manual review of doubtful authors

Two tables of decisions that the pipeline applies when it reads the bylines (`make exclusions`,
`make processed`). With them, the cleaned dataset is reproduced exactly: copy this folder to
`data/review/` in the repository. No person decided the cases: each one was read and decided
by a large language model (Claude, Anthropic), without web search, under written
instructions: correct or merge only with supporting evidence, answer unsure when in doubt.
The datasheet of the cleaned dataset (section 2.4) describes the review and its audits.

- `byline_parts.csv`: one row per byline part whose reading was checked. `part` is the text
  as exported; `replacement` is `KEEP` (read right), a corrected byline (`Family, Given`,
  several people separated by `;`), `NOBODY` (names no person), `UNSURE` or `CREDIT` (a
  production credit: an author only when first in the byline); `reason` is the evidence;
  `reviewer` is the model, the date and the round.
- `author_pairs.csv`: one row per pair of look-alike authors (`key_a`, `key_b` are their name
  keys, `name_a`, `name_b` their names). `decision` is `same`, `different` or `unsure`;
  `reason` is the evidence; `reviewer` as above.
