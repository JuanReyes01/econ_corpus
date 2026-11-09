"""Tests for econ_corpus.parse, using small synthetic records (no real article text)."""

from datetime import date
import hashlib
from pathlib import Path

import pyarrow.parquet as pq
import pytest

from econ_corpus import parse

SEP = "_" * 60
FOOTER = (
    "\n\nContáctenos en: https://example.test/contact\n"
    "Copyright de la base de datos © 2024 Example LLC. Reservados todos los derechos.\n"
    "Términos y condiciones: https://example.test/terms\n"
)
DEFAULT_META = {
    "Título": "Sample title",
    "Autor": "Doe, Jane",
    "Título de publicación": "Example Daily; City",
    "Año de publicación": "2022",
    "Fecha de publicación": "Nov 9, 2022",
    "Sección": "opinion",
    "Idioma de la publicación": "English",
    "Tipo de documento": "Opinions",
    "ID del documento de ProQuest": "1234567890",
    "Base de datos": "U.S. Newsstream",
}


def make_record(
    body: str = "Body line one.\nBody line two.",
    materia: str | None = None,
    extra: dict[str, str] | None = None,
    **meta_overrides: str | None,
) -> str:
    """Build one synthetic record chunk; an override of None removes that label."""
    meta = {**DEFAULT_META, **meta_overrides}
    head = (
        f"\nSample title\n\nAutor: Doe, Jane.\n\nhttps://example.test/doc\n\n"
        f"Resumen: Ninguno disponible.\n\nEnlaces: https://example.test/links\n\n"
        f"Texto completo: {body}\n\n"
    )
    materia_block = f"Materia: {materia}\n\n" if materia is not None else ""
    extra_block = "".join(f"{k}: {v}\n\n" for k, v in (extra or {}).items())
    meta_block = "".join(f"{k}: {v}\n\n" for k, v in meta.items() if v is not None)
    return head + materia_block + extra_block + meta_block


def make_file(records: list[str], *, footer: bool = True, crlf: bool = True) -> str:
    text = "".join(f"{SEP}\n{r}" for r in records) + f"{SEP}\n"
    text += FOOTER if footer else ""
    return text.replace("\n", "\r\n") if crlf else text


def parse_one(chunk: str, index: int = 0) -> dict:
    return parse.parse_record(chunk, "f.txt", index)


# --- splitting ---------------------------------------------------------------------


def test_split_drops_preamble_and_keeps_footer_as_last_chunk() -> None:
    chunks = parse.split_records(make_file([make_record(), make_record()]))
    assert len(chunks) == 3
    assert "Contáctenos" in chunks[-1]


def test_split_handles_lf_and_crlf_the_same() -> None:
    records = [make_record(), make_record()]
    assert parse.split_records(make_file(records, crlf=True)) == parse.split_records(
        make_file(records, crlf=False)
    )


# --- fields ------------------------------------------------------------------------


def test_record_with_materia_parses_fields() -> None:
    row = parse_one(make_record(materia="Topic A; Topic B"))
    assert row["title"] == "Sample title"
    assert row["author"] == "Doe, Jane"
    assert row["publication"] == "Example Daily; City"
    assert row["doc_id"] == 1234567890
    assert row["has_materia"] is True
    assert row["body_words"] == 6


def test_record_without_materia_keeps_metadata_out_of_body() -> None:
    row = parse_one(make_record(materia=None))
    assert row["has_materia"] is False
    assert row["title"] == "Sample title"
    assert row["body_sha256"] == hashlib.sha256(b"Body line one.\nBody line two.").hexdigest()


def test_body_lines_that_look_like_labels_stay_in_body() -> None:
    body = "Intro text.\nCredit: someone\nEditorial: not a label here\nLast words."
    row = parse_one(make_record(body=body))
    assert row["body_words"] == len(body.split())
    assert row["doc_id"] == 1234567890


def test_missing_author_is_none() -> None:
    assert parse_one(make_record(Autor=None))["author"] is None


def test_multiline_metadata_value_is_joined() -> None:
    row = parse_one(make_record(materia="Topic A;\nTopic B", Título="Line one\nLine two"))
    assert row["title"] == "Line one Line two"
    assert row["has_materia"] is True
    assert row["doc_id"] == 1234567890


def test_multiline_body_with_blank_lines_is_fully_counted() -> None:
    row = parse_one(make_record(body="One two.\n\nThree four.\n\nFive."))
    assert row["body_words"] == 5


def test_footer_chunk_is_flagged_and_empty() -> None:
    row = parse_one(parse.split_records(make_file([make_record()]))[-1], index=1)
    assert row["is_footer"] is True
    assert row["has_body"] is False
    assert row["doc_id"] is None
    assert row["record_index"] == 1


