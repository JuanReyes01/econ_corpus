"""Pipeline 1, in order: from the ProQuest exports to the shared raw table and its datasheet.

    uv run python -m econ_corpus.raw [FOLDER_OF_EXPORTS]

Input: the folder of `.txt` exports (only to parse them again) and the review files.
Output: everything listed in README.md of this folder, step by step.

Lives here: the order of the steps. Does not live here: what each step does (its module).

Step 1 (`parse`) runs only when the folder of exports is given: it takes about five minutes
and the records it writes are kept, so the other steps start from them. `parse` reads the
folder from the command line itself.
"""

import sys

from econ_corpus.raw import datasheet, exclusions, export, parse

STEPS = {
    "parse": parse.main,  # step 1: exports -> data/interim/records.parquet
    "exclusions": exclusions.main,  # step 2: one reason per row
    "export": export.main,  # step 3a: the raw table as CSV
    "datasheet": datasheet.main,  # step 3b: the datasheet of the raw table
}


def main(argv: list[str]) -> None:
    """Run the steps in order; `parse` only when `argv` names the folder of exports."""
    if len(argv) > 1 or any(arg.startswith("-") for arg in argv):
        usage = "one argument at most, the folder of exports: python -m econ_corpus.raw [FOLDER]"
        raise SystemExit(usage)
    steps = [name for name in STEPS if name != "parse" or argv]
    for number, name in enumerate(steps, start=1):
        print(f"[raw {number}/{len(steps)}] {name}", flush=True)  # noqa: T201
        STEPS[name]()


if __name__ == "__main__":
    main(sys.argv[1:])
