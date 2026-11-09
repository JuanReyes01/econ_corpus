"""Small pure helpers used to describe the parsed table: names, labels and shares.

Input: values taken from columns of the parsed table (see `parse`).
Output: display names, labels and formatted shares for the datasheet tables.

Lives here: grouping publication keys into newspapers, splitting multi-label fields,
formatting percentages. Does not live here: building tables (datasheet) or any filter
that decides which records to keep (exclusions).
"""

import re

# Publication key prefix (see `parse.compact`) -> display name. These are the 10 newspapers
# of the ProQuest query (the scraper README also lists New York Post, which was dropped);
# everything else is reported as 'Other'.
INTENDED_NEWSPAPERS = {
    "newyorktimes": "New York Times",
    "thewashingtonpost": "Washington Post",
    "wallstreetjournal": "Wall Street Journal",
    "losangelestimes": "Los Angeles Times",
    "bostonglobe": "Boston Globe",
    "chicagotribune": "Chicago Tribune",
    "usatoday": "USA Today",
    "newsday,": "Newsday",  # the Long Island editions; a Newsday of Zimbabwe also exists
    "tampabaytimes": "Tampa Bay Times",
    "startribune": "Star Tribune",
}

# Document types the ProQuest query asked for (matched ignoring case).
QUERIED_DOC_TYPES = {"commentary", "editorial", "news"}

# A section label containing one of these words (spaces removed, so 'Op Ed' becomes 'oped')
# is treated as an opinion section. Built from the most common sections of records that had
# no other opinion signal.
OPINION_SECTION_WORDS = (
    "opinion", "editorial", "op-ed", "oped", "op/ed", "viewpoint", "perspective", "letter",
    "commentary", "column",
)  # fmt: skip

# Section labels that are an opinion section without holding one of those words: 'EPg' is
# the editorial page of the Boston Globe before 1997.
OPINION_SECTIONS = {"epg"}

# A document-type label containing one of these words is treated as an opinion label.
OPINION_LABEL_WORDS = ("opinion", "editorial", "commentary", "op-ed", "op/ed", "letter", "column")

# Titles (spaces removed, casefolded) that mark opinion-page items: the title starts with a
# recurring opinion-page heading, or carries an opinion tag. Built from titles of records
# that had no section, such as Wall Street Journal editorial-page items.
OPINION_TITLE_STARTS = (
    "review&outlook", "letterstotheeditor", "opiniontoday:", "opinion:", "viewpoint:",
    "notable&quotable", "asides:", "boardofcontributors", "thejournaleditorialreport",
)  # fmt: skip
OPINION_TITLE_TAGS = ("(editorial)", "[op-ed", "[editorial", "[letter", "[commentary")


def newspaper_family(publication_key: str | None) -> str | None:
    """Return the newspaper a publication key belongs to, 'Other', or None if missing."""
    if publication_key is None:
        return None
    for prefix, name in INTENDED_NEWSPAPERS.items():
        if publication_key.startswith(prefix):
            return name
    return "Other"


def edition(publication_key: str) -> str:
    """Return 'online', 'pre-1997' or 'print' from the edition tag in a publication key."""
    if "(online)" in publication_key:
        return "online"
    if "pre-1997" in publication_key:
        return "pre-1997"
    return "print"


def split_labels(value: str | None) -> list[str]:
    """Split a comma-separated multi-label value such as 'Commentary, Opinions'."""
    if value is None:
        return []
    return [part.strip() for part in value.split(",") if part.strip()]


def label_key(label: str) -> str:
    """Return a label without spaces and casefolded, to compare it despite stray spaces."""
    return "".join(label.split()).casefold()


def download_date(source_file: str) -> str | None:
    """Return the YYYY-MM-DD date written in a ProQuest export file name."""
    match = re.search(r"\d{4}-\d{2}-\d{2}", source_file)
    return match[0] if match else None


def pct(part: int, total: int) -> str:
    """Format a share with one decimal, or 'n/a' when there is nothing to divide by."""
    return f"{100 * part / total:.1f}%" if total else "n/a"


def num(count: int) -> str:
    """Format a count with thousands separators."""
    return f"{count:,}"


def is_opinion_section(section: str | None) -> bool:
    """Tell whether a section label looks like an opinion or editorial section."""
    if section is None:
        return False
    squeezed = re.sub(r"\s+", "", section).casefold()
    return squeezed in OPINION_SECTIONS or any(w in squeezed for w in OPINION_SECTION_WORDS)


def is_opinion_label(label: str) -> bool:
    """Tell whether a document-type label looks like an opinion label."""
    squeezed = re.sub(r"\s+", "", label).casefold()
    return any(w in squeezed for w in OPINION_LABEL_WORDS)


def file_order(source_file: str) -> tuple[str, int]:
    """Return a sort key for export files: download date, then the number after it.

    ProQuest numbers the downloads of one day as '_3'; a browser that saves a name twice
    writes ' (3)'. Both are read.
    """
    match = re.search(r"(\d{4}-\d{2}-\d{2})(?:_(\d+)| \((\d+)\))?", source_file)
    return (match[1], int(match[2] or match[3] or 0)) if match else ("", 0)


def is_opinion_title(title: str | None) -> bool:
    """Tell whether a title starts with an opinion-page heading or carries an opinion tag."""
    if title is None:
        return False
    squeezed = re.sub(r"\s+", "", title).casefold()
    return squeezed.startswith(OPINION_TITLE_STARTS) or any(
        tag in squeezed for tag in OPINION_TITLE_TAGS
    )
