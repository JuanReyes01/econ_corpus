"""Used by step 2 of the pipeline: how many words of a text were written by its author.

Input: the text of a record.
Output: the number of words left once the page furniture is taken away, counted up to
MIN_OWN_WORDS, which is all that the reasons need.

Lives here: what page furniture is, as data, and the count. Does not live here: reading the
texts of the records (text_marks) or what the count means for a record (exclusions).

The text that ProQuest stores for a cartoon, a photograph or a gallery is not empty: the
export adds the credit and the description of the image, and the newspaper its own notices
and lists of links. A count of the stored words takes those for text and takes a short
letter for a caption. Without the furniture, a drawing has no words left and a letter keeps
all of its own.
"""

import re

import pyarrow as pa

# With fewer words of its author a piece has no text to read: about two sentences.
MIN_OWN_WORDS = 30
# The marks below were read in short texts only, where little follows an ending. In a text
# of LONG_TEXT_WORDS words or more the same words open a paragraph ('More on the budget:
# ...'), so a long text is not read: it has text, whatever its furniture.
LONG_TEXT_WORDS = 150

# A line that starts like one of these is dropped, alone. Lower case, matched at the start
# of the line.
FURNITURE_LINES = (
    # Added by the export: credits and descriptions of the images, notices, separators.
    r"cr[eé]dito?:",
    r"caption:",
    r"caption (?:text )?only",
    r"photo:",
    r"photographer:",
    r"graphic(?:-\w+)?:",
    r"illustration\b",
    r"drawing:",
    r"cartoon$",
    r"sidebar",
    r"see pdf for",
    r"note: quotes:",
    r"authoraffiliation\b",
    r"source url:",
    r"the story text of this article is not available",
    r"\(.{3,40} / for the times\)$",
    r"_{3,}",
    r"-{2,}$",
    r"\*$",
    r"--\s?\w+ \w+$",  # the signature under a drawing: '-- Jane Doe'
    # Added by the newspaper: invitations to follow, subscribe or read on.
    r"follow the new york times opinion section",
    r"follow the opinion section",
    r"see editorial cartoons and other visuals",
    r"sign up for ",
    r"to receive an email alert",
    r"for more in this series",
    r"read more:?$",
    r"more to read$",
    r"related:$",
    # The frame of a poll or a quiz.
    r"which of this week's",
    r"click the box",
    r"instructions: click",
    r"answers are:",
    r"who said it\?$",
    r"extras:$",
    r"winner:$",
)
# From a line that starts like one of these to the end, a short text is a list of links, a
# notice of the newspaper or a note on the author. A sentence of a letter can open with
# 'More' too ('More importantly: ...', 'More on that later, but ...'), so the head of a list
# is told by more than that word: the invitation ('See more', 'Read more'), a colon after
# who or what the list is about, or a name, which starts with a capital letter (`(?-i:`).
NAME = r"(?-i:[A-Z])"
ENDINGS = (
    r"(?:see|read) more (?:by|from|form|for|on|about)\b",  # 'Read more from Jane Doe'
    r"(?:see|read) more (?:\S+ ){0,3}cartoons\b",  # 'See more Jane Doe cartoons'
    r"more (?:by|from|on) [^,:]{1,40}:",  # 'More by Jane Doe: The price of bread'
    rf"more (?:by|from) {NAME}\S*(?: {NAME}\S*){{0,2}}$",  # 'More from Jane Doe', alone
    rf"(?:(?:see|read) )?more {NAME}[^,:]{{0,50}}:$",  # 'More Jane Doe on bread:'
    r"more [^,:]{0,30}cartoons[^,:]{0,30}:$",  # 'More cartoons:'
    r"more on this$",
    r"previous .{0,20}cartoons\b",
    r"the times is committed to publishing a diversity of letters",
    rf"(?:{NAME}\S* ){{1,6}}is (?:an|the) (?:editorial )?cartoonist (?:for|at|of)\b",
    r"editorial cartoonist .{0,40} captures the news",
)
# The address of the page, when the export glues it to the end of a line of text.
ADDRESS_RE = re.compile(r"\s*source url:.*$", re.IGNORECASE)
FURNITURE_RE = re.compile("|".join(FURNITURE_LINES), re.IGNORECASE)
ENDING_RE = re.compile("|".join(ENDINGS), re.IGNORECASE)


def own_words(text: str | None, enough: int = MIN_OWN_WORDS) -> int:
    """Count the words of a text that its author wrote, stopping at `enough`.

    A long text (see LONG_TEXT_WORDS) has `enough` without being read.
    """
    if not text:
        return 0
    if len(text.split(None, LONG_TEXT_WORDS - 1)) >= LONG_TEXT_WORDS:
        return enough
    count = 0
    for raw in text.split("\n"):
        line = " ".join(raw.split())
        if ENDING_RE.match(line):
            break
        if line and not FURNITURE_RE.match(line):
            count += len(ADDRESS_RE.sub("", line).split())
        if count >= enough:
            return enough
    return count


def own_word_counts(texts: pa.Array | pa.ChunkedArray) -> list[int]:
    """Return `own_words` of each text, in order."""
    return [own_words(text) for text in texts.to_pylist()]
