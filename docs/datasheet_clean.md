<!-- docs/datasheet_clean.md is generated from docs/datasheet_clean.template.md by
`make datasheet-clean`, which fills the double-brace names with numbers from the data. Change
the prose in the template, never in the generated file. -->

# A cleaned dataset of signed opinion articles in U.S. newspapers, 1980–2024

Data descriptor, version 1.0 (2026-11-09). Derived from the raw table described in
`docs/datasheet_raw.md`.

## Abstract

The dataset holds 399,248 opinion articles signed by at least one person, published
1980–2024 in ten U.S. newspapers with the highest circulation, and the
86,611 authors who signed them. Articles and authors are separate tables joined by a
link table, since an article can have several authors and an author many articles. The
dataset is derived from 1,377,766 rows parsed from ProQuest US Newsstream exports by a
sequence of exclusions, each row leaving for exactly one reason. Authors were read from the
bylines by explicit rules; name variants of one author were merged by a rule, and the doubtful
cases were decided in a manual review carried out by a large language model, which is
documented here.

## 1. Background and summary

The dataset supports the study of how economists communicate with the public through
newspaper opinion pieces. It keeps only what that study needs: opinion pieces, from the
queried newspapers, with an English text of at least 50 words, signed by a person.

| | |
|---|---|
| Articles | 399,248 |
| Authors | 86,611 |
| Article–author links | 447,631 |
| Newspapers | 10 |
| Publication years | 1980–2024 |
| Articles with one author | 93.1% |
| Authors with one article | 51,604 (59.6%) |

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
| duplicate_text | Same text in the same newspaper as another record, which stays | 37,325 | 1,192,522 |
| not_queried_newspaper | Publication is not one of the queried newspapers | 12,413 | 1,180,109 |
| missing_metadata | No publication, no id, or no document type and section: unclassifiable | 885 | 1,179,224 |
| not_opinion | A news section, and neither an opinion document type nor an opinion title | 118,978 | 1,060,246 |
| unclear_opinion | Generic document type, no section and no opinion title: may be opinion | 11,079 | 1,049,167 |
| no_text | Opinion piece with no text, or only a notice shared by several articles | 4,420 | 1,044,747 |
| no_author | Opinion piece that is unsigned or marked Anonymous | 631,192 | 413,555 |
| no_person_author | Byline names no person (an institution, or text with no full name) | 10,917 | 402,638 |
| short_or_cartoon | Signed opinion piece under 50 words or under a cartoon heading | 1,873 | 400,765 |
| not_english | Signed opinion piece whose text is not in English (mostly Spanish) | 1,517 | 399,248 |

- **Opinion:** a record is opinion if its document type, its section or its title marks it
  as commentary, editorial, op-ed or letters. Records with no such mark are left out, either
  as news (`not_opinion`) or, when they have no section, as undecided (`unclear_opinion`).
- **Newspapers:** the ten queried newspapers, print and online editions.
- **One text, one article:** a text found under several ids in one newspaper (print and
  online editions under another title or date, texts posted again) is kept once
  (`duplicate_text`): the signed copy published first. A body under 100 words is a repeat
  only under the same title and date.
- **Text and author:** an article needs body text and a byline that names at least one person.
  A body under 100 words carried by five or more different articles (a title on a date) is a
  notice or a credit ("text not available", a cartoon caption), not text (`no_text`). ProQuest's "Anonymous" and missing bylines are unsigned (`no_author`);
  a byline that names only an institution is `no_person_author`.
- **A text to read:** a signed opinion piece with a body under 50 words (a cartoon stored
  as its caption, a teaser, a cut text) or with a title that starts with a cartoon heading
  (`TOON-OP`, `Op-Comic`) is left out (`short_or_cartoon`).
- **English:** ProQuest labels every article English, but some online editions carry
  translations. A text is not English (`not_english`) when fewer than 5% of the words in
  its first 2,000 characters are among 39 common English words (`the`, `of`, `and` ...);
  in English prose they are a fifth to a third. Most of these texts are in Spanish; the
  rest are in Portuguese, French, Turkish, Arabic, Persian, Russian and other languages.

### 2.2 Reading the bylines

- `;` separates authors. A suffix standing alone joins the name before it, and a given name
  cut off from its family name is rejoined (`Lewis; , Flora`).
- A part is a person if it reads as `Given Family` (two to five capitalised name words, none
  of them an institution word) or as `Family, Given[, Suffix]` (up to three words before the
  comma and four after it, the first given word capitalised; one word before the comma may
  be an institution word that is also a family name, as in `Press, Jane`). No digits. Titles
  and offices before the name (Dr., Sen., State Rep) and degrees after it (MD, PhD) are
  dropped. One word is never taken as a name.
