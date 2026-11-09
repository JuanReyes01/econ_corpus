"""Stage 2 of the pipeline: describe the raw table and write its datasheet.

Input: the parquet written by `parse`, the reasons written by `exclusions` and a prose
template with {{placeholders}}.
Output: a markdown datasheet whose numbers all come from the data, plus yearly and
per-download tables as CSV, so every figure in the text can be reproduced.

The shared raw table leaves out footers and repeated ids, so the tables describe that table;
the repeats, the yearly counts and the download dates describe the table as parsed.

Lives here: the headline numbers, the template filling and the file writing. Does not
live here: the tables themselves (tables), the prose (the template, in docs/) or any
decision about which records to keep (exclusions).
"""

from collections import Counter, defaultdict
import csv
from pathlib import Path
import re

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

from econ_corpus import figures, summaries, tables
from econ_corpus.reasons import LEFT_OUT
from econ_corpus.tables import Articles, Table

COLUMNS = [
    "publication_key", "publication", "source_type_key", "author", "pub_year", "doc_id",
    "doc_type", "section", "language_key", "source_file", "date_status", "year_status",
    "id_status", "has_body", "title", "is_footer",
]  # fmt: skip


def fill(template: str, values: dict[str, str]) -> str:
    """Replace every {{name}} with its value; an unknown name raises KeyError."""
    return re.sub(r"\{\{(\w+)\}\}", lambda m: values[m[1]], template)


def _count_facts(articles: Articles) -> dict[str, str]:
    """Return record, id, year, author, body and download-date numbers."""
    n = len(articles["title"])
    ids = [i for i in articles["doc_id"] if i is not None]
    duplicates = len(ids) - len(set(ids))
    pairs = [
        (source, i)
        for source, i in zip(articles["source_file"], articles["doc_id"], strict=True)
        if i
    ]
    files_by_id: dict[int, set[str]] = {}
    for source, doc_id in pairs:
        files_by_id.setdefault(doc_id, set()).add(source)
    several_files = sum(len(files) > 1 for files in files_by_id.values())
    years = [y for y in articles["pub_year"] if y]
    signed = sum(a is not None for a in articles["author"])
    days = sorted({d for f in articles["source_file"] if (d := summaries.download_date(f))})
    no_body = [
        f for f, has in zip(articles["source_file"], articles["has_body"], strict=True) if not has
    ]
    return {
        "n_articles": summaries.num(n),
        "n_files": summaries.num(len(set(articles["source_file"]))),
        "n_unique_ids": summaries.num(len(set(ids))),
        "n_duplicate_rows": summaries.num(duplicates),
        "n_ids_in_several_files": summaries.num(several_files),
        "n_repeats_inside_a_file": summaries.num(len(pairs) - len(set(pairs))),
        "dup_pct": summaries.pct(duplicates, n),
        "year_min": str(min(years)),
        "year_max": str(max(years)),
        "n_with_author": summaries.num(signed),
        "with_author_pct": summaries.pct(signed, n),
        "n_no_body": summaries.num(len(no_body)),
        "n_no_body_files": summaries.num(len(set(no_body))),
        "download_first": days[0],
        "download_last": days[-1],
    }


def _label_facts(articles: Articles) -> dict[str, str]:
    """Return document-type and language numbers."""
    n = len(articles["title"])
    labels = [summaries.split_labels(v) for v in articles["doc_type"]]
    outside = sum(
        bool(each) and not any(x.casefold() in summaries.QUERIED_DOC_TYPES for x in each)
        for each in labels
    )
    english = sum(k == "english" for k in articles["language_key"])
    opinion_doc = [any(map(summaries.is_opinion_label, each)) for each in labels]
    opinion_sec = [summaries.is_opinion_section(sec) for sec in articles["section"]]
    news_in_opinion = sum(
        bool(each) and not doc and sec
        for each, doc, sec in zip(labels, opinion_doc, opinion_sec, strict=True)
    )
    no_signal = sum(not doc and not sec for doc, sec in zip(opinion_doc, opinion_sec, strict=True))
    return {
        "news_label_opinion_section_pct": summaries.pct(news_in_opinion, n),
        "no_opinion_signal_n": summaries.num(no_signal),
        "no_opinion_signal_pct": summaries.pct(no_signal, n),
        "n_doc_type_labels": summaries.num(len({d for d in articles["doc_type"] if d})),
        "n_outside_doc_types": summaries.num(outside),
        "outside_doc_types_pct": summaries.pct(outside, n),
        "english_only_pct": summaries.pct(english, n),
    }


