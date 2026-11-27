# MUON_REFERENCE_ONLY
"""Joint replay via multiset enumeration, packed polynomials, and integer scores."""

from collections import Counter, defaultdict
from fractions import Fraction
from math import factorial, lcm, prod


def assemble(data):
    at_site = defaultdict(dict)
    for model,site,value in data["rows"]:
        if value is not None:
            at_site[site][model] = value
    ids = sorted(set().union(*(set(series) for series in at_site.values())))
    columns = [[at_site[edge[side]] for edge in data["edges"]] for side in (0,1)]
    signatures = [[edge[side+2] for edge in data["edges"]] for side in (0,1)]
    groups = defaultdict(list)
    for model in ids:
        roles = []
        for cols,targets in zip(columns,signatures):
            roles.append("".join(str(int(column[model]==state)) if model in column else "-"
                                 for column,state in zip(cols,targets)))
        mask = "".join("0" if char=="-" else "1" for role in roles for char in role)
        if "1" in mask:
            groups[model%4,mask].append([model,*roles])
    return {"groups":[[b,m,values] for (b,m),values in sorted(groups.items())]}


def randomize(data):
    def distribution(rows):
        width = len(rows[0][1])
        copies = Counter(right for _,_,right in rows)
        reorderings = prod(factorial(n) for n in copies.values())
        weights = Counter()
        vector = [0]*width
        keys = tuple(copies)
        shifts = [[tuple(i for i in range(width) if left[i]==right[i]=="1") for right in keys]
                  for _,left,_ in rows]

        def visit(level):
            if level == len(rows):
                weights[tuple(vector)] += reorderings
                return
            for right,positions in zip(keys,shifts[level]):
                if copies[right]:
                    copies[right] -= 1
                    for i in positions:
                        vector[i] += 1
                    visit(level+1)
                    for i in positions:
                        vector[i] -= 1
                    copies[right] += 1
        visit(0)
        return [[list(v),w] for v,w in sorted(weights.items())]

    return {"kernels":[[b,m,distribution(rows)] for b,m,rows in data["groups"]]}


def pair(x):
    return [x.numerator,x.denominator]


def combine(data):
    width = data["width"]
    radix = 1 + sum(len(rows) for _,_,rows in data["groups"])
    powers = [radix**i for i in range(width)]
    packed = {0:1}
    for b,m,weights in data["kernels"]:
        stencil = [(sum(c*place for c,place in zip(v,powers)),w) for v,w in weights]
        following = defaultdict(int)
        for k,p in packed.items():
            for offset,q in stencil:
                following[k+offset] += p*q
        packed = following
    vectors = {tuple(k//place % radix for place in powers):w for k,w in packed.items()}
    support = [0]*width
    observed = [0]*width
    expectation = [Fraction(0) for _ in range(width)]
    for b,m,rows in data["groups"]:
        for i in range(width):
            values = Counter(l[i]+r[i] for _,l,r in rows if "-" not in l[i]+r[i])
            n = sum(values.values())
            if n:
                support[i] += n
                observed[i] += values["11"]
                expectation[i] += Fraction((values["10"]+values["11"])*(values["01"]+values["11"]),n)
    return {"support":support,"observed":observed,
            "expect":[pair(mu) if n else None for mu,n in zip(expectation,support)],
            "hist":[[list(k),v] for k,v in sorted(vectors.items())]}


def adjust(data):
    indices = [i for i,n in enumerate(data["support"]) if n]
    result = [None]*len(data["support"])
    if not indices:
        return {"tails":result}
    denominators = {i:data["expect"][i][1]*data["support"][i] for i in indices}
    scale = lcm(*denominators.values())

    def score(counts,i):
        x,d = data["expect"][i]
        return (counts[i]*d-x)*(scale//denominators[i])

    thresholds = {i:score(data["observed"],i) for i in indices}
    trials = [({i:score(counts,i) for i in indices},w) for counts,w in data["hist"]]
    total = sum(w for _,w in trials)
    raw = {}
    single, family = {},{}
    for threshold in set(thresholds.values()):
        active = [i for i in indices if thresholds[i] <= threshold]
        raw[threshold] = sum(w for s,w in trials if max(s[i] for i in active) >= threshold)
        family[threshold] = sum(w for s,w in trials if max(s.values()) >= threshold)
    for i,t in thresholds.items():
        single[i] = sum(w for s,w in trials if s[i] >= t)
        counts = (single[i],family[t],max(v for u,v in raw.items() if u>=t))
        result[i] = [pair(Fraction(v,total)) for v in counts]
    return {"tails":result}


def stress(data):
    i = data["edge"]
    if i is None:
        return {"edge":None,"support":0,"tails":None}
    block = data["drop"]
    remaining = {**data, **{key:[entry for entry in data[key] if entry[0]!=block]
                           for key in ("groups","kernels")}}
    output = combine(remaining)
    return {"edge":i,"support":output["support"][i],"tails":adjust(output)["tails"][i]}


def run(stage,data):
    return {"assemble":assemble,"randomize":randomize,"combine":combine,
            "adjust":adjust,"stress":stress}[stage](data)