- A list of names is read whole, with or without an affiliation after it (`Jane Doe and
  Richard Roe, Example Staff`; `Jane Doe, Richard Roe, and Ann Poe`), and so are the names
  around the note of an editorial-board item, one sentence each or as a list (`Jane Doe.
  Richard Roe. Written by members of the editorial board.`).
- If a part does not read as a name, a full name at its start is recovered
  (`Jane Doe. Springfield`, `Jane Doe is a columnist`), and co-authors that the export
  scrambled are put back (`Doe, Jane Roe and Ann` is Jane Roe and Ann Doe).
- The export moves the last word of a byline to its front: `Jane Doe; Ann Roe is on
  vacation.` comes out as `vacation., Jane Doe; Ann Roe is on`. The name after the moved word
  is read as an author (`Committee., Jane Doe`), and the note cut short after it is not.
- Debris of the export is removed first: a label or `By` glued to the name
  (`Jane DoeGuest essay`, `ByJane Doe`), a period glued to the next word (`Jane Q.Doe`) and
  `and` that swallowed the start of a name (`andrew Roe` is `and Andrew Roe`).
- A note after the byline that repeats the author (`Doe, Jane; Jane Q. Doe lives in ...`)
  adds no second author when its name is the earlier one with a letter of difference, a
  shorter or longer form of it, or the same words in another order. The earlier reading
  stands, except when the earlier part had a town where the family name goes
  (`Springfield, Jane Doe`) or the two names the wrong way round: then the name of the
  note is the one kept. Two names with different suffixes (`Sr`, `Jr`) are two people.
- A note that someone did not write (`Jane Doe is on vacation.`, `Jane Doe contributed
  reporting`) names nobody. `and` separates authors only after a name, not inside a sentence
  about the first author, and a `Family, Given` piece after an unfinished sentence about an
  author is a piece of that sentence. A name followed by a small word that may be a piece
  of it cut off by a stray space (`Jane Do e Roe`, `Jane Do rgan`) is not read: it goes
  to the manual review.
- Of 447,631 links, 426,091 (95.2%) were read as
  written, 16,404 were recovered and 5,136 come from the manual
  review (section 2.4). Each link records how it was read.

### 2.3 Deciding that two names are one author

- **Name key:** case, accents, periods, apostrophes, hyphens and spaces are ignored, so
  spelling variants and ProQuest's stray spaces give one key. Middle names and suffixes are
  kept.
- **Same key, one author:** every byline with the same name key is one author, in any
  newspaper and any year. Two people with exactly the same name are therefore one author
  (section 6).
- **Rule for variants:** names with the same first and family name are one author when their
  middle names and suffixes do not contradict each other (one is missing, or one is the
  initial of the other, compared name by name) and they are linked through shared newspapers
  (two variants can be joined by a third that shares a newspaper with each). One
  contradiction among such names stops every merge among them.
- **Result:** 90,705 name variants for 86,611 authors; 3,205 variants
  were merged by the rule and 889 by the manual review.
- **Not merged:** 7,165 pairs of look-alike authors are listed, not merged
  (section 3.5).

### 2.4 Manual review by a large language model

No person reviewed the cases. Each case was read and decided one by one by a large language
model (Claude, Anthropic), without web search, under written instructions: merge only with
supporting evidence, and answer "unsure" when in doubt. The evidence shown for an author was
its newspapers, its years and two headlines.

| Reviewed | Cases | Outcome |
|---|---|---|
| Byline parts (ambiguous, holding a place or publication word, long, read by moving pieces around, possibly damaged, or read as nobody) | 7,214 | 3,349 corrected, 3,010 not a person, 766 kept as read, 89 unsure |
| Pairs of look-alike authors with two or more articles each, or with one author of twenty or more | 2,370 | 889 same person, 926 different, 555 unsure |

- **Models:** most cases were decided by Claude Sonnet run as subagents; the rest, and the
  checks, by Claude Fable 5.1. The reviewer of every decision is recorded in the review files.
- **Checks:** random samples of the decisions of rounds 1, 3 and 4 (about 235) were read
  again by a second model, which rewrote two suffixes and changed no decision; an independent
  audit of the output then found credits of interviewers, illustrators and photographers
  taken as authors, and 31 corrections were changed. In round 5 the second model read every
  answer other than "not a person" (296) and changed four; the third audit showed that two
  of those four changes were wrong, and they were undone. In round 6 it read the 200 answers
  on byline parts and a sample of 60 merges, and changed one. A fourth audit then read
  samples of the decisions of round 6 (140 on parts, 240 on pairs); two corrections and six
  pair verdicts were changed after it. A fifth audit read the 90 parts and 12 pair verdicts
  of round 7 and found none wrong, and a sixth audit read 109 decisions of round 8 and found
  none clearly wrong.
