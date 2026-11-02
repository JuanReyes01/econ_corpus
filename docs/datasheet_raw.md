<!-- Prose template. `econ_corpus.datasheet` fills the double-brace names with numbers from the
data and writes docs/datasheet_raw.md. Edit the prose here, never the generated file. -->

# Datasheet: raw table of U.S. newspaper opinion articles (ProQuest)

Draft. Items marked **[TBD]** still need an answer from the data collector.

## 1. What this is

One row per record exported from ProQuest: **1,374,965 records** from **2,801 export
files**, publication years **1980–2024**. The table is the exports reorganised, not
cleaned: nothing is dropped, and values that could not be parsed are flagged. It keeps the
parsed metadata, where each record came from (`source_file`, `record_index`), and a SHA-256 hash,
word count and character count of the body. The article text itself is ProQuest-licensed and
is not in the table.

## 2. Where it comes from

- **Source:** ProQuest US Newsstream, through the Universidad de los Andes library proxy.
- **When:** exports dated 2024-11-22 to 2025-01-26 (from the file names).
- **Query (as documented by the collector):** exact publication name for 10 newspapers, AND
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
| Newspapers | Yes, but 282 publications outside the list also appear. Queried newspapers with no records: none | 4.1, 4.7 |
| Source type | Not newspapers only, by design: 421,849 records (30.7%) are online editions that ProQuest labels `Blog, podcast o sitio web` | 4.1, 4.1b, 4.1c |
| Document type | Labels vary widely (515 distinct). 448,205 records (32.6%) carry none of Commentary, Editorial or News | 4.3 |
| English | Yes, 99.8% are English only; the rest are bilingual or unlabelled | 4.5 |
| Dates | Yes, 1980–2024 | 4.2 |

What the blog label means here:

- 99.9% of the blog-labelled records are `(Online)` editions. Most come from
  New York Times, Washington Post, Los Angeles Times, Chicago Tribune, Tampa Bay Times (columns *Online* and *Blog/podcast/website* in 4.1).
- The label belongs to the publication edition, not to the article or the date. For each
  newspaper, either all of its online records carry it or none do, in every year (4.1b, last
  column). The share changes over time only because online editions start in different years
  (4.2).
- They are mostly opinion content, not casual blog posts: 95.2% sit in an
  opinion or editorial section (4.1c).
- The source is best read as a database of news opinion pieces, news articles and news
  organisations' websites, not of newspapers in print only.

## 4. What is in it

### 4.1 Newspapers, editions and signed pieces

Publication labels are grouped by newspaper. *With author* is the share of records with a named
author.

| Newspaper | Records | Print | Online | Pre-1997 | Blog/podcast/website | With author |
|---|---|---|---|---|---|---|
| New York Times | 436,859 | 164,497 | 272,362 | 0 | 272,362 | 32.7% |
| Washington Post | 309,813 | 149,105 | 106,335 | 54,373 | 106,335 | 48.7% |
| Wall Street Journal | 146,419 | 50,625 | 95,794 | 0 | 0 | 70.8% |
| Los Angeles Times | 156,233 | 89,677 | 15,892 | 50,664 | 15,892 | 55.4% |
| Boston Globe | 111,489 | 62,342 | 9,150 | 39,997 | 0 | 56.1% |
| Chicago Tribune | 77,800 | 29,326 | 23,297 | 25,177 | 23,297 | 49.8% |
| USA Today | 39,370 | 14,529 | 20,377 | 4,464 | 0 | 73.5% |
| Newsday | 57,368 | 57,368 | 0 | 0 | 0 | 62.8% |
| Tampa Bay Times | 15,992 | 12,904 | 3,088 | 0 | 3,088 | 22.4% |
| Star Tribune | 7,722 | 7,722 | 0 | 0 | 0 | 76.6% |
| Other | 13,984 | 13,414 | 556 | 14 | 863 | 55.2% |
| No metadata | 1,916 | 0 | 0 | 0 | 12 | 0.0% |
| Total | 1,374,965 | 651,509 | 546,851 | 174,689 | 421,849 | 48.5% |

### 4.1b Online editions and the blog label

| Newspaper | Online records | First year | Labelled blog/podcast/website | Years with both labels |
|---|---|---|---|---|
| New York Times | 272,362 | 1996 | 100.0% | 0 |
| Washington Post | 106,335 | 2011 | 100.0% | 0 |
| Wall Street Journal | 95,794 | 2010 | 0.0% | 0 |
| Los Angeles Times | 15,892 | 2017 | 100.0% | 0 |
| Boston Globe | 9,150 | 2006 | 0.0% | 0 |
| Chicago Tribune | 23,297 | 2017 | 100.0% | 0 |
| USA Today | 20,377 | 2014 | 0.0% | 0 |
| Tampa Bay Times | 3,088 | 2017 | 100.0% | 0 |

### 4.1c What the blog-labelled records are

