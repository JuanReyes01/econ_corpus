"""Tests for econ_corpus.check, with the builders replaced by stand-ins."""

from pathlib import Path

import pyarrow as pa
import pytest

from econ_corpus import check

TABLE = "a,b\n1,2\n"
COUNTS = "Reason,Records\nkept,1\n"
REASONS = "source_file,record_index,doc_id,reason\na.txt,0,1,kept\n"


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def make_paths(tmp_path: Path) -> check.Paths:
    docs = tmp_path / "docs"
    docs.mkdir()
    for name in ("review", "tables", "figures"):
        (tmp_path / name).mkdir()
    (tmp_path / "tables" / "counts.csv").write_text(TABLE, encoding="utf-8")
    (tmp_path / "tables" / "exclusion_counts.csv").write_text(COUNTS, encoding="utf-8")
    (tmp_path / "raw_reasons.csv").write_text(REASONS, encoding="utf-8")
    for name in ("raw.template.md", "clean.template.md"):
        (docs / name).write_text("template\n", encoding="utf-8")
    (docs / "raw.md").write_text("raw datasheet\n", encoding="utf-8")
    (docs / "clean.md").write_text("clean datasheet\n", encoding="utf-8")
    return check.Paths(
        records=tmp_path / "records.parquet",
        reasons=tmp_path / "exclusions.parquet",
        review=tmp_path / "review",
        raw_csv=tmp_path / "raw.csv",
        clean=tmp_path / "clean",
        raw_template=docs / "raw.template.md",
        raw_md=docs / "raw.md",
        clean_template=docs / "clean.template.md",
        clean_md=docs / "clean.md",
        tables=tmp_path / "tables",
        figures=tmp_path / "figures",
        raw_reasons=tmp_path / "raw_reasons.csv",
    )


@pytest.fixture
def stand_ins(monkeypatch: pytest.MonkeyPatch) -> dict[str, object]:
    """Replace every builder and guard by one that succeeds; a test then breaks one of them."""
    state: dict[str, object] = {"current": True, "raw": "raw datasheet\n"}
    state |= {"clean": "clean datasheet\n", "table": TABLE}
    state |= {"counts": COUNTS, "reasons": REASONS}
    monkeypatch.setattr(check.reasons, "load", lambda *_: pa.chunked_array([["kept"]]))
    monkeypatch.setattr(check.exclusions, "reason_counts", lambda _: state["counts"])
    monkeypatch.setattr(check.datasheet, "write_csv", lambda text, out: write(out, str(text)))

    def raw_reasons(_records: Path, _reasons: Path, out: Path) -> None:
        out.write_text(str(state["reasons"]), encoding="utf-8")

    monkeypatch.setattr(check.export, "write_reasons", raw_reasons)
    monkeypatch.setattr(check.manifest, "check", lambda *_: None)
    monkeypatch.setattr(check.export, "is_current", lambda *_: state["current"])
    monkeypatch.setattr(check.review_cases, "build", lambda *_: None)

    def raw(_records: Path, _reasons: Path, _template: Path, out: Path, **side: Path) -> None:
        out.write_text(str(state["raw"]), encoding="utf-8")
        side["tables_dir"].mkdir(parents=True, exist_ok=True)
        (side["tables_dir"] / "counts.csv").write_text(str(state["table"]), encoding="utf-8")

    def clean(*_: Path, out_md: Path, **__: Path) -> None:
        out_md.write_text(str(state["clean"]), encoding="utf-8")

    monkeypatch.setattr(check.datasheet, "build", raw)
    monkeypatch.setattr(check.datasheet_clean, "build", clean)
    return state


def test_outputs_that_belong_together_pass(tmp_path: Path, stand_ins: dict[str, object]) -> None:
    assert stand_ins
    assert check.stale(make_paths(tmp_path)) == []


def test_each_stale_output_is_named(tmp_path: Path, stand_ins: dict[str, object]) -> None:
    stand_ins |= {"current": False, "clean": "another clean datasheet\n", "table": "a,b\n9,9\n"}
    problems = check.stale(make_paths(tmp_path))
    assert [problem.split()[0] for problem in problems] == ["raw.csv", "clean.md", "counts.csv"]


def test_stale_reasons_stop_the_check_at_once(
    tmp_path: Path, stand_ins: dict[str, object], monkeypatch: pytest.MonkeyPatch
) -> None:
    assert stand_ins

    def refuse(*_: Path) -> None:
        msg = "run the exclusions again"
        raise ValueError(msg)

    monkeypatch.setattr(check.reasons, "load", refuse)
    assert check.stale(make_paths(tmp_path)) == ["run the exclusions again"]


def test_stale_reasons_of_the_raw_table_and_stale_counts_are_named(
    tmp_path: Path, stand_ins: dict[str, object]
) -> None:
    stand_ins |= {"counts": "Reason,Records\nkept,2\n", "reasons": REASONS + "a.txt,1,2,kept\n"}
    problems = check.stale(make_paths(tmp_path))
    assert [problem.split()[0] for problem in problems] == [
        "raw_reasons.csv",
        "exclusion_counts.csv",
    ]


def test_a_file_that_no_step_writes_any_more_is_named(
    tmp_path: Path, stand_ins: dict[str, object]
) -> None:
    assert stand_ins
    paths = make_paths(tmp_path)
    (paths.tables / "old_table.csv").write_text("a\n", encoding="utf-8")
    assert [problem.split()[0] for problem in check.stale(paths)] == ["old_table.csv"]
