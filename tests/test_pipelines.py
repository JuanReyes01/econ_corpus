"""Tests for the two entry points: each runs the steps of its pipeline in order."""

import pytest

from econ_corpus.clean import __main__ as clean_pipeline
from econ_corpus.raw import __main__ as raw_pipeline


def record(monkeypatch: pytest.MonkeyPatch, pipeline: object) -> list[str]:
    """Replace every step of a pipeline by a note of its name; return the list they fill."""
    ran: list[str] = []
    steps = {name: (lambda name=name: ran.append(name)) for name in pipeline.STEPS}
    monkeypatch.setattr(pipeline, "STEPS", steps)
    return ran


def test_the_raw_pipeline_runs_its_steps_in_order(monkeypatch: pytest.MonkeyPatch) -> None:
    ran = record(monkeypatch, raw_pipeline)
    raw_pipeline.main(["folder/of/exports"])
    assert ran == ["parse", "exclusions", "export", "datasheet"]


def test_the_raw_pipeline_parses_only_when_given_the_exports(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ran = record(monkeypatch, raw_pipeline)
    raw_pipeline.main([])
    assert ran == ["exclusions", "export", "datasheet"]


def test_the_clean_pipeline_runs_its_steps_in_order(monkeypatch: pytest.MonkeyPatch) -> None:
    ran = record(monkeypatch, clean_pipeline)
    clean_pipeline.main()
    assert ran == ["processed", "review_cases", "datasheet_clean", "overview"]


def test_a_step_that_fails_stops_the_pipeline(monkeypatch: pytest.MonkeyPatch) -> None:
    ran = record(monkeypatch, clean_pipeline)

    def fail() -> None:
        msg = "stale"
        raise ValueError(msg)

    monkeypatch.setitem(clean_pipeline.STEPS, "review_cases", fail)
    with pytest.raises(ValueError, match="stale"):
        clean_pipeline.main()
    assert ran == ["processed"]


@pytest.mark.parametrize("pipeline", [raw_pipeline, clean_pipeline])
def test_every_step_is_the_main_of_the_module_it_is_named_after(pipeline: object) -> None:
    for name, step in pipeline.STEPS.items():
        assert step is getattr(pipeline, name).main, name


def test_the_raw_pipeline_takes_one_folder_at_most(monkeypatch: pytest.MonkeyPatch) -> None:
    ran = record(monkeypatch, raw_pipeline)
    with pytest.raises(SystemExit, match="one argument"):
        raw_pipeline.main(["exports", "more"])
    assert ran == []


@pytest.mark.parametrize("flag", ["-h", "--help", "--parse"])
def test_the_raw_pipeline_takes_no_option_for_a_folder(
    monkeypatch: pytest.MonkeyPatch, flag: str
) -> None:
    ran = record(monkeypatch, raw_pipeline)
    with pytest.raises(SystemExit, match="the folder of exports"):
        raw_pipeline.main([flag])
    assert ran == []
