"""The reasons table: why a row of the parsed table is left out, as data.

Input: nothing; this module only holds the table.
Output: `REASONS`, one entry per reason, and `LEFT_OUT`, the codes of rows that are not part of
the shared raw table.

Lives here: the codes, their meaning and the two flags. Does not live here: the rules that
assign a reason (exclusions) or what is done with the flags (export, datasheet).

`in_raw` says whether a row belongs to the shared raw table (footers and repeats do not);
`dropped` says whether it leaves the cleaned dataset. Each row gets exactly one reason.
"""

# The reasons table: code and meaning, in the order the rules are applied.
REASONS = [
    {
        "code": "file_footer",
        "description": "Row is the footer of an export file, not an article",
        "in_raw": False,
        "dropped": True,
    },
    {
        "code": "duplicate_id",
        "description": "Repeats a ProQuest id; the copy with the longest body is the one kept",
        "in_raw": False,
        "dropped": True,
    },
    {
        "code": "not_queried_newspaper",
        "description": "Publication is not one of the queried newspapers",
        "in_raw": True,
        "dropped": True,
    },
    {
        "code": "duplicate_text",
        "description": "Same body, title, date and newspaper as an earlier record",
        "in_raw": False,
        "dropped": True,
    },
    {
        "code": "missing_metadata",
        "description": "No document type, no section and no opinion title: cannot be classified",
        "in_raw": True,
        "dropped": True,
    },
    {
        "code": "not_opinion",
        "description": "A news section, and neither an opinion document type nor an opinion title",
        "in_raw": True,
        "dropped": True,
    },
    {
        "code": "unclear_opinion",
        "description": "Generic document type, no section and no opinion title: may be opinion",
        "in_raw": True,
        "dropped": True,
    },
    {
        "code": "no_text",
        "description": "Opinion piece with no body text",
        "in_raw": True,
        "dropped": True,
    },
    {
        "code": "no_author",
        "description": "Opinion piece that is unsigned or marked Anonymous",
        "in_raw": True,
        "dropped": True,
    },
    {
        "code": "no_person_author",
        "description": "Byline names no person (an institution, or text with no full name)",
        "in_raw": True,
        "dropped": True,
    },
    {
        "code": "kept",
        "description": "Opinion piece with text, signed by at least one person",
        "in_raw": True,
        "dropped": False,
    },
]

LEFT_OUT = [r["code"] for r in REASONS if not r["in_raw"]]
