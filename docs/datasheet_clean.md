<!-- docs/datasheet_clean.md is generated from docs/datasheet_clean.template.md by
`make datasheet-clean`, which fills the double-brace names with numbers from the data. Change
the prose in the template, never in the generated file. -->

# A cleaned dataset of signed opinion articles in U.S. newspapers, 1980–2024

Data descriptor, version 1.0 (2026-11-08). Derived from the raw table described in
`docs/datasheet_raw.md`.

## Abstract

The dataset holds 402,361 opinion articles signed by at least one person, published
1980–2024 in ten U.S. newspapers with the highest circulation, and the
85,420 authors who signed them. Articles and authors are separate tables joined by a
link table, since an article can have several authors and an author many articles. The
dataset is derived from 1,377,766 rows parsed from ProQuest US Newsstream exports by a
sequence of exclusions, each row leaving for exactly one reason. Authors were read from the
bylines by explicit rules; name variants of one author were merged by a rule, and the doubtful
cases were decided in a manual review carried out by a large language model, which is
documented here.

## 1. Background and summary

The dataset supports the study of how economists communicate with the public through
newspaper opinion pieces. It keeps only what that study needs: opinion pieces, from the
queried newspapers, with text, signed by a person.

| | |
|---|---|
| Articles | 402,361 |
| Authors | 85,420 |
| Article–author links | 450,763 |
| Newspapers | 10 |
| Publication years | 1980–2024 |
| Articles with one author | 93.1% |
| Authors with one article | 50,516 (59.1%) |

## 2. Methods

### 2.1 Selection of articles

Every parsed row gets exactly one reason, so the counts add up. The first three exclusions
give the shared raw table; the others leave only the cleaned dataset (Figure 1).

![From the ProQuest exports to the cleaned dataset](../reports/figures/clean_flow.svg)

*Figure 1.* Exclusions from the rows parsed to the cleaned dataset.

| Step | Left out | Records | Remaining |
|---|---|---|---|
| Rows parsed |  |  | 1,377,766 |
| file_footer | Row is the footer of an export file, not an article | 2,801 | 1,374,965 |
| duplicate_id | Repeats a ProQuest id; the copy with the longest body is the one kept | 145,118 | 1,229,847 |
| duplicate_text | Same body, title, date and newspaper as another record, which stays | 2,991 | 1,226,856 |
| not_queried_newspaper | Publication is not one of the queried newspapers | 12,413 | 1,214,443 |
| missing_metadata | No publication, no id, or no document type and section: unclassifiable | 885 | 1,213,558 |
| not_opinion | A news section, and neither an opinion document type nor an opinion title | 125,240 | 1,088,318 |
| unclear_opinion | Generic document type, no section and no opinion title: may be opinion | 11,149 | 1,077,169 |
| no_text | Opinion piece with no text, or only a notice shared by several articles | 4,420 | 1,072,749 |
| no_author | Opinion piece that is unsigned or marked Anonymous | 659,275 | 413,474 |
| no_person_author | Byline names no person (an institution, or text with no full name) | 11,113 | 402,361 |

- **Opinion:** a record is opinion if its document type, its section or its title marks it
  as commentary, editorial, op-ed or letters. Records with no such mark are left out, either
  as news (`not_opinion`) or, when they have no section, as undecided (`unclear_opinion`).
- **Newspapers:** the ten queried newspapers, print and online editions.
- **Text and author:** an article needs body text and a byline that names at least one person.
  A body under 100 words carried by five or more different articles (a title on a date) is a
  notice or a credit ("text not available", a cartoon caption), not text (`no_text`). ProQuest's "Anonymous" and missing bylines are unsigned (`no_author`);
  a byline that names only an institution is `no_person_author`.

### 2.2 Reading the bylines

- `;` separates authors. A suffix standing alone joins the name before it, and a given name
  cut off from its family name is rejoined (`Lewis; , Flora`).
- A part is a person if it reads as `Family, Given[, Suffix]` or `Given Family`: two to five
  capitalised name words, no institution word, no digits. Titles and offices before the name
  (Dr., Sen., State Rep) and degrees after it (MD, PhD) are dropped. One word is never taken as
  a name.
