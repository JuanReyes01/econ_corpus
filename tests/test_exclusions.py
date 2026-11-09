"""Tests for econ_corpus.exclusions on tiny synthetic tables."""

from datetime import date
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from econ_corpus import exclusions, parse, reasons, review, summaries

DEFAULTS = {
    "is_footer": False,
    "source_file": "ProQuestDocuments-2024-11-22_1.txt",
    "record_index": 0,
    "doc_id": 1,
    "body_sha256": "aaa",
    "body_chars": 100,
    "body_words": 500,
    "author": "Doe, Jane",
    "title": "Sample title",
    "pub_date": date(2020, 1, 2),
    "publication_key": "newyorktimes,lateedition(eastcoast);newyork,n.y.",
    "doc_type": "Commentary",
    "section": "Opinion",
}


def make_rows(*rows: dict) -> dict[str, list]:
    """Build a dict of columns from row dicts; missing keys take the defaults."""
    full = [{**DEFAULTS, **row} for row in rows]
    return {key: [row[key] for row in full] for key in DEFAULTS}


def records_table(rows: dict[str, list]) -> pa.Table:
    """Build a records table by hand, stamped as the parser stamps the ones it writes."""
    return pa.table(rows).replace_schema_metadata(parse.stamp())


def reasons_of(*rows: dict) -> list[str]:
    return exclusions.assign_reasons(make_rows(*rows))


# --- the reasons table -------------------------------------------------------------


def test_reason_codes_are_unique_and_end_with_kept() -> None:
    codes = [r["code"] for r in exclusions.REASONS]
    assert len(codes) == len(set(codes))
    assert codes[-1] == "kept"


def test_every_reason_has_a_description_and_a_dropped_flag() -> None:
    assert all(r["description"] for r in exclusions.REASONS)
    assert all(isinstance(r["dropped"], bool) for r in exclusions.REASONS)


def test_only_clear_non_opinion_and_duplicates_are_dropped() -> None:
    dropped = {r["code"] for r in exclusions.REASONS if r["dropped"]}
    assert dropped == {
        "file_footer",
        "not_queried_newspaper",
        "duplicate_id",
        "duplicate_text",
        "missing_metadata",
        "not_opinion",
        "unclear_opinion",
        "no_text",
        "no_author",
        "no_person_author",
    }


def test_only_footers_and_repeats_leave_the_raw_table() -> None:
    outside = {r["code"] for r in exclusions.REASONS if not r["in_raw"]}
    assert outside == {"file_footer", "duplicate_id", "duplicate_text"}


# --- file order --------------------------------------------------------------------


def test_file_order_sorts_by_date_then_numeric_suffix() -> None:
    names = [
        "ProQuestDocuments-2024-11-22_128.txt",
        "ProQuestDocuments-2024-11-22_9.txt",
        "ProQuestDocuments-2024-11-22.txt",
        "ProQuestDocuments-2024-11-21_500.txt",
    ]
    assert sorted(names, key=summaries.file_order) == [
        "ProQuestDocuments-2024-11-21_500.txt",
        "ProQuestDocuments-2024-11-22.txt",
        "ProQuestDocuments-2024-11-22_9.txt",
        "ProQuestDocuments-2024-11-22_128.txt",
    ]


# --- one reason per row ------------------------------------------------------------


def test_footer_rows_are_not_articles() -> None:
    assert reasons_of({"is_footer": True, "doc_id": None}) == ["file_footer"]


def test_plain_opinion_piece_is_kept() -> None:
    assert reasons_of({}) == ["kept"]


def test_news_label_in_an_opinion_section_is_kept() -> None:
    assert reasons_of({"doc_type": "NEWSPAPER", "section": "Opinion"}) == ["kept"]


def test_opinion_label_in_another_section_is_kept() -> None:
    assert reasons_of({"doc_type": "Commentary", "section": "Sports"}) == ["kept"]


def test_no_opinion_label_and_no_opinion_section_is_not_opinion() -> None:
    assert reasons_of({"doc_type": "NEWSPAPER", "section": "Sports"}) == ["not_opinion"]


def test_no_document_type_and_no_section_is_missing_metadata() -> None:
    assert reasons_of({"doc_type": None, "section": None}) == ["missing_metadata"]


def test_generic_label_and_no_section_is_unclear() -> None:
    row = {"doc_type": "NEWSPAPER", "section": None, "title": "World News: Vote count"}
    assert reasons_of(row) == ["unclear_opinion"]


def test_editorial_title_rescues_a_record_with_no_section() -> None:
    row = {"doc_type": "NEWSPAPER", "section": None, "title": "REVIEW & OUTLOOK (Editorial): X"}
    assert reasons_of(row) == ["kept"]


