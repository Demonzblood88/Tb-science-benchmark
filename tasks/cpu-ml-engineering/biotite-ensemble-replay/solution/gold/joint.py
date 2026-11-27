# MUON_REFERENCE_ONLY
"""Exact matched randomization for the overlapping hypotheses."""

from collections import Counter
from fractions import Fraction
from math import factorial

OPS = ("assemble", "randomize", "combine", "adjust", "stress")


def assemble(data):
    landmarks = {}
    for m, s, value in data["rows"]:
        if value is not None:
            landmarks.setdefault(m, {})[s] = value
    grouped = {}
    for m, sites in sorted(landmarks.items()):
        left = "".join("-" if a not in sites else str(int(sites[a] == x)) for a,b,x,y in data["edges"])
        right = "".join("-" if b not in sites else str(int(sites[b] == y)) for a,b,x,y in data["edges"])
        if not left or not (set(left) | set(right)) - {"-"}:
            continue
        mask = "".join("0" if c == "-" else "1" for c in left + right)
        grouped.setdefault((m % 4, mask), []).append([m,left,right])
    return {"groups": [[block,mask,rows] for (block,mask), rows in sorted(grouped.items())]}


def hits(left, right):
    return tuple(int(x == y == "1") for x,y in zip(left,right))


def add(x,y):
    return tuple(a+b for a,b in zip(x,y))


def combine_dist(x,y):
    out = Counter()
    for left, a in x.items():
        for right, b in y.items():
            out[add(left,right)] += a*b
    return out


def wire(dist):
    return [[list(k), value] for k,value in sorted(dist.items())]


def read(rows):
    return {tuple(key): count for key,count in rows}


def randomize(data):
    return {"kernels": [[b, mask, wire(kernel([x for _,x,_ in rows], [y for _,_,y in rows]))]
                        for b,mask,rows in data["groups"]]}


def packet_stats(groups, width):
    sup = [0] * width
    obs = [0] * width
    expected = [Fraction() for _ in sup]
    for _,mask,rows in groups:
        n = len(rows)
        for i in range(width):
            if mask[i] == mask[width+i] == "1":
                a = sum(left[i] == "1" for _,left,_ in rows)
                b = sum(right[i] == "1" for _,_,right in rows)
                sup[i] += n
                obs[i] += sum(left[i] == right[i] == "1" for _,left,right in rows)
                expected[i] += Fraction(a*b, n)
    return sup, obs, expected


def as_pair(p):
    return None if p is None else [p.numerator, p.denominator]


def combine(data):
    width = data["width"]
    sup, obs, expected = packet_stats(data["groups"], width)
    dist = {(0,)*width: 1}
    for _,_,hist in data["kernels"]:
        dist = combine_dist(dist, read(hist))
    return {"support":sup, "observed":obs, "expect":[as_pair(x) if s else None
                for s,x in zip(sup,expected)], "hist":wire(dist)}


def adjust(data):
    sup, obs = data["support"], data["observed"]
    allowed = [i for i,n in enumerate(sup) if n]
    expected = [Fraction(*x) if x is not None else None for x in data["expect"]]
    out = [None] * len(sup)
    if not allowed:
        return {"tails":out}
    seen = {i:(obs[i]-expected[i])/sup[i] for i in allowed}
    step = {i:0 for i in allowed}
    single = dict(step)
    family = dict(step)
    total = sum(count for _,count in data["hist"])
    for overlap, weight in data["hist"]:
        stats = {i:(overlap[i]-expected[i])/sup[i] for i in allowed}
        maximum = max(stats.values())
        for i in allowed:
            single[i] += weight * (stats[i] >= seen[i])
            family[i] += weight * (maximum >= seen[i])
            step[i] += weight * any(stats[j] >= seen[i] for j in allowed if seen[j] <= seen[i])
    running = 0
    for threshold in sorted(set(seen.values()), reverse=True):
        same = [i for i in allowed if seen[i] == threshold]
        running = max(running, step[same[0]])
        for i in same:
            out[i] = [as_pair(Fraction(x, total)) for x in (single[i],family[i],running)]
    return {"tails":out}


def stress(data):
    edge, drop = data["edge"], data["drop"]
    if edge is None:
        return {"edge":None, "support":0, "tails":None}
    subset = {"width":data["width"], "groups":[row for row in data["groups"] if row[0] != drop],
              "kernels":[row for row in data["kernels"] if row[0] != drop]}
    remixed = combine(subset)
    return {"edge":edge, "support":remixed["support"][edge],
            "tails":adjust(remixed)["tails"][edge]}


def run(stage, data):
    return {"assemble":assemble, "randomize":randomize, "combine":combine,
            "adjust":adjust, "stress":stress}[stage](data)



def kernel(left, right):
    from functools import lru_cache
    multiplicities = Counter(right)
    patterns = tuple(sorted(multiplicities))
    impacts = [[hits(row, pattern) for pattern in patterns] for row in left]

    @lru_cache(None)
    def suffix(counts):
        i = len(left) - sum(counts)
        if i == len(left):
            return Counter({(0,)*len(left[0]):1})
        out = Counter()
        for j, copies in enumerate(counts):
            if copies:
                reduced = list(counts)
                reduced[j] -= 1
                for vector, weight in suffix(tuple(reduced)).items():
                    out[add(impacts[i][j],vector)] += weight * copies
        return out
    return suffix(tuple(multiplicities[x] for x in patterns))
