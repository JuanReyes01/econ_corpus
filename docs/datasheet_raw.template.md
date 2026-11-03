<!-- Prose template. `econ_corpus.datasheet` fills the double-brace names with numbers from the
data and writes docs/datasheet_raw.md. Edit the prose here, never the generated file. -->

# A raw table of U.S. newspaper opinion articles from ProQuest US Newsstream, {{year_min}}–{{year_max}}

Data descriptor, version 1.0 (2026-11-02). Companion to the cleaned dataset derived from this table.

## Abstract

The table holds {{n_articles}} records exported from ProQuest US Newsstream for ten U.S.
newspapers with the highest circulation, published {{year_min}}–{{year_max}}. Each record keeps
its metadata as exported, parsed dates, years and identifiers with explicit quality flags, its
file of origin, and a hash and word count of the article text. Nothing was removed or corrected,
so the table documents the source as delivered, including duplicates, news items and publications
outside the query. A companion table assigns every record one exclusion reason. This descriptor
reports how the data were collected and parsed, what they contain, and where they depart from
the intended design.

## 1. Background and summary

The table is the first stage of a corpus built to study how economists communicate with the
public through newspaper opinion pieces. It is a faithful reorganisation of the ProQuest exports,
kept raw so that other researchers can derive their own samples from it.

| | |
|---|---|
| Records | {{n_articles}} (plus {{n_footer_rows}} file-footer rows, one per export file) |
| Export files | {{n_files}} |
| Publication years | {{year_min}}–{{year_max}} |
| Newspapers queried | {{n_queried_newspapers}} |
| Distinct ProQuest ids | {{n_unique_ids}} |
| Records with a named author | {{n_with_author}} ({{with_author_pct}}) |

## 2. Methods

### 2.1 Collection

- **Source:** ProQuest US Newsstream, through the Universidad de los Andes library proxy.
- **Period:** exports dated {{download_first}} to {{download_last}}.
- **Newspapers:** {{n_queried_newspapers}}, selected for having the highest circulation in the
  U.S. Online editions are included on purpose, since much current opinion is published online.
  New York Post is not provided by the subscription.
- **Query:** exact publication name AND `noft(opinion OR op-ed OR editorial)`, a full-text
  search for those words.
- **Filters:** document type Commentary, Editorial or News; English; date range resumed from the
  last download.
- **How:** 100 results per page, select all, export every 5 pages (500 records) to a `.txt`
  file. CAPTCHAs solved by hand.

### 2.2 Parsing

- Each export file is split at lines of exactly 60 underscores. The last separator is followed
  by a footer, kept as a row with `is_footer` set.
- A record is a header, the body (after `Texto completo:`) and a block of `Label: value`
  metadata lines. The block is read backwards from its last line, one blank-separated block at a
  time, for as long as the block starts with a known label. This is needed because the optional
  `Materia` line makes the block start vary, and body lines can look like labels.
- Stray spaces that ProQuest inserts inside metadata values (`En glish`, `Aug 29, 202 2`) are
  tolerated when parsing. Values are stored as exported; space-free, case-folded copies are
  stored in the `*_key` columns. The body is never altered.
- Dates, years and identifiers are parsed with an explicit status (`ok`, `missing`,
  `unparseable`, and `year_only` for dates). No value is silently dropped.
- Provenance is kept in `source_file` and `record_index`. The article text is replaced by its
  SHA-256 hash, word count and character count.

### 2.3 Quality control

- Per file, the records found are compared with the separator lines counted independently: all
  {{n_files}} files contain one footer and as many records as separators.
- The detection of the `Materia` line was cross-checked against a plain text search on one in
  ten files, with no disagreement (details in `docs/decisions.md`). The cross-check found and
  fixed a parsing gap that had hidden `Materia` in 3.9% of records.
- Tests use synthetic records only, and every rule is logged with its evidence in
  `docs/decisions.md`.

## 3. Data records

### 3.1 Raw table

One row per record, in `data/interim/records.parquet`. The article text is ProQuest-licensed and
is not included.

| Column | Type | Content |
|---|---|---|
| `source_file` | string | Export file the record comes from |
| `record_index` | integer | Position in the file, from 0; the footer is last |
| `is_footer` | boolean | Row is the file footer, not an article |
| `title`, `author`, `publication`, `section` | string | Metadata as exported; multi-line values joined |
| `language`, `source_type`, `doc_type` | string | Metadata as exported |
| `year_raw`, `date_raw`, `id_raw` | string | Publication year, publication date and ProQuest id as exported |
| `pub_year`, `date_year`, `doc_id` | integer | Parsed year, year of the parsed date, and ProQuest id |
| `pub_date` | date | Parsed publication date; empty if only a year is given |
| `year_status`, `date_status`, `id_status` | string | `ok`, `missing`, `unparseable`; dates also `year_only` |
| `publication_key`, `language_key`, `source_type_key`, `doc_type_key` | string | Space-free, case-folded copies for comparing categories |
| `has_materia` | boolean | Record has a `Materia` (subject) line |
| `n_meta_fields` | integer | Metadata lines recognised in the record |
| `has_body` | boolean | Record has body text |
| `body_words`, `body_chars` | integer | Word and character counts of the body |
| `body_sha256` | string | SHA-256 hash of the body text |

