# MUON_REFERENCE_ONLY
import numpy as np

from recordio import STATES, encode


def summarize(series, sites, pairs):
    keys = sorted({*sites, *(x for pair in pairs for x in pair)})
    index = {site: i for i, site in enumerate(keys)}
    votes = np.full((len(series), len(keys)), -1, dtype=np.int16)
    for row, (_, ordered, coords) in enumerate(series):
        take = np.asarray([site in index for site in ordered], dtype=bool)
        dst = [index[site] for site in ordered if site in index]
        votes[row, dst] = encode(coords).astype(np.int16).filled(-1)[take]
    nclass = len(STATES)

    def pack(codes, alphabet):
        counts = np.bincount(codes[codes >= 0], minlength=len(alphabet))
        support = int(counts.sum())
        return {"support": support, "mass": {alphabet[i]: int(counts[i]) / support
                 for i in np.flatnonzero(counts)}}

    joints = {}
    double = [x + y for x in STATES for y in STATES]
    for a, b in pairs:
        left, right = votes[:, [index[a], index[b]]].T
        codes = np.where((left >= 0) & (right >= 0), left * nclass + right, -1)
        joints[f"{a},{b}"] = pack(codes, double)
    return {"models": len(series), "sites": {str(s): pack(votes[:, index[s]], STATES)
                                             for s in sites}, "pairs": joints}