def test_article_is_not_footer() -> None:
    assert parse_one(make_record())["is_footer"] is False


# --- no body -----------------------------------------------------------------------


@pytest.mark.parametrize("body", ["", "   "])
def test_empty_body_flag(body: str) -> None:
    row = parse_one(make_record(body=body))
    assert row["has_body"] is False
    assert row["body_words"] == 0
    assert row["doc_id"] == 1234567890


def test_missing_texto_completo_line_means_no_body() -> None:
    chunk = make_record().replace("Texto completo: Body line one.\nBody line two.\n\n", "")
    row = parse_one(chunk)
    assert row["has_body"] is False
    assert row["title"] == "Sample title"


# --- stray spaces ------------------------------------------------------------------


def test_stray_spaces_in_metadata_are_normalized() -> None:
    row = parse_one(
        make_record(
            **{
                "Idioma de la publicación": "En glish",
                "Fecha de publicación": "Aug 29, 202 2",
                "Año de publicación": "20 06",
                "ID del documento de ProQuest": "222 6442937",
            }
        )
    )
    assert row["language_key"] == "english"
    assert row["pub_date"] == date(2022, 8, 29)
    assert row["date_status"] == "ok"
    assert row["pub_year"] == 2006
    assert row["doc_id"] == 2226442937
    assert row["id_status"] == "ok"


def test_stray_spaces_in_body_are_never_touched() -> None:
    body = "En glish  text with   odd spacing."
    row = parse_one(make_record(body=body))
    assert row["body_sha256"] == hashlib.sha256(body.encode()).hexdigest()
    assert row["body_words"] == len(body.split())


def test_compact_removes_all_whitespace_and_casefolds() -> None:
    assert parse.compact(" Per iódicos ") == "periódicos"


# --- dates, years, ids -------------------------------------------------------------


def test_date_year_only_is_flagged_not_nat() -> None:
    row = parse_one(make_record(**{"Fecha de publicación": "2019"}))
    assert row["pub_date"] is None
    assert row["date_status"] == "year_only"
    assert row["date_year"] == 2019


@pytest.mark.parametrize("raw", ["Foo 99, 2022", "Feb 30, 2022", "garbage"])
def test_unparseable_date_is_flagged(raw: str) -> None:
    row = parse_one(make_record(**{"Fecha de publicación": raw}))
    assert row["pub_date"] is None
    assert row["date_status"] == "unparseable"


def test_missing_date_is_flagged() -> None:
    assert parse_one(make_record(**{"Fecha de publicación": None}))["date_status"] == "missing"


def test_unparseable_id_and_year_are_flagged() -> None:
    row = parse_one(
        make_record(**{"ID del documento de ProQuest": "12x4", "Año de publicación": "abcd"})
    )
    assert row["doc_id"] is None
    assert row["id_status"] == "unparseable"
    assert row["pub_year"] is None
    assert row["year_status"] == "unparseable"


def test_parse_date_helper_cases() -> None:
    assert parse.parse_date("Nov 9, 2022") == (date(2022, 11, 9), 2022, "ok")
    assert parse.parse_date(None) == (None, None, "missing")
    assert parse.parse_date("2019") == (None, 2019, "year_only")


# --- provenance --------------------------------------------------------------------


def test_provenance_columns() -> None:
    row = parse.parse_record(make_record(), "ProQuestDocuments-x.txt", 7)
    assert row["source_file"] == "ProQuestDocuments-x.txt"
    assert row["record_index"] == 7


# --- sanity check and parquet ------------------------------------------------------


def write_file(tmp_path: Path, name: str, records: list[str], *, footer: bool = True) -> Path:
    path = tmp_path / name
    path.write_bytes(make_file(records, footer=footer).encode("utf-8"))
    return path


def test_sanity_check_ok_when_records_match_separators(tmp_path: Path) -> None:
    path = write_file(tmp_path, "a.txt", [make_record()] * 3)
    result = parse.sanity_check(path)
    assert result == {
        "source_file": "a.txt",
        "separators": 4,
        "records": 3,
        "footers": 1,
        "odd_rules": 0,
        "ok": True,
    }


def test_sanity_check_fails_without_footer(tmp_path: Path) -> None:
    path = write_file(tmp_path, "b.txt", [make_record()] * 2, footer=False)
    result = parse.sanity_check(path)
    assert result["footers"] == 0
    assert result["ok"] is False