def _publication_facts(articles: Articles) -> dict[str, str]:
    """Return newspaper-coverage and source-type numbers, including where blogs come from."""
    n = len(articles["title"])
    keys = articles["publication_key"]
    families = [summaries.newspaper_family(k) for k in keys]
    queried = list(summaries.INTENDED_NEWSPAPERS.values())
    blog = [s == tables.BLOG_LABEL for s in articles["source_type_key"]]
    blog_keys = [k for k, is_blog in zip(keys, blog, strict=True) if is_blog]
    blog_sections = [
        sec for sec, is_blog in zip(articles["section"], blog, strict=True) if is_blog
    ]
    opinion = sum(summaries.is_opinion_section(sec) for sec in blog_sections)
    online = sum(summaries.edition(k) == "online" for k in blog_keys if k)
    return {
        "n_other_publications": summaries.num(
            len({k for k, f in zip(keys, families, strict=True) if f == "Other"})
        ),
        "missing_newspapers": ", ".join(x for x in queried if x not in families) or "none",
        "n_blog": summaries.num(sum(blog)),
        "blog_pct": summaries.pct(sum(blog), n),
        "blog_online_pct": summaries.pct(online, len(blog_keys)),
        "blog_newspapers": ", ".join(
            x for x in queried if x in {summaries.newspaper_family(k) for k in blog_keys}
        ),
        "blog_opinion_section_pct": summaries.pct(opinion, len(blog_sections)),
        "n_queried_newspapers": str(len(queried)),
    }


def _peak_year_facts(articles: Articles) -> dict[str, str]:
    """Return the year with the most repeated rows, and how many files its ids are spread over."""
    rows: Counter = Counter()
    files: defaultdict[int, defaultdict[int, set[str]]] = defaultdict(lambda: defaultdict(set))
    for year, doc_id, source in zip(
        articles["pub_year"], articles["doc_id"], articles["source_file"], strict=True
    ):
        if year and doc_id is not None:
            rows[year] += 1
            files[year][doc_id].add(source)
    peak = max(rows, key=lambda y: rows[y] - len(files[y]))
    spread = sum(len(f) >= 3 for f in files[peak].values())  # noqa: PLR2004
    return {
        "dup_peak_year": str(peak),
        "dup_peak_rows": summaries.num(rows[peak]),
        "dup_peak_unique": summaries.num(len(files[peak])),
        "dup_peak_multi_file_pct": summaries.pct(spread, len(files[peak])),
    }


def facts(articles: Articles) -> dict[str, str]:
    """Return the headline numbers quoted in the prose of the datasheet."""
    return (
        _count_facts(articles)
        | _label_facts(articles)
        | _publication_facts(articles)
        | _peak_year_facts(articles)
    )


# Facts that describe the table as parsed, before repeated ids were removed.
PARSED_FACTS = [
    "n_duplicate_rows", "n_ids_in_several_files", "n_repeats_inside_a_file", "dup_pct",
    "dup_peak_year", "dup_peak_rows", "dup_peak_unique", "dup_peak_multi_file_pct",
    "n_files", "download_first", "download_last",
]  # fmt: skip