- **Retired decisions:** a decision that applies to no byline any more, because the rules
  that split bylines changed, is taken out of the review files and kept apart; the counts
  above are of the decisions in force. The set was checked for
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
| `kind` | string | `no_shared_newspaper` (compatible names never in the same newspaper), `conflicting_names` (middle names or suffixes contradict within the group), `one_letter_apart` (keys one letter apart in the same newspaper), `nickname` (given names that are a short form or the initials of each other, in any newspaper), `swapped_names` (given and family name the other way round) or `apart_by_review` |
| `review` | string | `different`, `unsure` or `not_reviewed`. A verdict on a pair that no rule lists any more is kept in the review files only |

## 4. Contents

### 4.1 Newspapers

| Newspaper | Articles | Print | Online | Pre-1997 | Share |
|---|---|---|---|---|---|
| Washington Post | 105,347 | 49,865 | 44,584 | 10,898 | 26.4% |
| New York Times | 96,315 | 66,728 | 29,587 | 0 | 24.1% |
| Los Angeles Times | 58,103 | 32,787 | 9,855 | 15,461 | 14.6% |
| Boston Globe | 41,199 | 23,314 | 5,721 | 12,164 | 10.3% |
| Wall Street Journal | 37,400 | 1,943 | 35,457 | 0 | 9.4% |
| Newsday | 20,649 | 20,649 | 0 | 0 | 5.2% |
| Chicago Tribune | 19,524 | 4,250 | 11,812 | 3,462 | 4.9% |
| USA Today | 18,710 | 2,889 | 15,818 | 3 | 4.7% |
| Tampa Bay Times | 1,525 | 98 | 1,427 | 0 | 0.4% |
| Star Tribune | 476 | 476 | 0 | 0 | 0.1% |
| Total | 399,248 | 202,999 | 154,261 | 41,988 | 100.0% |

### 4.2 Decades

| Decade | Articles | Share |
|---|---|---|
| 1980s | 30,877 | 7.7% |
| 1990s | 49,003 | 12.3% |
| 2000s | 74,513 | 18.7% |
| 2010s | 131,011 | 32.8% |
| 2020s | 113,829 | 28.5% |
| Unknown year | 15 | 0.0% |

### 4.3 Authors per article

| Authors | Articles | Share |
|---|---|---|
| 1 | 371,836 | 93.1% |
| 2 | 19,524 | 4.9% |
| 3 | 2,967 | 0.7% |
| 4 | 1,729 | 0.4% |
| 5 or more | 3,192 | 0.8% |

### 4.4 Articles per author

| Articles | Authors | Share |
|---|---|---|
| 1 | 51,604 | 59.6% |
| 2 to 9 | 30,319 | 35.0% |
| 10 to 99 | 4,283 | 4.9% |
| 100 or more | 405 | 0.5% |

### 4.5 Most frequent authors

| Author | Articles |
|---|---|
| Jennifer Rubin | 5,048 |
| George F Will | 3,874 |
| Paul Krugman | 3,514 |
| EJ Dionne Jr | 3,060 |
| David Ignatius | 2,690 |
| Ellen Goodman | 2,563 |
| Nicholas Kristof | 2,368 |
| Thomas L Friedman | 2,366 |
| Jeff Jacoby | 2,351 |
| Maureen Dowd | 2,301 |
| James Freeman | 2,292 |
| Richard Cohen | 2,272 |
| David S Broder | 2,225 |
| Joan Vennochi | 2,144 |
| Paul Waldman | 2,135 |

### 4.6 How the names were read

| Read | Count | Share |
|---|---|---|
| as_written | 426,091 | 95.2% |
| recovered | 16,404 | 3.7% |
| manual_review | 5,136 | 1.1% |

## 5. Technical validation

- **Keys:** every article has its own ProQuest id and at least one author; the build stops
  otherwise. Every link points to an article and an author that exist, by construction: the
  three tables are written from one reading of the bylines.
- **Reasons:** they are matched to the records by file and position in the file, and the
  counts per reason add up to the rows parsed. The reasons carry a fingerprint of the columns
  they were decided from and of the code, so reasons computed before a new parse or a change
  of the rules are refused.
- **Review:** a review file with a repeated case, an unknown verdict or an unreadable
  correction stops the build, and so does a pair judged different that ends up merged. The
  reasons carry a fingerprint of the corrections they were computed with, and the tables carry
  the fingerprints of the reasons, of both review files, of the code and of every table
  (`manifest.json`); this document and the lists of cases refuse tables built
  from other inputs or cut short.
