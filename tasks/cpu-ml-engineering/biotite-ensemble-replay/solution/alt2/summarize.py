# MUON_REFERENCE_ONLY
from itertools import product

import numpy as np

from recordio import STATES, encode


def summarize(series, sites, pairs):
    queries = list(sites) + [x for pair in pairs for x in pair]
    keys = list(dict.fromkeys(queries))
    key_index = {site: i for i, site in enumerate(keys)}
    # Accumulate in batch with a model x site x state presence tensor.
    tensor = np.zeros((len(series), len(keys), len(STATES)), dtype=np.int32)
    for m, (_, positions, coords) in enumerate(series):
        states = encode(coords).astype(np.int16).filled(-1)
        for k, code in zip(positions, states):
            if k in key_index and code >= 0:
                tensor[m, key_index[k], code] = 1

    def pack(counts, alphabet):
        n = int(counts.sum())
        return {"support": n,
                "mass": {s: int(c) / n for s, c in zip(alphabet, counts.ravel()) if c}}

    total = tensor.sum(axis=0)
    joint_names = [a + b for a, b in product(STATES, repeat=2)]
    return {
        "models": len(series),
        "sites": {str(site): pack(total[key_index[site]], STATES) for site in sites},
        "pairs": {f"{a},{b}": pack(tensor[:, key_index[a], :].T @ tensor[:, key_index[b], :],
                                   joint_names) for a, b in pairs},
    }