def repeat_facts(parsed: Articles, removed: Counter) -> dict[str, str]:
    """Return the parsed size, the repeats removed and the ids with an empty copy.

    `removed` counts the rows of the parsed table per exclusion reason. An id has an empty copy
    when one of its copies has no body next to a copy that has one.
    """
    copies: defaultdict[int, list[bool]] = defaultdict(list)
    for doc_id, has_body in zip(parsed["doc_id"], parsed["has_body"], strict=True):
        if doc_id is not None:
            copies[doc_id].append(has_body)
    mixed = sum(len(h) > 1 and any(h) and not all(h) for h in copies.values())
    return {
        "n_parsed": summaries.num(len(parsed["title"])),
        "n_ids_parsed": summaries.num(len(copies)),
        "n_repeats_removed": summaries.num(removed["duplicate_id"]),
        "n_text_repeats_removed": summaries.num(removed["duplicate_text"]),
        "n_ids_with_empty_copy": summaries.num(mixed),
    }


def write_csv(rows: Table, path: Path) -> None:
    """Write a table to a CSV file, creating the folder if needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        csv.writer(handle).writerows(rows)


def build(  # noqa: PLR0913 (one argument per input or output file)
    parquet: Path,
    reasons: Path,
    template: Path,
    out_md: Path,
    *,
    tables_dir: Path,
    figures_dir: Path,
) -> None:
    """Read the parquet, fill the template and write the datasheet and the CSV tables."""
    table = pq.read_table(parquet, columns=COLUMNS)
    codes = pq.read_table(reasons, columns=["reason"])["reason"]
    in_raw = pc.invert(pc.is_in(codes, value_set=pa.array(LEFT_OUT)))
    parsed = table.filter(pc.invert(table["is_footer"])).to_pydict()
    articles = table.filter(in_raw).to_pydict()
    described = {
        "newspapers": tables.newspaper_table(articles),
        "online_editions": tables.online_edition_table(articles),
        "blog_profile": tables.blog_profile_table(articles),
        "decades": tables.decade_table(articles),
        "doc_types": tables.doc_type_table(articles),
        "sections": tables.section_table(articles),
        "languages": tables.language_table(articles),
        "missing": tables.missing_table(articles),
        "other_publications": tables.other_publications_table(articles),
    }
    as_parsed = {k: v for k, v in facts(parsed).items() if k in PARSED_FACTS}
    footers = {"n_footer_rows": summaries.num(pc.sum(table["is_footer"]).as_py())}
    values = (
        facts(articles)
        | as_parsed
        | repeat_facts(parsed, Counter(codes.to_pylist()))
        | footers
        | {name: tables.md_table(rows) for name, rows in described.items()}
    )
    out_md.write_text(fill(template.read_text(encoding="utf-8"), values), encoding="utf-8")
    write_csv(tables.year_table(parsed), tables_dir / "raw_by_year.csv")
    write_csv(tables.download_table(parsed), tables_dir / "raw_by_download_date.csv")
    figures_dir.mkdir(parents=True, exist_ok=True)
    shared_chart = figures.year_chart_svg(
        tables.year_table(articles),
        labels=("Records",),
        heading="Records per publication year in the shared table",
    )
    (figures_dir / "records_by_year.svg").write_text(shared_chart, encoding="utf-8")
    repeats_chart = figures.year_chart_svg(
        tables.year_comparison_table(parsed, articles),
        labels=("As parsed", "Shared table"),
        heading="Records per publication year, as parsed and in the shared table",
    )
    (figures_dir / "repeats_by_year.svg").write_text(repeats_chart, encoding="utf-8")


def main() -> None:
    """Build the datasheet of the raw table from the repo's default locations."""
    build(
        Path("data/interim/records.parquet"),
        Path("data/interim/exclusions.parquet"),
        Path("docs/datasheet_raw.template.md"),
        Path("docs/datasheet_raw.md"),
        tables_dir=Path("reports/tables"),
        figures_dir=Path("reports/figures"),
    )


if __name__ == "__main__":
    main()
