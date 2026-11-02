<!-- Prose template. `econ_corpus.datasheet` fills the double-brace names with numbers from the
data and writes docs/datasheet_raw.md. Edit the prose here, never the generated file. -->

# Datasheet: raw table of U.S. newspaper opinion articles (ProQuest)

Draft. Items marked **[TBD]** still need an answer from the data collector.

## 1. What this is

One row per record exported from ProQuest: **{{n_articles}} records** from **{{n_files}} export
files**, publication years **{{year_min}}–{{year_max}}**. The table is the exports reorganised, not
cleaned: nothing is dropped, and values that could not be parsed are flagged. It keeps the
parsed metadata, where each record came from (`source_file`, `record_index`), and a SHA-256 hash,
word count and character count of the body. The article text itself is ProQuest-licensed and
is not in the table.

## 2. Where it comes from

- **Source:** ProQuest US Newsstream, through the Universidad de los Andes library proxy.
- **When:** exports dated {{download_first}} to {{download_last}} (from the file names).
- **Query (as documented by the collector):** exact publication name for {{n_queried_newspapers}} newspapers, AND
  `noft(opinion OR op-ed OR editorial)`, a search of the full text for those words.
- **Filters:** document type Commentary, Editorial or News, English, and a date range that
  resumed from the last download. The collector added the online editions of the newspapers on
  purpose, because much current opinion is published there. ProQuest labels those editions
  `Blog, podcast o sitio web`.
- **How:** 100 results per page, select all, export every 5 pages (500 records) as a `.txt`
  file. Partly automated; CAPTCHAs solved by hand.
- **Why these newspapers:** they are among the U.S. newspapers with the highest circulation.
  The scraper notes also list New York Post, but the library's ProQuest subscription does not
  provide it (checked by the collector), so it has no records.

## 3. Did the filters hold?

| Filter | Result | Evidence |
|---|---|---|
| Newspapers | Yes, but {{n_other_publications}} publications outside the list also appear. Queried newspapers with no records: {{missing_newspapers}} | 4.1, 4.7 |
| Source type | Not newspapers only, by design: {{n_blog}} records ({{blog_pct}}) are online editions that ProQuest labels `Blog, podcast o sitio web` | 4.1, 4.1b, 4.1c |
| Document type | Labels vary widely ({{n_doc_type_labels}} distinct). {{n_outside_doc_types}} records ({{outside_doc_types_pct}}) carry none of Commentary, Editorial or News | 4.3 |
| English | Yes, {{english_only_pct}} are English only; the rest are bilingual or unlabelled | 4.5 |
| Dates | Yes, {{year_min}}–{{year_max}} | 4.2 |

What the blog label means here:

- {{blog_online_pct}} of the blog-labelled records are `(Online)` editions. Most come from
  {{blog_newspapers}} (columns *Online* and *Blog/podcast/website* in 4.1).
- The label belongs to the publication edition, not to the article or the date. For each
  newspaper, either all of its online records carry it or none do, in every year (4.1b, last
  column). The share changes over time only because online editions start in different years
  (4.2).
- They are mostly opinion content, not casual blog posts: {{blog_opinion_section_pct}} sit in an
  opinion or editorial section (4.1c).
- The source is best read as a database of news opinion pieces, news articles and news
  organisations' websites, not of newspapers in print only.

## 4. What is in it

### 4.1 Newspapers, editions and signed pieces

Publication labels are grouped by newspaper. *With author* is the share of records with a named
author.

{{newspapers}}

### 4.1b Online editions and the blog label

{{online_editions}}

### 4.1c What the blog-labelled records are

{{blog_profile}}

### 4.2 Years

By decade of the publication year. The full yearly table is `reports/tables/raw_by_year.csv`.

{{decades}}

### 4.3 Document types and authorship

Top labels as exported. A record with two labels (for example `Commentary, Opinions`) counts
once under each. Editorials are mostly unsigned; commentary and op-eds are mostly signed.

{{doc_types}}

### 4.4 Sections

Top section labels as exported, grouped ignoring case. Each newspaper names its sections
differently.

{{sections}}

### 4.5 Language

{{languages}}

### 4.6 Missing values

{{missing}}

### 4.7 Publications outside the query

Publications not among the queried newspapers, most common first. Why the query returned
them: **[TBD]**.

{{other_publications}}

## 5. Known issues for users

- **Duplicates:** {{n_duplicate_rows}} records ({{dup_pct}}) repeat a ProQuest id already in the
  table; there are {{n_unique_ids}} distinct ids. {{n_ids_in_several_files}} ids appear in more
  than one file and {{n_repeats_inside_a_file}} repeat inside a single file, which points to
  overlapping download rounds. They are concentrated in the 2010s (4.2). Duplicate rows are kept.
- **Opinion and news are mixed:** the keyword query matches any article that mentions
  "opinion" or "editorial", and News is a queried document type. This table is not yet a set of
  opinion pieces.
- **Authors:** {{n_with_author}} records ({{with_author_pct}}) name an author. Unsigned pieces,
  mostly editorials, cannot be linked to a person.
- **No body text:** {{n_no_body}} records, all in {{n_no_body_files}} files.
- **Stray spaces:** ProQuest inserts spaces inside metadata values (`En glish`). Values are kept
  as exported; the `*_key` columns are the space-free versions to use for comparing categories.
- **Parsing:** rules and evidence are in `docs/decisions.md`; the parser is
  `econ_corpus/parse.py`.
