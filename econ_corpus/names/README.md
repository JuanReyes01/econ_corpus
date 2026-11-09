# Names: who signed an article

Reading bylines and deciding which names are one author. Pipeline 1 uses it to tell whether
a byline names a person; pipeline 2 to build the authors of the cleaned dataset.

| File | What it does |
|---|---|
| `name_words.py` | Word lists, as data: titles and ranks, suffixes, particles, words of institutions, places and publications |
| `authors.py` | One name: reads `Family, Given` or `Given Family`, writes it for display, and gives the key that ignores case, accents and spaces |
| `parts.py` | One part of a byline: reads the persons it names, and recovers a name followed by a town, a role, a note, a list of co-authors or the members of an editorial board |
| `bylines.py` | One byline: cuts it into parts, puts the names of its parts together (a name repeated by the note after it counts once) and applies the corrections of the manual review |
| `identity.py` | Which name keys are one author: the rule that merges variants of a name, and how review verdicts bend it |
| `lookalikes.py` | The pairs of authors that look alike and are not merged (a letter apart, a short form of the given name, names swapped) |
| `review.py` | The decisions of the manual review, read from `data/review/` (corrected byline parts and verdicts on pairs of names) |

Nothing here reads the records or writes a file of the pipelines.
