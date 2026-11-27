# MUON_REFERENCE_ONLY
from collections import Counter

import numpy as np

from recordio import STATES, encode


def summarize(series, sites, pairs):
    singles = {site: Counter() for site in sites}
    joints = {(a,b): Counter() for a,b in pairs}
    for _, positions, coords in series:
        encoded = encode(coords)
        votes = {site: STATES[int(x)] for site, x, masked in
                 zip(positions, encoded.data, np.ma.getmaskarray(encoded)) if not masked}
        for site, counter in singles.items():
            if site in votes:
                counter[votes[site]] += 1
        for (a,b), counter in joints.items():
            if a in votes and b in votes:
                counter[votes[a] + votes[b]] += 1

    def pack(counter):
        n = sum(counter.values())
        return {"support": n, "mass": {k: v / n for k, v in counter.items()}}

    return {"models": len(series),
            "sites": {str(site): pack(counts) for site, counts in singles.items()},
            "pairs": {f"{a},{b}": pack(counts) for (a,b), counts in joints.items()}}
