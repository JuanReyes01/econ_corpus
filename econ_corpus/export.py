"""Stage 2b of the pipeline: write the raw table as a CSV that can be shared.

Input: the parquet written by `parse` (all metadata fields, parsed columns and the text).
Output: one UTF-8 CSV with the same columns in the same order, one row per parquet row
(file footers included), missing values as empty cells.

Lives here: the streaming conversion. Does not live here: any change to the values. The
CSV holds ProQuest-licensed text, so it is shared directly and never committed.
"""

from pathlib import Path

import pyarrow.csv as pacsv
import pyarrow.parquet as pq

BATCH_SIZE = 20_000  # rows per batch; the parquet is read in pieces so it never has to fit in RAM


def write_csv(parquet: Path, out: Path, batch_size: int = BATCH_SIZE) -> int:
    """Stream the parquet into a CSV and return the number of rows written."""
    out.parent.mkdir(parents=True, exist_ok=True)
    source = pq.ParquetFile(parquet)
    rows = 0
    with pacsv.CSVWriter(out, source.schema_arrow) as writer:
        for batch in source.iter_batches(batch_size=batch_size):
            writer.write_batch(batch)
            rows += batch.num_rows
    return rows


def main() -> None:
    """Export the raw table at its default location."""
    rows = write_csv(
        Path("data/interim/records.parquet"), Path("data/processed/econ_corpus_raw.csv")
    )
    print(f"{rows:,} rows written")  # noqa: T201 (command-line feedback)


if __name__ == "__main__":
    main()