def test_write_parquet_streams_files_and_keeps_the_text(tmp_path: Path) -> None:
    a = write_file(tmp_path, "a.txt", [make_record()] * 2)
    b = write_file(tmp_path, "b.txt", [make_record(materia="X")])
    out = tmp_path / "out" / "records.parquet"
    checks = parse.write_parquet([a, b], out)
    table = pq.read_table(out)
    assert table.num_rows == 5  # 2 + footer, 1 + footer
    assert {"source_file", "record_index", "body_sha256", "body_words"} <= set(table.column_names)
    assert table["text"].to_pylist()[0] == "Body line one.\nBody line two."
    assert [c["ok"] for c in checks] == [True, True]


def test_labels_between_body_and_title_are_metadata_not_body() -> None:
    extra = {
        "e-ISSN": "12345678",
        "columna": "Editorial",
        "Número de acceso": "99",
        "Empresa": "Example Corp",
        "URL": "https://example.test/article",
        "Historial de publicaciones\u00a0": "Example Daily",
        "Nombre del producto": "Example product",
        "Tomo": "12",
        "Año": "2020",
        "Etnicidad": "Example",
        "Duración del clip": "1:00",
    }
    row = parse_one(make_record(materia="Topic A", extra=extra))
    assert row["title"] == "Sample title"
    assert row["has_materia"] is True
    assert row["body_words"] == 6


# --- every field that exists is kept -----------------------------------------------


def test_extra_metadata_labels_get_their_own_column() -> None:
    extra = {
        "URL": "https://example.test/article",
        "Empresa": "Example Corp",
        "Historial de publicaciones": "Example Daily",
        "Lugar": "Springfield",
    }
    row = parse_one(make_record(materia="Topic A; Topic B", extra=extra))
    assert row["subject"] == "Topic A; Topic B"
    assert row["url"] == "https://example.test/article"
    assert row["company"] == "Example Corp"
    assert row["publication_history"] == "Example Daily"
    assert row["location"] == "Springfield"


def test_extra_label_missing_from_a_record_is_none() -> None:
    row = parse_one(make_record())
    assert row["subject"] is None
    assert row["url"] is None


def test_header_fields_before_the_body_are_kept() -> None:
    row = parse_one(make_record())
    assert row["header_url"] == "https://example.test/doc"
    assert row["abstract"] == "Ninguno disponible."
    assert row["links"] == "https://example.test/links"


def test_text_is_the_body_exactly_as_exported() -> None:
    body = 'En glish  text,\n\nwith   odd spacing and a "quote".'
    assert parse_one(make_record(body=body))["text"] == body


def test_footer_and_empty_body_have_no_text() -> None:
    footer = parse_one(parse.split_records(make_file([make_record()]))[-1], index=1)
    assert footer["text"] is None
    assert parse_one(make_record(body="   "))["text"] is None


def test_every_extra_label_and_the_text_are_in_the_schema() -> None:
    assert set(parse.EXTRA_LABELS.values()) <= set(parse.SCHEMA.names)
    assert parse.SCHEMA.names[-1] == "text"
    assert len(set(parse.SCHEMA.names)) == len(parse.SCHEMA.names)


def test_underscore_rule_inside_body_is_reported_not_a_failure(tmp_path: Path) -> None:
    body = "Sign here:\n" + "_" * 38 + "\nThanks."
    path = write_file(tmp_path, "c.txt", [make_record(body=body)])
    result = parse.sanity_check(path)
    assert result["records"] == 1
    assert result["odd_rules"] == 1
    assert result["ok"] is True


# --- found in the audit ------------------------------------------------------------


def test_a_body_paragraph_that_starts_with_a_label_already_read_stays_in_the_body() -> None:
    body = "First paragraph.\n\nEditorial: this paragraph belongs to the body."
    row = parse_one(make_record(body=body, extra={"Editorial": "Example Publisher Inc"}))
    assert row["publisher"] == "Example Publisher Inc"
    assert row["text"] == body
    assert row["title"] == "Sample title"


def test_parse_folder_reads_the_files_in_name_order_and_checks_each(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    raw.mkdir()
    write_file(raw, "b.txt", [make_record()])
    write_file(raw, "a.txt", [make_record(), make_record()])
    (raw / "notes.md").write_text("not an export")
    out = tmp_path / "interim" / "records.parquet"
    checks = parse.parse_folder(raw, out)
    assert [c["source_file"] for c in checks] == ["a.txt", "b.txt"]
    assert all(c["ok"] for c in checks)
    table = pq.read_table(out, columns=["source_file", "record_index"])
    assert table["source_file"].to_pylist() == ["a.txt", "a.txt", "a.txt", "b.txt", "b.txt"]


def test_parse_folder_refuses_a_folder_without_exports(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        parse.parse_folder(tmp_path, tmp_path / "records.parquet")
