"""Step 3a of the pipeline: write the raw table as a CSV that can be shared.

Input: the parquet written by `parse` (all metadata fields, parsed columns and the text) and
the exclusions parquet, which gives every row one reason.
Output: one UTF-8 CSV with the same columns in the same order, missing values as empty cells.
File footers, repeated ProQuest ids and repeated text (the reasons not marked `in_raw`) are left
out; every other row stays, whatever its reason.

Lives here: the streaming filter and conversion. Does not live here: which reasons leave the
raw table (reasons) or any change to a value. The CSV holds ProQuest-licensed text, so it is
shared directly and never committed.
"""

import json
from pathlib import Path

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.csv as pacsv
import pyarrow.parquet as pq

from econ_corpus.reasons import LEFT_OUT, RECORDS_STAMP, fingerprint, load, rules_fingerprint

BATCH_SIZE = 20_000  # rows per batch; the parquet is read in pieces so it never has to fit in RAM


def _stamp(parquet: Path, reasons: Path, out: Path) -> dict[str, str]:
    """Return what the CSV depends on: the records, the rules, the rows left out, its size."""
    codes = load(parquet, reasons)
    left_out = pc.is_in(codes, value_set=pa.array(LEFT_OUT))
    return {
        "records": (pq.read_schema(reasons).metadata or {})[RECORDS_STAMP.encode()].decode(),
        "rules": rules_fingerprint(),
        "left_out": fingerprint(pa.table({"left_out": left_out})),
        "bytes": str(out.stat().st_size) if out.exists() else "",
    }


def is_current(parquet: Path, reasons: Path, out: Path) -> bool:
    """Tell whether the CSV on disk is the one these records and reasons give."""
    stamp = out.with_suffix(".json")
    stored = json.loads(stamp.read_text(encoding="utf-8")) if stamp.exists() else {}
    return stored == _stamp(parquet, reasons, out)


def write_csv(parquet: Path, reasons: Path, out: Path, batch_size: int = BATCH_SIZE) -> int:
    """Stream the rows that belong to the raw table into a CSV; return how many were written.

    The reasons file has one row per row of the parquet, in the same order. A stamp is written
    next to the CSV, so a later step can tell whether the file still matches its inputs.
    """
    source = pq.ParquetFile(parquet)
    codes = load(parquet, reasons)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.with_suffix(".json").unlink(missing_ok=True)
    written = start = 0
    with pacsv.CSVWriter(out, source.schema_arrow) as writer:
        for batch in source.iter_batches(batch_size=batch_size):
            # Row groups of the two files differ, so line the reasons up by position.
            codes_here = codes.slice(start, batch.num_rows).combine_chunks()
            keep = pc.invert(pc.is_in(codes_here, value_set=pa.array(LEFT_OUT)))
            writer.write_batch(batch.filter(keep))
            written += pc.sum(keep).as_py() or 0
            start += batch.num_rows
    stamp = json.dumps(_stamp(parquet, reasons, out), indent=2) + "\n"
    out.with_suffix(".json").write_text(stamp, encoding="utf-8")
    return written


def main() -> None:
    """Export the raw table at its default location."""
    rows = write_csv(
        Path("data/interim/records.parquet"),
        Path("data/interim/exclusions.parquet"),
        Path("data/processed/econ_corpus_raw.csv"),
    )
    print(f"{rows:,} rows written")  # noqa: T201 (command-line feedback)


if __name__ == "__main__":
    main()
