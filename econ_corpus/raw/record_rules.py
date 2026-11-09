"""Used by step 2 of the pipeline: the rules that judge one record on its own metadata.

Input: the document type, section, title and byline of one record, or one row of the parsed
table, as a dict of columns.
Output: whether it is opinion, whether a person signs it, and whether it is a page compiled
from the words of others.

Lives here: the opinion, author and compiled-page rules. Does not live here: the copies of a
record or of a text (repeats), or the order in which the rules are applied (exclusions).
"""

from econ_corpus.names import bylines
from econ_corpus.shared import summaries
from econ_corpus.shared.tables import Articles

# The round-up of late-night jokes of ROUNDUP_PAPER often has no heading: a title that names
# a comedian over a body under ROUNDUP_WORDS. Its columns about a comedian are longer.
ROUNDUP_PAPER, ROUNDUP_WORDS = "USA Today", 300


def opinion_reason(
    doc_type: str | None, section: str | None, title: str | None, *, rubric: bool = False
) -> str:
    """Return the reason for a record that is not a duplicate.

    An opinion title, document type or section keeps the record, and so does the rubric of an
    opinion page as the first line of its text (see `text_marks`). Without any of them, a
    record with no section is unclear (the section is what would settle it), and one in a
    news section is not opinion.
    """
    labels = summaries.split_labels(doc_type)
    if summaries.is_opinion_title(title) or rubric:
        return "kept"
    if not labels and section is None:
        return "missing_metadata"
    if any(map(summaries.is_opinion_label, labels)) or summaries.is_opinion_section(section):
        return "kept"
    return "unclear_opinion" if section is None else "not_opinion"


def author_reason(byline: str | None, corrections: dict[str, str] | None) -> str:
    """Return the reason for an opinion piece with text, given its byline."""
    if not bylines.is_signed(byline):
        return "no_author"
    return "kept" if bylines.people(byline, corrections) else "no_person_author"


def compiled(rows: Articles, i: int, family: str | None, *, poll: bool = False) -> bool:
    """Tell whether a piece is a page compiled from the words of others.

    A heading in the title says so in any newspaper (see `summaries.is_compiled_title`). The
    round-up of jokes of ROUNDUP_PAPER is also told without one, and a poll on the words of
    others by the frame in its text (`poll`, see `text_marks.poll_frames`).
    """
    title = rows["title"][i]
    short = (rows["body_words"][i] or 0) < ROUNDUP_WORDS
    roundup = family == ROUNDUP_PAPER and short and summaries.is_late_night_title(title)
    return summaries.is_compiled_title(title) or roundup or poll
