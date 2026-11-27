"""Summarize the state series for request sites and pairs."""

from recordio import STATES, encode


def summarize(series, sites, pairs):
    counts = len(series)
    first = series[0] if counts else None
    states = {}
    if first:
        _, positions, coords = first
        states = dict(zip(positions, (STATES[int(code)] for code in encode(coords).filled())))
    singles = {}
    for site in sites:
        value = states.get(site)
        singles[str(site)] = {"support": int(value is not None), "mass": {value: 1.0} if value else {}}
    joints = {}
    for a, b in pairs:
        value = states.get(a, "") + states.get(b, "")
        joints[f"{a},{b}"] = {"support": int(len(value) == 2), "mass": {value: 1.0} if len(value) == 2 else {}}
    return {"models": counts, "sites": singles, "pairs": joints}
