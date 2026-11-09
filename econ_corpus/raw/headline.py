"""Used by step 3b of the pipeline: the headline numbers quoted in the raw datasheet.

Input: articles as a dict of columns (see `shared.tables`): the shared raw table or the
table as parsed, and the count of parsed rows per reason.
Output: the numbers, already written as text, keyed by their placeholder in the template.

Lives here: counting records, ids, repeats, years, authors, labels, newspapers and blogs
for the prose. Does not live here: the tables (shared.tables), the template filling and the
file writing (datasheet), or any decision about which records to keep (exclusions).
"""

from collections import Counter, defaultdict

from econ_corpus.names import bylines
from econ_corpus.shared import summaries, tables
from econ_corpus.shared.tables import Articles


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
    signed = sum(map(bylines.is_signed, articles["author"]))  # 'Anonymous' is no author
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
    keys = [{summaries.label_key(x) for x in each} for each in labels]
    outside = sum(bool(each) and not each & summaries.QUERIED_DOC_TYPES for each in keys)
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
        "n_doc_type_labels": summaries.num(len(set().union(*keys))),
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
