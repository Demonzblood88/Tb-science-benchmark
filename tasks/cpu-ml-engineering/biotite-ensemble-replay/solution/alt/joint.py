# MUON_REFERENCE_ONLY
"""Independent replay with forward labeled assignment and product measures."""

import itertools
from collections import Counter
from fractions import Fraction
from operator import itemgetter
from math import prod


def bits(row, edge, side):
    site = edge[side]
    code = row.get(site)
    return "-" if code is None else ("1" if code == edge[side+2] else "0")


def assemble(data):
    models = {m:{} for m,_,_ in data["rows"]}
    for m,s,value in data["rows"]:
        models[m][s] = value
    tagged = []
    for m,symbols in models.items():
        l,r = ("".join(bits(symbols, edge, side) for edge in data["edges"]) for side in (0,1))
        coverage = "".join(str(int(p != "-")) for p in l+r)
        if "1" in coverage:
            tagged.append((m%4,coverage,m,l,r))
    return {"groups":[[block,mask,[list(row[2:]) for row in rows]]
                      for (block,mask),rows in itertools.groupby(sorted(tagged),key=itemgetter(0,1))]}


def randomize(data):
    result = []
    for block,mask,rows in data["groups"]:
        last = (1<<len(rows))-1
        frontier = {0:Counter({(0,)*data["width"]:1})}
        for _,left,_ in rows:
            nxt = {}
            for used,dist in frontier.items():
                fresh = last ^ used
                while fresh:
                    bit = fresh & -fresh
                    fresh -= bit
                    right = rows[bit.bit_length()-1][2]
                    destination = nxt.setdefault(used|bit,Counter())
                    inc = [int(a == b == "1") for a,b in zip(left,right)]
                    for vector,weight in dist.items():
                        destination[tuple(a+b for a,b in zip(vector,inc))] += weight
            frontier = nxt
        result.append([block,mask,[[list(v),w] for v,w in sorted(frontier[last].items())]])
    return {"kernels":result}


def encode(p):
    return [p.numerator,p.denominator]


def combine(data):
    width = data["width"]
    support,observed,mean = [],[],[]
    for i in range(width):
        pairs = [[(l[i],r[i]) for _,l,r in records
                  if l[i] != "-" and r[i] != "-"]
                 for _,_,records in data["groups"]]
        n = sum(map(len,pairs))
        support.append(n)
        observed.append(sum(row == ("1","1") for subset in pairs for row in subset))
        mean.append(encode(sum((Fraction(sum(a=="1" for a,b in subset)*
                                         sum(b=="1" for a,b in subset),len(subset))
                                  for subset in pairs if subset),Fraction())) if n else None)
    masses = Counter()
    for parts in itertools.product(*(hist for _,_,hist in data["kernels"])):
        vector = tuple(sum(v[i] for v,w in parts) for i in range(width))
        masses[vector] += prod(w for v,w in parts)
    return {"support":support,"observed":observed,"expect":mean,
            "hist":[[list(vector),mass] for vector,mass in sorted(masses.items())]}


def adjust(data):
    supported = [(i,Fraction(*e),n) for i,(n,e) in enumerate(zip(data["support"],data["expect"])) if n]
    rows = [None] * len(data["support"])
    if not supported:
        return {"tails":rows}

    def scores(vector):
        return tuple((vector[i]-mu)/n for i,mu,n in supported)

    goal = scores(data["observed"])
    trials = [(scores(vector),weight) for vector,weight in data["hist"]]
    total = sum(weight for vector,weight in trials)
    surviving = set(range(len(goal)))
    previous = 0
    ordered = sorted(enumerate(goal),key=lambda entry:-entry[1])
    for threshold, group in itertools.groupby(ordered,key=itemgetter(1)):
        ties = [j for j,score in group]
        family = sum(w for s,w in trials if any(score >= threshold for score in s))
        step = sum(w for s,w in trials if any(s[j] >= threshold for j in surviving))
        previous = max(step,previous)
        for j in ties:
            single = sum(w for s,w in trials if s[j] >= threshold)
            rows[supported[j][0]] = [encode(Fraction(v,total)) for v in (single,family,previous)]
        surviving.difference_update(ties)
    return {"tails":rows}


def stress(data):
    selected = data["edge"]
    if selected is None:
        return {"edge":None,"support":0,"tails":None}
    kept = {"width":data["width"]}
    for field in ("groups","kernels"):
        kept[field] = [row for row in data[field] if row[0] != data["drop"]]
    changed = combine(kept)
    return {"edge":selected,"support":changed["support"][selected],
            "tails":adjust(changed)["tails"][selected]}


def run(stage,data):
    return dict(assemble=assemble,randomize=randomize,combine=combine,
                adjust=adjust,stress=stress)[stage](data)