def test_op_ed_tag_in_the_title_keeps_a_record_in_a_news_section() -> None:
    row = {"doc_type": "News", "section": "A", "title": "What it means:   [Op-Ed ]"}
    assert reasons_of(row) == ["kept"]


def test_publication_outside_the_queried_newspapers_is_dropped() -> None:
    other = {"publication_key": "washingtonexaminer;washington,d.c."}
    assert reasons_of(other) == ["not_queried_newspaper"]


def test_a_repeated_non_queried_publication_is_still_a_repeated_id() -> None:
    other = {"publication_key": "laopinión;losangeles,calif."}
    second = {**other, "source_file": "ProQuestDocuments-2024-11-23_1.txt"}
    assert reasons_of(other, second) == ["not_queried_newspaper", "duplicate_id"]


def test_a_record_without_publication_or_id_cannot_be_classified() -> None:
    assert reasons_of({"publication_key": None}) == ["missing_metadata"]
    assert reasons_of({"doc_id": None}) == ["missing_metadata"]


# --- text and authors ---------------------------------------------------------------


def test_opinion_piece_without_text_is_dropped() -> None:
    assert reasons_of({"body_chars": 0, "body_sha256": None}) == ["no_text"]


def test_unsigned_opinion_piece_is_dropped() -> None:
    assert reasons_of({"author": None}) == ["no_author"]
    assert reasons_of({"author": "Anonymous"}) == ["no_author"]


def test_byline_that_names_no_person_is_dropped() -> None:
    assert reasons_of({"author": "The Editorial Board"}) == ["no_person_author"]


def test_one_person_among_the_byline_parts_is_enough() -> None:
    assert reasons_of({"author": "The Editorial Board; Doe, Jane"}) == ["kept"]


def test_a_news_item_is_not_opinion_whatever_its_author() -> None:
    row = {"doc_type": "NEWSPAPER", "section": "Sports", "author": None}
    assert reasons_of(row) == ["not_opinion"]


def test_text_and_author_reasons_are_the_last_before_kept() -> None:
    codes = [r["code"] for r in exclusions.REASONS]
    assert codes[-4:] == ["no_text", "no_author", "no_person_author", "kept"]


def test_a_reviewed_byline_decides_whether_a_person_signed() -> None:
    row = make_rows({"author": "Doe Roe, Ann"})
    assert exclusions.assign_reasons(row) == ["kept"]
    assert exclusions.assign_reasons(row, {"Doe Roe, Ann": ""}) == ["no_person_author"]
    board = make_rows({"author": "Example Board, The"})
    assert exclusions.assign_reasons(board, {"Example Board, The": "Doe, Jane"}) == ["kept"]


# --- duplicates --------------------------------------------------------------------


def test_repeated_id_keeps_the_earliest_download_whatever_the_row_order() -> None:
    later = {"source_file": "ProQuestDocuments-2024-12-01_2.txt"}
    earlier = {"source_file": "ProQuestDocuments-2024-11-22_9.txt"}
    assert reasons_of(later, earlier) == ["duplicate_id", "kept"]


def test_repeated_id_keeps_the_copy_with_the_longest_body_even_if_it_is_later() -> None:
    earlier_empty = {"source_file": "ProQuestDocuments-2024-11-22_1.txt", "body_chars": 0}
    later_full = {"source_file": "ProQuestDocuments-2024-12-01_1.txt", "body_chars": 500}
    assert reasons_of(earlier_empty, later_full) == ["duplicate_id", "kept"]


def test_repeated_id_with_equal_bodies_keeps_the_earliest_download() -> None:
    earlier = {"source_file": "ProQuestDocuments-2024-11-22_1.txt", "body_chars": 300}
    later = {"source_file": "ProQuestDocuments-2024-12-01_1.txt", "body_chars": 300}
    assert reasons_of(later, earlier) == ["duplicate_id", "kept"]


def test_a_missing_body_length_counts_as_zero() -> None:
    no_body = {"source_file": "ProQuestDocuments-2024-11-22_1.txt", "body_chars": None}
    with_body = {"source_file": "ProQuestDocuments-2024-12-01_1.txt", "body_chars": 10}
    assert reasons_of(no_body, with_body) == ["duplicate_id", "kept"]


def test_numeric_file_suffix_decides_the_earliest_copy() -> None:
    a = {"source_file": "ProQuestDocuments-2024-11-22_128.txt"}
    b = {"source_file": "ProQuestDocuments-2024-11-22_9.txt"}
    assert reasons_of(a, b) == ["duplicate_id", "kept"]


def test_a_news_article_repeated_is_counted_once_as_news_and_then_as_duplicates() -> None:
    news = {"doc_type": "NEWSPAPER", "section": "Sports"}
    second = {**news, "source_file": "ProQuestDocuments-2024-11-23_1.txt"}
    assert reasons_of(news, second) == ["not_opinion", "duplicate_id"]