- **Delivery:** before the files are copied, the raw table, the cleaned tables and both
  datasheets are checked against the current records, reasons and review, and the datasheets
  are built again and compared.
- **Look-alike authors left apart** (kind / review):

| Kind / review | Count | Share |
|---|---|---|
| nickname / not_reviewed | 2,202 | 30.7% |
| conflicting_names / not_reviewed | 1,656 | 23.1% |
| no_shared_newspaper / not_reviewed | 1,213 | 16.9% |
| one_letter_apart / not_reviewed | 699 | 9.8% |
| nickname / different | 303 | 4.2% |
| conflicting_names / different | 297 | 4.1% |
| nickname / unsure | 212 | 3.0% |
| conflicting_names / unsure | 192 | 2.7% |
| one_letter_apart / different | 187 | 2.6% |
| no_shared_newspaper / unsure | 82 | 1.1% |
| no_shared_newspaper / different | 50 | 0.7% |
| one_letter_apart / unsure | 42 | 0.6% |
| swapped_names / not_reviewed | 18 | 0.3% |
| apart_by_review / different | 5 | 0.1% |
| apart_by_review / not_reviewed | 3 | 0.0% |
| swapped_names / different | 2 | 0.0% |
| swapped_names / unsure | 2 | 0.0% |

## 6. Usage notes and limitations

- **Unsigned opinion is absent:** 631,192 opinion pieces have no author, mostly
  editorials. They are in the raw table.
- **Bylines that name nobody:** 10,917 articles, signed by an editorial
  board, a publication or a role.
- **Authors may still be split:** of the 7,165 look-alike pairs,
  5,791 were not reviewed: one of the two authors has a single
  article and the other fewer than twenty. 530 were reviewed and left unsure.
- **Authors may be wrongly merged:** the rule needs a shared newspaper and compatible names,
  which two people with a common name can meet, across decades too (a father and a son, one
  written with `Jr`; a writer of the 1990s and a historian of the 2020s). In an audit of 100
  authors with two or more name variants, seven to nine held more than one person.
- **People with the same name are one author:** nothing tells two people apart when their
  names are written alike (a senator and a letter writer). In the audit this touched about
  1% of the authors of a random sample and about 3% of those with ten or more articles,
  usually one to three articles each.
- **Residual errors in reading:** four audits by a language model each judged a fresh
  random sample of 300 authors against their bylines and found five (1.7%), two (0.7%), one
  (0.3%) and none wrong, each drawn before the corrections that followed it. Among authors
  with ten or more articles the last three audits found no reading error in 150; among
  authors read by recovery or by the review, two in 150. The last audit still found by
  targeted search 57 names that are not a person (institutions and roles after a name in a
  byline) and about 15 damaged names, most with one article, corrected since; others of
  the kind remain.
- **Co-authors in lists:** a list of names that the rules cannot read whole gives its first
  name only. The last audit estimated 150 to 250 articles with a missing co-author before
  the rules for lists were widened; lists in other forms remain.
- **Credits of podcasts and videos:** the people credited under a transcript (producers,
  editors, a photographer) are read as authors when they are written like one.
- **Readers' letters:** letters to the editor count as opinion, so many authors with one
  article are readers.
- **One word is never a name:** pen names of one word and bylines cut to one word are lost.
- **The name key ignores spaces**, because the export puts stray spaces inside names: `Jane
  C Hu` and `Jane Chu` are one author. An audit found four such pairs.
- **Subtler duplicates** are not detected: edited versions of one article, whose text
  differs, and the same text in two newspapers.
- **One text, one article:** records of different articles that carry the same text are
  one article. Known case: 32 instalments of a weekly poll column of the Chicago Tribune,
  stored only as their fixed introduction.
- **Language:** the rule reads only the start of a text and counts English words, so a
  text that mixes languages can fall on either side. A listing of the cases near the limit
  found three texts in Spanish with English passages that stay and two English captions
  left out.
- **Cartoons** have no label in ProQuest. They are left out when stored as a caption under
  50 words or under a cartoon heading; a cartoon with a longer caption and no heading
  stays.
- **Opinion is taken from ProQuest's labels:** a few arts reviews and news analyses filed
  under an opinion label are in, and opinion columns filed under a news section are out.
  Signed pieces of the opinion pages of USA Today of 1991 to 2012 whose only mark is in
  the first line of the text ("THE EDITORIAL PAGE", about 300) are out: the selection
  reads the labels and the title, not the text. Records with no section and a generic
  document type are left out as undecided
  (`unclear_opinion`); an audit of 100 of them found four signed op-eds, mostly of the Wall
  Street Journal before 1998.

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
