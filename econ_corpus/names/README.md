# Names: who signed an article

Reading bylines and deciding which names are one author. Pipeline 1 uses it to tell whether
a byline names a person; pipeline 2 to build the authors of the cleaned dataset.

| File | What it does |
|---|---|
| `name_words.py` | Word lists, as data: titles and ranks, suffixes, particles, words of institutions, places and publications |
| `name_tokens.py` | One word of a name: whether it is a title or initials, a particle, in capitals or a word of an institution, and the form in which it is looked up |
| `authors.py` | One name: reads `Family, Given` or `Given Family` |
| `spelling.py` | Writes a name for display, gives the key that ignores case, accents and spaces, and tells whether two spellings are one letter apart |
| `name_start.py` | The name at the start of a part of a byline that goes on with other text (a town, a role, a note), read once when it is written twice |
| `name_lists.py` | Several people in one part: a list of co-authors, co-authors scrambled by the export, the members of an editorial board; and whether two names share a family name or a first given name |
| `parts.py` | One part of a byline: removes the labels the export glued to it, leaves out notes about people who did not write, and tries each way of reading it in turn |
| `bylines.py` | One byline: cuts it into parts, puts the names of its parts together (a name repeated by the note after it counts once) and applies the corrections of the manual review |
| `identity.py` | Which name keys are one author: the rule that merges variants of a name, and how review verdicts bend it |
| `lookalikes.py` | The pairs of authors that look alike and are not merged (a letter apart, a short form of the given name, names swapped) |
| `review.py` | The decisions of the manual review, read from `data/review/` (corrected byline parts and verdicts on pairs of names) |

Nothing here reads the records or writes a file of the pipelines.
