"""Stage 2b of the pipeline: write the raw table as a CSV that can be shared.

Input: the parquet written by `parse` (all metadata fields, parsed columns and the text) and
the exclusions parquet, which gives every row one reason.
Output: one UTF-8 CSV with the same columns in the same order, missing values as empty cells.
File footers and repeated ProQuest ids (the reasons not marked `in_raw`) are left out; every
other row stays, whatever its reason, so the CSV is the raw table with one row per id.

Lives here: the streaming filter and conversion. Does not live here: which reasons leave the
raw table (exclusions) or any change to a value. The CSV holds ProQuest-licensed text, so it is
shared directly and never committed.
"""

from pathlib import Path

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.csv as pacsv
import pyarrow.parquet as pq

from econ_corpus.reasons import LEFT_OUT

BATCH_SIZE = 20_000  # rows per batch; the parquet is read in pieces so it never has to fit in RAM


def write_csv(parquet: Path, reasons: Path, out: Path, batch_size: int = BATCH_SIZE) -> int:
    """Stream the rows that belong to the raw table into a CSV; return how many were written.

    The reasons file has one row per row of the parquet, in the same order.
    """
    source = pq.ParquetFile(parquet)
    codes = pq.read_table(reasons, columns=["reason"])["reason"]
    total = source.metadata.num_rows
    if len(codes) != total:
        msg = f"{reasons.name} has {len(codes)} rows but {parquet.name} has {total}"
        raise ValueError(msg)
    out.parent.mkdir(parents=True, exist_ok=True)
    written = start = 0
    with pacsv.CSVWriter(out, source.schema_arrow) as writer:
        for batch in source.iter_batches(batch_size=batch_size):
            # Row groups of the two files differ, so line the reasons up by position.
            codes_here = codes.slice(start, batch.num_rows).combine_chunks()
            keep = pc.invert(pc.is_in(codes_here, value_set=pa.array(LEFT_OUT)))
            writer.write_batch(batch.filter(keep))
            written += pc.sum(keep).as_py() or 0
            start += batch.num_rows
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
