#!/bin/sh
set -eu
cd "$(dirname "$0")"
PYTHONPATH=src python3.12 -m iris_adapters --adapter jsonl --sink jsonl --output output/normalized.jsonl
