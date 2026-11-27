"""Former reducer for the archive follow-up jobs."""

from recordio import STATES, encode, read_entry
from extract import coordinate_series


def run(stage, data):
    if stage != "capture":
        raise ValueError("follow-up stage unavailable")
    series = coordinate_series(read_entry(data["entry"]), data["chain"])
    models = [(m, dict(zip(sites, map(int, encode(coords).filled()))))
              for m, sites, coords in series]
    return {"shards": [[[m, site, STATES[observed[site]] if site in observed else None]
                        for m, observed in models for site in sorted(sites)]
                       for sites in data["partitions"]]}