def test_same_text_title_date_and_newspaper_under_another_id_is_a_duplicate() -> None:
    first = {"doc_id": 1}
    second = {"doc_id": 2, "source_file": "ProQuestDocuments-2024-11-23_1.txt"}
    assert reasons_of(first, second) == ["kept", "duplicate_text"]


LATER = "ProQuestDocuments-2024-11-23_1.txt"


def test_repeated_text_keeps_the_copy_that_qualifies_even_if_it_is_later() -> None:
    unsigned = {"doc_id": 1, "author": None}
    signed = {"doc_id": 2, "source_file": LATER}
    assert reasons_of(unsigned, signed) == ["duplicate_text", "kept"]
    news = {"doc_id": 1, "doc_type": "NEWSPAPER", "section": "Sports"}
    assert reasons_of(news, signed) == ["duplicate_text", "kept"]


def test_repeated_text_keeps_the_earliest_copy_when_none_qualifies() -> None:
    first = {"doc_id": 1, "author": None}
    second = {"doc_id": 2, "author": None, "source_file": LATER}
    assert reasons_of(first, second) == ["no_author", "duplicate_text"]


def test_repeated_text_keeps_the_earliest_of_the_copies_that_qualify() -> None:
    first, second, third = {"doc_id": 1, "author": None}, {"doc_id": 2}, {"doc_id": 3}
    second, third = {**second, "source_file": LATER}, {**third, "source_file": LATER}
    third["record_index"] = 1
    assert reasons_of(first, second, third) == ["duplicate_text", "kept", "duplicate_text"]


def test_which_copy_of_a_text_stays_does_not_depend_on_the_review() -> None:
    first = {"doc_id": 1, "author": "Example Board, The"}
    second = {"doc_id": 2, "source_file": LATER}
    rows = make_rows(first, second)
    plain = exclusions.assign_reasons(rows)
    reviewed = exclusions.assign_reasons(rows, {"Example Board, The": "Doe, Ann"})
    assert plain == ["no_person_author", "duplicate_text"]
    assert reviewed == ["kept", "duplicate_text"]


def test_a_byline_that_names_no_person_still_counts_as_signed_when_choosing_the_copy() -> None:
    board = {"doc_id": 1, "author": "The Editorial Board"}
    signed = {"doc_id": 2, "source_file": LATER}
    assert reasons_of(board, signed) == ["no_person_author", "duplicate_text"]


def test_stray_spaces_and_case_in_the_title_do_not_hide_a_repeated_text() -> None:
    first = {"doc_id": 1}
    second = {"doc_id": 2, "title": "Sam ple  TITLE", "source_file": LATER}
    assert reasons_of(first, second) == ["kept", "duplicate_text"]


def test_same_text_with_another_title_is_not_an_obvious_duplicate() -> None:
    first = {"doc_id": 1}
    second = {"doc_id": 2, "title": "Another title"}
    assert reasons_of(first, second) == ["kept", "kept"]


def test_same_text_on_another_date_is_not_an_obvious_duplicate() -> None:
    first = {"doc_id": 1}
    second = {"doc_id": 2, "pub_date": date(2021, 5, 6)}
    assert reasons_of(first, second) == ["kept", "kept"]


def test_records_without_body_are_never_text_duplicates() -> None:
    first = {"doc_id": 1, "body_sha256": None}
    second = {"doc_id": 2, "body_sha256": None}
    assert reasons_of(first, second) == ["kept", "kept"]


# --- counts and files --------------------------------------------------------------


def test_reason_counts_add_up_and_list_every_reason() -> None:
    reasons = ["kept", "kept", "not_opinion", "file_footer"]
    rows = exclusions.reason_counts(reasons)
    assert [r[0] for r in rows[1:-1]] == [r["code"] for r in exclusions.REASONS]
    assert rows[-1] == ["Total", "", "4", "100.0%", "", ""]
    counts = {r[0]: r[2] for r in rows[1:-1]}
    assert counts["kept"] == "2"
    assert counts["duplicate_id"] == "0"
    assert rows[0][-2:] == ["In raw", "Dropped"]
    assert {r[0]: r[-2] for r in rows[1:-1]}["duplicate_id"] == "no"
    assert {r[0]: r[-2] for r in rows[1:-1]}["kept"] == "yes"
    assert {r[0]: r[-1] for r in rows[1:-1]}["not_opinion"] == "yes"
    assert {r[0]: r[-1] for r in rows[1:-1]}["unclear_opinion"] == "yes"
    assert {r[0]: r[-2] for r in rows[1:-1]}["unclear_opinion"] == "yes"


