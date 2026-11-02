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
    "newsday": "Newsday",
    "tampabaytimes": "Tampa Bay Times",
    "startribune": "Star Tribune",
}

# Document types the ProQuest query asked for (matched ignoring case).
QUERIED_DOC_TYPES = {"commentary", "editorial", "news"}

# A section label containing one of these words is treated as an opinion section.
OPINION_SECTION_WORDS = ("opinion", "editorial", "op-ed", "op/ed")


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
    return section is not None and any(w in section.casefold() for w in OPINION_SECTION_WORDS)
