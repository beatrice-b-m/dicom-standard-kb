"""Run one deterministic reference-agent case against a local KB."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from dicom_kb.db.models import read_sqlite
from dicom_kb.eval.runner import (
    run_reference_agent_cases,
    select_agent_regression_cases,
    write_agent_runs,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True, type=Path)
    parser.add_argument("--edition", required=True)
    parser.add_argument("--case", default="agent.ct.required_modules")
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()

    selected_cases = select_agent_regression_cases((args.case,))
    with read_sqlite(args.db) as connection:
        runs = run_reference_agent_cases(
            connection,
            edition=args.edition,
            cases=selected_cases,
        )
    write_agent_runs(args.out, runs)
    print(json.dumps({"runs": len(runs), "output": str(args.out)}, sort_keys=True))


if __name__ == "__main__":
    main()