### 3.2 Companion files

- `data/interim/exclusions.parquet`: `source_file`, `record_index` and one exclusion `reason`
  per row (section 6).
- `reports/tables/raw_by_year.csv` and `reports/tables/raw_by_download_date.csv`: yearly counts,
  and counts and publication-year range per download date.
- `reports/figures/records_by_year.svg`: Figure 1.

## 4. Contents

### 4.1 Newspapers

*With author*: share of records with a named author.

{{newspapers}}

### 4.2 Online editions and the blog label

{{online_editions}}

### 4.3 Blog-labelled records by document type

{{blog_profile}}

### 4.4 Years

![Records and distinct ids per publication year](../reports/figures/records_by_year.svg)

*Figure 1.* Records and distinct ProQuest ids per publication year.

{{decades}}

### 4.5 Document types and authorship

A record with two labels counts once under each. Editorials are mostly unsigned; commentary and
op-eds mostly signed.

{{doc_types}}

### 4.6 Sections

Top labels, grouped ignoring case. Each newspaper names its sections differently.

{{sections}}

### 4.7 Language

{{languages}}

### 4.8 Missing values

{{missing}}

### 4.9 Publications outside the query

Most common first. These are removed in the cleaned dataset (reason `not_queried_newspaper`).

{{other_publications}}

## 5. Technical validation

### 5.1 Do the filters hold?

| Filter | Result | Section |
|---|---|---|
| Newspapers | {{n_other_publications}} publications outside the list also appear. Queried newspapers with no records: {{missing_newspapers}} | 4.1, 4.9 |
| Source type | Not newspapers only, by design: {{n_blog}} records ({{blog_pct}}) are online editions that ProQuest labels `Blog, podcast o sitio web` | 4.1–4.3 |
| Document type | {{n_doc_type_labels}} distinct labels; {{n_outside_doc_types}} records ({{outside_doc_types_pct}}) carry none of Commentary, Editorial or News | 4.5 |
| English | {{english_only_pct}} English only; the rest bilingual or unlabelled | 4.7 |
| Dates | {{year_min}}–{{year_max}} | 4.4 |

The blog label:

- {{blog_online_pct}} of blog-labelled records are `(Online)` editions, mostly {{blog_newspapers}}.
- It belongs to the publication edition, not the article or date: per newspaper, all online
  records carry it or none do, in every year (section 4.2, last column).
- {{blog_opinion_section_pct}} sit in an opinion or editorial section (section 4.3). The content
  is news opinion, not casual blog posts.

### 5.2 Duplicates

{{n_duplicate_rows}} records ({{dup_pct}}) repeat a ProQuest id; {{n_unique_ids}} ids are
distinct. {{n_ids_in_several_files}} ids appear in more than one file and
{{n_repeats_inside_a_file}} repeat inside a file, which points to overlapping downloads.
{{dup_peak_year}} stands out in Figure 1: {{dup_peak_rows}} records but only
{{dup_peak_unique}} distinct ids, because its articles were downloaded repeatedly
({{dup_peak_multi_file_pct}} of its ids appear in 3 or more files). The peak is duplication,
not more articles. Duplicates are kept in the raw table.

### 5.3 News and opinion

Document type is not a reliable marker of opinion. {{news_label_opinion_section_pct}} of
records have a non-opinion label but sit in an opinion section, and {{no_opinion_signal_n}}
({{no_opinion_signal_pct}}) have neither an opinion label nor an opinion section. All are kept in
the raw table.

## 6. Usage notes and limitations

- **Exclusion reasons:** the companion table gives every record one reason: file footer,
  publication not queried, repeated id, repeated text (same title, date and newspaper),
  missing metadata, not opinion, unclear opinion, or kept. Records flagged `unclear_opinion`
  (no section, generic type, no opinion title) are not dropped and are left to the user to
  judge. Counts: `reports/tables/exclusion_counts.csv`.
- **Subtler duplicates** (reprints, edited versions under another title) are not detected.
- **Authors:** {{n_with_author}} records ({{with_author_pct}}) name an author. Unsigned pieces,
  mostly editorials, cannot be linked to a person.
- **No body text:** {{n_no_body}} records, all in {{n_no_body_files}} files.
- **Metadata as exported:** values keep ProQuest's stray spaces; use the `*_key` columns to
  compare categories. Some fields are recognised but not stored as columns (for example `URL`,
  `Empresa`, `Historial de publicaciones`).
- **Query matches text, not genre:** the keyword search returns any article mentioning
  "opinion" or "editorial", and News is a queried document type.

## 7. Code availability

The pipeline is in the repository `econ_corpus`: `parse` (exports to table), `exclusions`
(reasons), `tables`, `figures` and `datasheet` (this document). Every rule and its evidence are
in `docs/decisions.md`. `make datasheet` regenerates this document from the table.
