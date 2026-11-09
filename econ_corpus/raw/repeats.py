"""Used by step 2 of the pipeline: find the copies of one record and of one text.

Input: rows of the parsed table, as a dict of columns, and the order in which they are judged.
Output: the copy of each ProQuest id that is judged, what the copies of a text share, the
bodies that are a notice shared by different articles, and the copies of a text marked
`duplicate_text`.

Lives here: choosing among repeated ids, keying repeated text and telling placeholders from
text. Does not live here: the order in which the rules are applied (exclusions), or the
rules judged on one record (record_rules).
"""

from collections.abc import Iterable
from datetime import date

from econ_corpus.raw import labels
from econ_corpus.shared.tables import Articles

# A body shorter than PLACEHOLDER_WORDS can be a notice, a caption or an introduction shared
# by different articles. Carried by PLACEHOLDER_ARTICLES or more of them it is a notice ("text
# not available") or a credit, not their text.
PLACEHOLDER_WORDS, PLACEHOLDER_ARTICLES = 100, 5


def kept_copies(rows: Articles, order: list[int]) -> dict[int, int]:
    """Return, for each ProQuest id, the row to keep: the longest body, then the earliest download.

    A later copy can be the only one with text (some downloads came out without body), so
    the earliest copy alone is not a safe choice.
    """
    kept: dict[int, int] = {}
    for i in order:
        doc_id = rows["doc_id"][i]
        if rows["is_footer"][i] or doc_id is None:
            continue
        # Strictly longer, so on a tie the earliest copy stays.
        if doc_id not in kept or (rows["body_chars"][i] or 0) > (
            rows["body_chars"][kept[doc_id]] or 0
        ):
            kept[doc_id] = i
    return kept


def text_key(rows: Articles, i: int, family: str | None) -> tuple | None:
    """Return what the copies of the text of row `i` share, or None if it cannot repeat.

    A body of PLACEHOLDER_WORDS or more is one text wherever it appears in a newspaper: under
    another title (print and online editions) or on another date (a text posted again). A
    shorter body can belong to different articles, so its copies also share title and date.
    """
    sha, title, day = rows["body_sha256"][i], rows["title"][i], rows["pub_date"][i]
    if sha and (rows["body_words"][i] or 0) >= PLACEHOLDER_WORDS:
        return (sha, family)
    # Titles are compared without ProQuest's stray spaces, like every other metadata.
    return (sha, family, labels.compact(title), day) if sha and title and day else None


def mark_repeated_text(
    groups: Iterable[list[int]], reasons: list[str], qualifies: set[int], days: list[date | None]
) -> None:
    """Leave one copy of each repeated text and mark the others `duplicate_text`, in place.

    The copy that stays is a signed opinion piece with text if there is one, then the first
    published (an undated copy comes last), then the earliest download.
    """
    for copies in groups:
        stays = min(copies, key=lambda i: (i not in qualifies, days[i] or date.max))
        for i in copies:
            if i != stays:
                reasons[i] = "duplicate_text"


def placeholders(rows: Articles, judged: list[int]) -> set[str]:
    """Return the bodies that are a notice shared by different articles, not their text.

    Articles are counted, not rows: an article is a title on a date, so the copies of one
    article share a body without making it a notice. A long body under several titles is
    real text printed more than once.
    """
    articles: dict[str, set[tuple]] = {}
    for i in judged:
        if (rows["body_words"][i] or 0) < PLACEHOLDER_WORDS:
            article = (labels.compact(rows["title"][i] or ""), rows["pub_date"][i])
            articles.setdefault(rows["body_sha256"][i], set()).add(article)
    return {sha for sha, found in articles.items() if len(found) >= PLACEHOLDER_ARTICLES}