def test_write_exclusions_keeps_one_row_per_input_row(tmp_path: Path) -> None:
    rows = make_rows(
        {},
        {"doc_id": 2, "doc_type": "NEWSPAPER", "section": "Sports", "body_sha256": "bbb"},
        {"is_footer": True, "doc_id": None},
    )
    source = tmp_path / "records.parquet"
    pq.write_table(records_table(rows), source)
    out = tmp_path / "interim" / "exclusions.parquet"
    exclusions.write_exclusions(source, out)
    result = pq.read_table(out).to_pydict()
    assert result["reason"] == ["kept", "not_opinion", "file_footer"]
    stamp = pq.read_schema(out).metadata[b"byline_parts"].decode()
    assert stamp == review.fingerprint({})
    exclusions.write_exclusions(source, out, {"Doe Roe, Ann": "Doe, Ann"})
    assert pq.read_schema(out).metadata[b"byline_parts"].decode() != stamp
    assert set(result) == {"source_file", "record_index", "reason"}


def test_reasons_are_refused_for_records_that_changed_since_they_were_computed(
    tmp_path: Path,
) -> None:
    source = tmp_path / "records.parquet"
    pq.write_table(records_table(make_rows({}, {"doc_id": 2, "body_sha256": "bbb"})), source)
    out = tmp_path / "exclusions.parquet"
    exclusions.write_exclusions(source, out)
    assert reasons.load(source, out).to_pylist() == ["kept", "kept"]
    # A new parse gives the same files and positions but another byline.
    pq.write_table(
        records_table(make_rows({}, {"doc_id": 2, "body_sha256": "bbb", "author": None})), source
    )
    with pytest.raises(ValueError, match="parse"):
        reasons.load(source, out)


def test_a_short_body_under_many_titles_is_a_placeholder_however_few_rows() -> None:
    rows = [
        {"doc_id": i, "title": f"Title {i}", "body_sha256": "ppp", "body_words": 12}
        for i in range(1, exclusions.PLACEHOLDER_ARTICLES + 1)
    ]
    assert reasons_of(*rows) == ["no_text"] * exclusions.PLACEHOLDER_ARTICLES
    assert reasons_of(*rows[:-1]) == ["kept"] * (exclusions.PLACEHOLDER_ARTICLES - 1)


def test_a_long_body_under_many_titles_is_text() -> None:
    rows = [
        {"doc_id": i, "title": f"Part {i}", "body_sha256": "lll", "body_words": 6000}
        for i in range(1, 30)
    ]
    assert reasons_of(*rows) == ["kept"] * 29


def test_copies_of_one_article_do_not_make_its_body_a_placeholder() -> None:
    rows = [{"doc_id": i, "body_sha256": "sss", "body_words": 40} for i in range(1, 30)]
    assert reasons_of(*rows) == ["kept", *["duplicate_text"] * 28]


def test_a_short_body_printed_on_many_days_under_one_title_is_a_placeholder() -> None:
    rows = [
        {"doc_id": i, "pub_date": date(2020, 1, i), "body_sha256": "ccc", "body_words": 11}
        for i in range(1, exclusions.PLACEHOLDER_ARTICLES + 1)
    ]
    assert reasons_of(*rows) == ["no_text"] * exclusions.PLACEHOLDER_ARTICLES


def test_reasons_are_refused_once_the_rules_change(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "records.parquet"
    pq.write_table(records_table(make_rows({})), source)
    out = tmp_path / "exclusions.parquet"
    exclusions.write_exclusions(source, out)
    monkeypatch.setattr(reasons, "rules_fingerprint", lambda: "other code")
    with pytest.raises(ValueError, match="rules"):
        reasons.load(source, out)


def test_a_reasons_file_without_fingerprints_says_so(tmp_path: Path) -> None:
    source = tmp_path / "records.parquet"
    pq.write_table(records_table(make_rows({})), source)
    out = tmp_path / "exclusions.parquet"
    keys = {"source_file": ["ProQuestDocuments-2024-11-22_1.txt"], "record_index": [0]}
    table = pq.read_table(source, columns=["source_file", "record_index"])
    pq.write_table(table.append_column("reason", pa.array(["kept"])), out)
    assert keys
    with pytest.raises(ValueError, match="no fingerprint"):
        reasons.load(source, out)


def test_the_rules_fingerprint_changes_with_the_code(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("X = 1\n", encoding="utf-8")
    before = reasons.rules_fingerprint(tmp_path)
    (tmp_path / "a.py").write_text("X = 2\n", encoding="utf-8")
    assert reasons.rules_fingerprint(tmp_path) != before


def test_reasons_are_refused_for_records_written_by_another_parser(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "records.parquet"
    pq.write_table(records_table(make_rows({})), source)
    out = tmp_path / "exclusions.parquet"
    exclusions.write_exclusions(source, out)
    reasons.load(source, out)
    monkeypatch.setattr(parse, "code_fingerprint", lambda: "another parser")
    with pytest.raises(ValueError, match="parse"):
        reasons.load(source, out)