| Document type | Blog-labelled records | Share of blog-labelled |
|---|---|---|
| News | 200,060 | 47.4% |
| Opinions | 166,684 | 39.5% |
| Editorial | 57,665 | 13.7% |
| Commentary | 56,465 | 13.4% |
| Letter To The Editor | 253 | 0.1% |
| New s | 122 | 0.0% |

### 4.2 Years

By decade of the publication year. The full yearly table is `reports/tables/raw_by_year.csv`.

| Decade | Records | Unique ids | With author |
|---|---|---|---|
| 1980s | 127,871 | 119,082 | 46.9% |
| 1990s | 217,596 | 205,523 | 40.8% |
| 2000s | 368,954 | 350,967 | 36.3% |
| 2010s | 475,704 | 377,600 | 53.4% |
| 2020s | 183,087 | 174,958 | 71.4% |
| Unknown year | 1,753 | 835 | 0.0% |

### 4.3 Document types and authorship

Top labels as exported. A record with two labels (for example `Commentary, Opinions`) counts
once under each. Editorials are mostly unsigned; commentary and op-eds are mostly signed.

| Document type | Records | With author |
|---|---|---|
| News | 376,090 | 45.9% |
| Editorial | 315,679 | 24.2% |
| NEWSPAPER | 283,251 | 44.6% |
| Opinions | 266,083 | 54.4% |
| Commentary | 234,968 | 88.7% |
| Op-Ed | 9,762 | 94.9% |
| OP-ED | 6,423 | 94.5% |
| EDITORIAL | 5,984 | 1.6% |
| Opinion | 5,356 | 87.2% |
| Letter To The Editor | 2,856 | 0.1% |
| editorial | 2,621 | 1.8% |
| Opinion Piece | 2,392 | 98.3% |

### 4.4 Sections

Top section labels as exported, grouped ignoring case. Each newspaper names its sections
differently.

| Section | Records | Share |
|---|---|---|
| opinion | 441,604 | 32.1% |
| a | 120,076 | 8.7% |
| editorial | 118,919 | 8.6% |
| editorial-opinion | 85,535 | 6.2% |
| opinions | 55,016 | 4.0% |
| op/ed | 39,623 | 2.9% |
| news | 36,492 | 2.7% |
| editorial - opinion | 35,412 | 2.6% |
| editorial page | 24,239 | 1.8% |
| op-ed | 18,742 | 1.4% |
| california metro; part b; editorial pages desk | 17,261 | 1.3% |
| main news; part a; editorial desk | 14,749 | 1.1% |

### 4.5 Language

| Language | Records | Share |
|---|---|---|
| English only | 1,371,935 | 99.8% |
| Missing | 1,731 | 0.1% |
| Includes Spanish | 1,299 | 0.1% |

### 4.6 Missing values

| Field | Missing | Share |
|---|---|---|
| Title | 1,916 | 0.1% |
| Author | 707,543 | 51.5% |
| Section | 54,462 | 4.0% |
| Full publication date | 27,238 | 2.0% |
| Document id | 882 | 0.1% |
| Body text | 2,500 | 0.2% |

### 4.7 Publications outside the query

Publications not among the queried newspapers, most common first. Why the query returned
them: **[TBD]**.

| Publication | Records |
|---|---|
| Washington Examiner; Washington, D.C. | 1,706 |
| La Opinión; Los Angeles, Calif. | 1,283 |
| Philadelphia Daily News; Philadelphia, Pa. | 414 |
| The Press Democrat; Santa Rosa, Calif. | 399 |
| South Florida Sun - Sentinel; Fort Lauderdale, Fla. | 330 |
| Pittsburgh Post - Gazette; Pittsburgh, Pa. | 259 |
| Politico, U.S. edition; Arlington | 240 |
| Orlando Sentinel (Online); Orlando | 200 |
| Public Opinion; Chambersburg, Pa. | 196 |
| Daily News; Los Angeles, Calif. | 191 |
| Reno Gazette - Journal; Reno, Nev. | 175 |
| York Daily Record; York, Pa. | 166 |

## 5. Known issues for users

- **Duplicates:** 145,118 records (10.6%) repeat a ProQuest id already in the
  table; there are 1,228,965 distinct ids. 100,661 ids appear in more
  than one file and 0 repeat inside a single file, which points to
  overlapping download rounds. They are concentrated in the 2010s (4.2). Duplicate rows are kept.
- **Opinion and news are mixed:** the keyword query matches any article that mentions
  "opinion" or "editorial", and News is a queried document type. This table is not yet a set of
  opinion pieces.
- **Authors:** 667,422 records (48.5%) name an author. Unsigned pieces,
  mostly editorials, cannot be linked to a person.
- **No body text:** 2,500 records, all in 5 files.
- **Stray spaces:** ProQuest inserts spaces inside metadata values (`En glish`). Values are kept
  as exported; the `*_key` columns are the space-free versions to use for comparing categories.
- **Parsing:** rules and evidence are in `docs/decisions.md`; the parser is
  `econ_corpus/parse.py`.