- If a part does not read as a name, a full name at its start is recovered
  (`Jane Doe. Springfield`, `Jane Doe is a columnist`), a name after the end of a note about
  it too (`Committee., Jane Doe`), and co-authors that the export scrambled are put back
  (`Doe, Jane Roe and Ann` is Jane Roe and Ann Doe).
- Debris of the export is removed first: a label or `By` glued to the name
  (`Jane DoeGuest essay`, `ByJane Doe`), a period glued to the next word (`Jane Q.Doe`) and
  `and` that swallowed the start of a name (`andrew Roe` is `and Andrew Roe`).
- A note that someone did not write (`Jane Doe is on vacation.`) names nobody. A name
  followed by a small word that may be a piece of it cut off by a stray space
  (`Jane Do e Roe`) is not read: it goes to the manual review.
- Of 450,763 links, 430,402 (95.5%) were read as
  written, 15,357 were recovered and 5,004 come from the manual
  review (section 2.4). Each link records how it was read.

### 2.3 Deciding that two names are one author

- **Name key:** case, accents, periods, apostrophes, hyphens and spaces are ignored, so
  spelling variants and ProQuest's stray spaces give one key. Middle names and suffixes are
  kept.
- **Rule:** names with the same first and family name are one author when their middle names
  and suffixes do not contradict each other (one is missing, or one is the initial of the
  other, compared name by name) and they share at least one newspaper. One contradiction among such names stops
  every merge among them.
- **Result:** 89,162 name variants for 85,420 authors; 3,132 variants
  were merged by the rule and 610 by the manual review.
- **Not merged:** 5,468 pairs of look-alike authors are listed, not merged
  (section 3.5).

### 2.4 Manual review by a large language model

No person reviewed the cases. Each case was read and decided one by one by a large language
model (Claude, Anthropic), without web search, under written instructions: merge only with
supporting evidence, and answer "unsure" when in doubt. The evidence shown for an author was
its newspapers, its years and two headlines.

| Reviewed | Cases | Outcome |
|---|---|---|
| Byline parts (ambiguous, holding a place or publication word, long, read by moving pieces around, possibly damaged, or read as nobody) | 7,237 | 3,102 corrected, 3,387 not a person, 660 kept as read, 88 unsure |
| Pairs of look-alike authors with two or more articles each | 1,607 | 638 same person, 588 different, 381 unsure |

- **Models:** most cases were decided by Claude Sonnet run as subagents; the rest, and the
  checks, by Claude Fable 5.1. The reviewer of every decision is recorded in the review files.
- **Checks:** random samples of the decisions of rounds 1, 3 and 4 (about 235) were read
  again by a second model, which rewrote two suffixes and changed no decision; an independent
  audit of the output then found credits of interviewers, illustrators and photographers
  taken as authors, and 31 corrections were changed. In round 5 the second model read every
  answer other than "not a person" (294) and changed four. The set was checked for
  contradictions. The rounds are described in the README of the review files.
- **Evidence for damaged names:** a name with a lone small letter (`Doe, Jan e`) was
  corrected from the spelling of the same name in other bylines, when there was one.
- **How decisions are applied:** they are data read by the pipeline, never edits to the
  rules. A corrected byline and a merge by review are marked `manual_review`. A pair judged
  different is never merged by the rule. A pair judged unsure is left to the rule: it stays
  apart, with its verdict in the list of look-alike pairs, unless the rule later merges it.
- **Limit:** a language model can be wrong, above all for authors it knows nothing about.
  The decisions and their reasons are delivered with the dataset so they can be audited.

## 3. Data records

Five CSV files (UTF-8, comma-separated). The article text is ProQuest-licensed: the dataset
is for internal use among the project's researchers.

### 3.1 `articles.csv`

One row per article, keyed by `doc_id` (the ProQuest id). It has every column of the raw table
(see its datasheet) except `is_footer`, plus:

