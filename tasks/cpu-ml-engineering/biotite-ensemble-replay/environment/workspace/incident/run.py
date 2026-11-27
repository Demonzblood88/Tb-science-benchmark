"""Stable CLI for the CPU inference service."""

import json
import sys

from extract import coordinate_series
from recordio import read_entry
from summarize import summarize


def main():
    batch = json.load(sys.stdin)
    if isinstance(batch, dict):
        if batch["stage"] in ("identify","selective","allocate","reallocate","certify"):
            from decision import run
        elif batch["stage"] in ("assemble", "randomize", "combine", "adjust", "stress"):
            from joint import run
        else:
            from stages import run
        result = run(batch["stage"], batch["data"])
    else:
        result = summarize_archive(batch)
    json.dump(result, sys.stdout, allow_nan=False, sort_keys=True, separators=(",", ":"))
    sys.stdout.write("\n")


def summarize_archive(batch):
    result = {}
    for request in batch:
        block = read_entry(request["entry"])
        series = coordinate_series(block, request["chain"])
        result[request["id"]] = summarize(series, request["sites"], request["pairs"])
    return result


if __name__ == "__main__":
    main()
