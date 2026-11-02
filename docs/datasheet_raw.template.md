<!-- Prose template. `econ_corpus.datasheet` fills the double-brace names with numbers from the
data and writes docs/datasheet_raw.md. Edit the prose here, never the generated file. -->

# Datasheet: raw table of U.S. newspaper opinion articles (ProQuest)

Draft. Items marked **[TBD]** are not yet documented.

## 1. Summary

- **Records:** {{n_articles}}, from {{n_files}} export files; publication years {{year_min}}–{{year_max}}.
- **Unit:** one row per exported record. Nothing is removed; values that cannot be parsed are flagged.
- **Columns:** parsed metadata, provenance (`source_file`, `record_index`), and a SHA-256 hash,
  word count and character count of the body. The article text is ProQuest-licensed and is not
  included.

## 2. Collection

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

## 3. Filter check

| Filter | Result | Evidence |
|---|---|---|
| Newspapers | {{n_other_publications}} publications outside the list also appear. Queried newspapers with no records: {{missing_newspapers}} | 4.1, 4.7 |
| Source type | Not newspapers only, by design: {{n_blog}} records ({{blog_pct}}) are online editions that ProQuest labels `Blog, podcast o sitio web` | 4.1, 4.1b, 4.1c |
| Document type | {{n_doc_type_labels}} distinct labels; {{n_outside_doc_types}} records ({{outside_doc_types_pct}}) carry none of Commentary, Editorial or News | 4.3 |
| English | {{english_only_pct}} English only; the rest bilingual or unlabelled | 4.5 |
| Dates | {{year_min}}–{{year_max}} | 4.2 |

The blog label:

- {{blog_online_pct}} of blog-labelled records are `(Online)` editions, mostly {{blog_newspapers}}.
- It belongs to the publication edition, not the article or date: per newspaper, all online
  records carry it or none do, in every year (4.1b, last column).
- {{blog_opinion_section_pct}} sit in an opinion or editorial section (4.1c). The content is
  news opinion, not casual blog posts.

## 4. Contents

### 4.1 Newspapers

*With author*: share of records with a named author.

{{newspapers}}

### 4.1b Online editions and the blog label

{{online_editions}}

### 4.1c Blog-labelled records by document type

{{blog_profile}}

### 4.2 Years

By decade; yearly table in `reports/tables/raw_by_year.csv`.

{{decades}}

{{dup_peak_year}} stands out: {{dup_peak_rows}} records but only {{dup_peak_unique}} distinct ids.
Its articles were downloaded repeatedly ({{dup_peak_multi_file_pct}} of its ids appear in 3 or
more files), so the peak is duplication, not more articles.

### 4.3 Document types and authorship

A record with two labels counts once under each. Editorials are mostly unsigned; commentary and
op-eds mostly signed.

{{doc_types}}

### 4.4 Sections

Top labels, grouped ignoring case. Each newspaper names its sections differently.

{{sections}}

### 4.5 Language

{{languages}}

### 4.6 Missing values

{{missing}}

### 4.7 Publications outside the query

Most common first. Why the query returned them: **[TBD]**.

{{other_publications}}

## 5. Known issues

- **Duplicates:** {{n_duplicate_rows}} records ({{dup_pct}}) repeat a ProQuest id; {{n_unique_ids}}
  ids are distinct. {{n_ids_in_several_files}} ids appear in more than one file and
  {{n_repeats_inside_a_file}} repeat inside a file, which points to overlapping downloads. Kept.
- **News mixed with opinion:** document type is not a reliable marker.
  {{news_label_opinion_section_pct}} of records have a non-opinion label but sit in an opinion
  section; {{no_opinion_signal_n}} ({{no_opinion_signal_pct}}) have neither an opinion label nor
  an opinion section. All are kept here; selecting opinion pieces belongs to the cleaned dataset.
- **Authors:** {{n_with_author}} records ({{with_author_pct}}) name an author. Unsigned pieces,
  mostly editorials, cannot be linked to a person.
- **No body text:** {{n_no_body}} records, all in {{n_no_body_files}} files.
- **Stray spaces:** ProQuest inserts spaces inside metadata values (`En glish`). Values are kept
  as exported; the `*_key` columns are the space-free versions for comparing categories.
- **Parsing:** rules and evidence in `docs/decisions.md`; parser in `econ_corpus/parse.py`.