| Column | Type | Content |
|---|---|---|
| `newspaper` | string | One of the ten newspapers, the same for its print and online editions |
| `edition` | string | `print`, `online` or `pre-1997` (ProQuest's label for older records) |

`author` keeps the byline as exported; the authors read from it are in the tables below.

### 3.2 `authors.csv`

| Column | Type | Content |
|---|---|---|
| `author_id` | integer | Key, numbered in the order of the name keys |
| `name` | string | Commonest spelling of the author's main name variant, given name first |
| `articles` | integer | Articles signed |
| `name_variants` | integer | Name variants merged into this author |

### 3.3 `author_names.csv`

| Column | Type | Content |
|---|---|---|
| `author_id` | integer | Author the variant belongs to |
| `name` | string | The variant, given name first |
| `name_key` | string | Its key (section 2.3) |
| `articles` | integer | Articles in which the variant appears |
| `rule` | string | `main` (the variant that names the author), `shared_newspaper` (merged by the rule) or `manual_review` |

### 3.4 `article_authors.csv`

The many-to-many link.

| Column | Type | Content |
|---|---|---|
| `doc_id` | integer | Article |
| `author_id` | integer | Author |
| `position` | integer | Order in the byline, from 1 |
| `read` | string | `as_written`, `recovered` or `manual_review` (section 2.2) |

### 3.5 `author_candidates.csv`

Pairs of authors that look alike and are not merged.

| Column | Type | Content |
|---|---|---|
| `author_id_a`, `name_a`, `articles_a` | | First author of the pair |
| `author_id_b`, `name_b`, `articles_b` | | Second author |
| `kind` | string | `no_shared_newspaper` (compatible names never in the same newspaper), `conflicting_names` (middle names or suffixes contradict within the group), `one_letter_apart` (keys one letter apart in the same newspaper), `nickname` (first names that are short forms of each other, in the same newspaper), `swapped_names` (given and family name the other way round) or `apart_by_review` |
| `review` | string | `different`, `unsure` or `not_reviewed`. A verdict on a pair that no rule lists any more is kept in the review files only |

## 4. Contents

### 4.1 Newspapers

| Newspaper | Articles | Print | Online | Pre-1997 | Share |
|---|---|---|---|---|---|
| Washington Post | 108,653 | 50,106 | 47,720 | 10,827 | 27.0% |
| New York Times | 94,000 | 64,199 | 29,801 | 0 | 23.4% |
| Los Angeles Times | 58,730 | 33,150 | 10,114 | 15,466 | 14.6% |
| Boston Globe | 41,319 | 23,365 | 5,789 | 12,165 | 10.3% |
| Wall Street Journal | 38,217 | 1,963 | 36,254 | 0 | 9.5% |
| Chicago Tribune | 20,358 | 4,331 | 12,551 | 3,476 | 5.1% |
| Newsday | 20,021 | 20,021 | 0 | 0 | 5.0% |
| USA Today | 19,177 | 2,891 | 16,286 | 0 | 4.8% |
| Tampa Bay Times | 1,526 | 98 | 1,428 | 0 | 0.4% |
| Star Tribune | 360 | 360 | 0 | 0 | 0.1% |
| Total | 402,361 | 200,484 | 159,943 | 41,934 | 100.0% |

### 4.2 Decades

| Decade | Articles | Share |
|---|---|---|
| 1980s | 28,064 | 7.0% |
| 1990s | 48,531 | 12.1% |
| 2000s | 74,646 | 18.6% |
| 2010s | 134,661 | 33.5% |
| 2020s | 116,444 | 28.9% |
| Unknown year | 15 | 0.0% |

### 4.3 Authors per article

| Authors | Articles | Share |
|---|---|---|
| 1 | 374,639 | 93.1% |
| 2 | 19,906 | 4.9% |
| 3 | 2,989 | 0.7% |
| 4 | 1,703 | 0.4% |
| 5 or more | 3,124 | 0.8% |

### 4.4 Articles per author

| Articles | Authors | Share |
|---|---|---|
| 1 | 50,516 | 59.1% |
| 2 to 9 | 30,175 | 35.3% |
| 10 to 99 | 4,320 | 5.1% |
| 100 or more | 409 | 0.5% |

### 4.5 Most frequent authors

| Author | Articles |
|---|---|
| Jennifer Rubin | 5,067 |
| George F Will | 3,877 |
| Paul Krugman | 3,514 |
| EJ Dionne Jr | 3,078 |
| David Ignatius | 2,736 |
| Ellen Goodman | 2,569 |
| Thomas L Friedman | 2,366 |
| Jeff Jacoby | 2,354 |
| Nicholas Kristof | 2,353 |
| James Freeman | 2,303 |
| Maureen Dowd | 2,303 |
| Richard Cohen | 2,273 |
| David S Broder | 2,227 |
| Paul Waldman | 2,153 |
| Joan Vennochi | 2,147 |

### 4.6 How the names were read

| Read | Count | Share |
|---|---|---|
| as_written | 430,402 | 95.5% |
| recovered | 15,357 | 3.4% |
| manual_review | 5,004 | 1.1% |

## 5. Technical validation

- **Keys:** every article has its own ProQuest id; every link points to an article and an
  author that exist; every article has at least one author. The build stops otherwise.
- **Reasons:** they are matched to the records by file and position in the file, and the
  counts per reason add up to the rows parsed. The reasons carry a fingerprint of the columns
  they were decided from, so reasons computed before a new parse are refused.
- **Review:** a review file with a repeated case, an unknown verdict or an unreadable
  correction stops the build, and so does a pair judged different that ends up merged. The
  reasons carry a fingerprint of the corrections they were computed with, and the tables carry
  the fingerprints of the reasons and of both review files (`manifest.json`); this document
  and the lists of cases refuse tables built from other inputs.
- **Look-alike authors left apart** (kind / review):

| Kind / review | Count | Share |
|---|---|---|
| conflicting_names / not_reviewed | 1,686 | 30.8% |
| no_shared_newspaper / not_reviewed | 1,219 | 22.3% |
| nickname / not_reviewed | 884 | 16.2% |
| one_letter_apart / not_reviewed | 794 | 14.5% |
| conflicting_names / different | 228 | 4.2% |
| conflicting_names / unsure | 170 | 3.1% |
| one_letter_apart / different | 142 | 2.6% |
| nickname / different | 91 | 1.7% |
| nickname / unsure | 87 | 1.6% |
| no_shared_newspaper / unsure | 74 | 1.4% |
| no_shared_newspaper / different | 38 | 0.7% |
| one_letter_apart / unsure | 24 | 0.4% |
| swapped_names / not_reviewed | 19 | 0.3% |
| apart_by_review / different | 5 | 0.1% |
| apart_by_review / not_reviewed | 3 | 0.1% |
| swapped_names / different | 2 | 0.0% |
| swapped_names / unsure | 2 | 0.0% |

## 6. Usage notes and limitations

- **Unsigned opinion is absent:** 659,275 opinion pieces have no author, mostly
  editorials. They are in the raw table.
- **Bylines that name nobody:** 11,113 articles, signed by an editorial
  board, a publication or a role.
- **Authors may still be split:** of the 5,468 look-alike pairs,
  4,605 were not reviewed, most because one of the two authors has a
  single article. 357 were reviewed and left unsure.
- **Authors may be wrongly merged:** the rule needs a shared newspaper and compatible names,
  which two people with a common name can meet.
- **Readers' letters:** letters to the editor count as opinion, so many authors with one
  article are readers.
- **One word is never a name:** pen names of one word and bylines cut to one word are lost.
- **Subtler duplicates** (reprints, edited versions under another title, the print and
  online editions of one article under different titles or dates) are not detected.
- **Language:** a small share of the articles (about 0.4%, estimated once from the text) is
  in Spanish, mostly from online editions, although ProQuest labels them English.
- **Cartoons and very short items** signed by a person are kept when their body is not a
  notice shared by several articles.
- **Opinion is taken from ProQuest's labels:** a few arts reviews and news analyses filed
  under an opinion label are in, and opinion columns filed under a news section are out.

## 7. Code availability

The pipeline is in the private repository `econ_corpus` [1]: `exclusions` and `reasons`
(selection), `authors` and `bylines` (reading names), `identity` (one author), `review` and
`review_cases` (manual review), `processed` (tables) and `datasheet_clean` (this document).
Every rule and its evidence are in `docs/decisions.md`. `README.md` lists the commands, from
`make parse` on, that regenerate the dataset and this document.

## 8. References

[1] J. C. Reyes, "econ_corpus: build and audit a corpus of U.S. newspaper opinion articles,"
GitHub repository, 2026. Accessed: Nov. 8, 2026. [Online]. Available:
https://github.com/JuanReyes01/econ_corpus
