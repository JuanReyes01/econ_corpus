"""Tests for econ_corpus.check, with the builders replaced by stand-ins."""

from pathlib import Path

import pytest

from econ_corpus import check


def make_paths(tmp_path: Path) -> check.Paths:
    docs = tmp_path / "docs"
    docs.mkdir()
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
    )


@pytest.fixture
def stand_ins(monkeypatch: pytest.MonkeyPatch) -> dict[str, object]:
    """Replace every builder and guard by one that succeeds; a test then breaks one of them."""
    state: dict[str, object] = {
        "current": True,
        "raw": "raw datasheet\n",
        "clean": "clean datasheet\n",
    }
    monkeypatch.setattr(check.reasons, "load", lambda *_: None)
    monkeypatch.setattr(check.manifest, "check", lambda *_: None)
    monkeypatch.setattr(check.export, "is_current", lambda *_: state["current"])

    def raw(_records: Path, _reasons: Path, _template: Path, out: Path, **_: Path) -> None:
        out.write_text(str(state["raw"]), encoding="utf-8")

    def clean(*_: Path, out_md: Path, **__: Path) -> None:
        out_md.write_text(str(state["clean"]), encoding="utf-8")

    monkeypatch.setattr(check.datasheet, "build", raw)
    monkeypatch.setattr(check.datasheet_clean, "build", clean)
    return state


def test_outputs_that_belong_together_pass(tmp_path: Path, stand_ins: dict[str, object]) -> None:
    assert stand_ins
    assert check.stale(make_paths(tmp_path)) == []


def test_each_stale_output_is_named(tmp_path: Path, stand_ins: dict[str, object]) -> None:
    stand_ins |= {"current": False, "clean": "another clean datasheet\n"}
    problems = check.stale(make_paths(tmp_path))
    assert len(problems) == 2
    assert "raw.csv" in problems[0]
    assert "clean.md" in problems[1]


def test_stale_reasons_stop_the_check_at_once(
    tmp_path: Path, stand_ins: dict[str, object], monkeypatch: pytest.MonkeyPatch
) -> None:
    assert stand_ins

    def refuse(*_: Path) -> None:
        msg = "run the exclusions again"
        raise ValueError(msg)

    monkeypatch.setattr(check.reasons, "load", refuse)
    assert check.stale(make_paths(tmp_path)) == ["run the exclusions again"]
