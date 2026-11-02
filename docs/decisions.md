# Decisions log

One entry per rule or filter: what, why, evidence, date.

| Date | Decision | Reason | Evidence |
|------|----------|--------|----------|
| 2026-11-02 | Build from the raw `.txt` exports, not the legacy CSV | The CSV converter corrupts or loses records (see CLAUDE.md) | Legacy audit |
| 2026-11-02 | Parse the metadata block backwards from `Base de datos:`, accepting only blocks that start with a known label (matched ignoring stray spaces) | 27.6% of records have no `Materia` line, and body lines can look like labels (`Credit:`, `Editorial:`), so scanning forward cannot find where the body ends | Layout sampled in 8 raw files; synthetic tests in `tests/test_parse.py` |
| 2026-11-02 | Normalize stray spaces only in metadata values; the body is never altered (only CRLF to LF and outer whitespace trimmed before hashing) | ProQuest inserts spaces inside metadata values, the body is clean and is the research object | CLAUDE.md known facts |
| 2026-11-02 | Parsed dates, years and ids carry an explicit status column (`ok`, `missing`, `unparseable`, plus `year_only` for dates); never silent NaT | Silent NaT hides how many dates were lost and why | `parse_date`, `parse_int` |
| 2026-11-02 | Compare categories through `*_key` columns (all whitespace removed, casefolded) and keep the raw value | Stray spaces split one category into many ('English', 'En glish') | `compact()` in `parse.py` |
| 2026-11-02 | The parquet table stores `body_sha256`, `body_words`, `body_chars` instead of body text | 7.5 GB of licensed text should not be copied; any body can be re-read from `source_file` + `record_index`. Owner chose this | Owner decision, 2026-11-02 |
| 2026-11-02 | The file footer is kept as a row with `is_footer = True`, not dropped silently | Counts must add up: records + footers = separators per file | `check_text()` in `parse.py` |
| 2026-11-02 | Label whitelist is data-driven: `e-ISSN`, `columna`, `Número de acceso`, `Fecha del hito`, `Características del documento`, `Detalles de fuente`, `Número`, `Autor corporativo/institucional` added after the first full run | Unknown labels stopped the backward walk: 579k records lost title/date and "no Materia" read 63.5% | Rerun: no title 1,916, no Materia 31.5% |
| 2026-11-02 | Sanity check counts exact 60-underscore lines; other underscore rules are reported as `odd_rules`, not failures | 34 files held underscore rules inside article text (lengths 20-168) but parsed to the expected 500 records | All 2,801 files pass after the change |
| 2026-11-02 | Ruff runs with `select = ["ALL"]` on `econ_corpus/` and `tests/`; ignored: D203, D213 (contradict D211, D212), COM812, ISC001 (conflict with the formatter), CPY001 (no copyright header policy); tests also ignore S101, PLR2004, D103, INP001 | Owner wants the strictest linting; the ignores are only rules that contradict each other or are meaningless here | `pyproject.toml` |
| 2026-11-02 | Module docstring says what the module is, its input and output, and what does and does not belong there; format details live in line comments next to the code they explain | The header had become a layout dump that did not explain the file's purpose | `econ_corpus/parse.py` |
| 2026-11-02 | A pre-commit hook runs `ruff format --check`, `ruff check` and `pytest` through `uv run` (local hooks, no network) | Same commands as `make lint` and `make test`, so a commit cannot skip them | `.pre-commit-config.yaml`, installed with `uv run pre-commit install` |
