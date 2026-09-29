"""Reproducible fixture ingestion command."""

import argparse
import os
from pathlib import Path

from .adapters.csv_fixture import CsvFixtureAdapter
from .adapters.jsonl_fixture import JsonlFixtureAdapter
from .pipeline import ingest
from .staging import JsonlStaging, PostgresStaging


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate and stage IRIS fixture records")
    parser.add_argument("--adapter", choices=("jsonl", "csv"), default="jsonl")
    parser.add_argument("--input", type=Path)
    parser.add_argument("--sink", choices=("jsonl", "postgres"), default="jsonl")
    parser.add_argument("--output", type=Path, default=Path("output/normalized.jsonl"))
    parser.add_argument("--dsn", default=os.environ.get("DATABASE_URL"))
    args = parser.parse_args(argv)

    source = args.input or Path(
        "fixtures/source_records.jsonl" if args.adapter == "jsonl" else "fixtures/second_source.csv"
    )
    adapter = JsonlFixtureAdapter(source) if args.adapter == "jsonl" else CsvFixtureAdapter(source)
    if args.sink == "postgres":
        if not args.dsn:
            parser.error("--sink postgres requires --dsn or DATABASE_URL")
        sink = PostgresStaging(args.dsn)
    else:
        sink = JsonlStaging(args.output)

    count = ingest(adapter, sink)
    destination = str(args.output) if args.sink == "jsonl" else f"PostGIS batch {sink.batch_id}"
    print(f"staged {count} validated records from {source} to {destination}")
    return 0
