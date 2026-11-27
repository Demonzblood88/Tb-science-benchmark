"""Build, bound and independently replay the joint audit packets."""

from fractions import Fraction

from flow import PANELS, plan
from joint_reference import OPS, run

JOINT_OPS = OPS[:4] + ("isolate", "stress")


def choose(packet):
    combined = packet[2]
    tails = packet[3]["tails"]
    eligible = [i for i,(n,t) in enumerate(zip(combined["support"],tails)) if n and t is not None]
    if not eligible:
        return None, {}
    edge = min(eligible, key=lambda i:(Fraction(*tails[i][2]), i))
    width = len(tails)
    blocks = {}
    for b, mask, rows in packet[0]["groups"]:
        if mask[edge] == mask[width+edge] == "1":
            blocks[b] = blocks.get(b,0) + len(rows)
    return edge, blocks


def branch(history):
    _, available = choose(history)
    return min(available, key=lambda b:(-available[b], b)) if available else None


def joint_plan(panel, op, history, panels):
    prev = panels[panel-1] if panel else None
    cohort = plan(panel, 3, panels[panel], prev)["data"]
    edges = [row[0] for row in panels[panel][3]["tables"]]
    width = len(edges)
    if op == "assemble":
        data = {"rows":cohort["rows"], "edges":edges}
    elif op == "randomize":
        data = {"groups":history[0]["groups"], "width":width}
    elif op == "combine":
        data = {"width":width, "groups":history[0]["groups"], "kernels":history[1]["kernels"]}
    elif op == "adjust":
        data = history[2]
    elif op == "stress":
        edge, _ = choose(history)
        data = {"width":width, "groups":history[0]["groups"], "kernels":history[1]["kernels"],
                "edge":edge, "drop":branch(history)}
    else:
        raise ValueError("unknown joint audit operation")
    return {"stage":op, "panel":PANELS[panel][0], "data":data}


def integer(x, hi=256):
    return type(x) is int and 0 <= x <= hi


def pair(x, prob=False):
    return (isinstance(x,list) and len(x) == 2 and type(x[0]) is int and type(x[1]) is int
            and 0 <= x[0] and 0 < x[1] and (not prob or x[0] <= x[1]))


def hist(rows, width):
    if not isinstance(rows,list) or not 1 <= len(rows) <= 8192:
        return False
    keys = []
    for record in rows:
        if not isinstance(record,list) or len(record) != 2:
            return False
        vec,weight = record
        if (not isinstance(vec,list) or len(vec) != width or not all(map(integer,vec))
                or not integer(weight, 2**256) or weight == 0):
            return False
        keys.append(tuple(vec))
    return sorted(set(keys)) == keys


def shape(payload, output):
    op, data = payload["stage"], payload["data"]
    bad = ValueError(f"invalid {op} response envelope")
    if not isinstance(output,dict):
        raise bad
    if op == "assemble":
        width = len(data["edges"])
        groups = output.get("groups")
        if set(output) != {"groups"} or not isinstance(groups,list) or len(groups) > 32:
            raise bad
        models = set()
        keys = []
        for group in groups:
            if not isinstance(group,list) or len(group) != 3:
                raise bad
            block,mask,rows = group
            if (type(block) is not int or block not in (1,3) or not isinstance(mask,str)
                    or len(mask) != 2*width or set(mask)-{"0","1"} or "1" not in mask
                    or not isinstance(rows,list) or not 1 <= len(rows) <= 10):
                raise bad
            keys.append((block,mask))
            mids = []
            for row in rows:
                if not isinstance(row,list) or len(row) != 3:
                    raise bad
                m,left,right = row
                if (not integer(m,10000) or m % 4 != block or m in models
                        or any(not isinstance(s,str) or len(s) != width or set(s)-{"0","1","-"}
                               for s in (left,right))
                        or "".join("0" if c == "-" else "1" for c in left+right) != mask):
                    raise bad
                models.add(m)
                mids.append(m)
            if mids != sorted(mids):
                raise bad
        if keys != sorted(set(keys)):
            raise bad
    elif op == "randomize":
        kernels = output.get("kernels")
        if (set(output) != {"kernels"} or not isinstance(kernels,list)
                or len(kernels) != len(data["groups"])):
            raise bad
        for row,group in zip(kernels,data["groups"]):
            if (not isinstance(row,list) or len(row) != 3 or row[:2] != group[:2]
                    or not hist(row[2],data["width"])):
                raise bad
    elif op == "combine":
        width = data["width"]
        if set(output) != {"hist","support","observed","expect"} or not hist(output["hist"],width):
            raise bad
        if any(not isinstance(output[k],list) or len(output[k]) != width
               for k in ("support","observed","expect")):
            raise bad
        for n,k,e in zip(*(output[x] for x in ("support","observed","expect"))):
            if not integer(n) or not integer(k,n) or (n and not pair(e)) or (not n and e is not None):
                raise bad
    elif op == "adjust":
        tails = output.get("tails")
        if set(output) != {"tails"} or not isinstance(tails,list) or len(tails) != len(data["support"]):
            raise bad
        for n,t in zip(data["support"],tails):
            if (n and not triple(t)) or (not n and t is not None):
                raise bad
    elif op == "stress":
        n = output.get("support")
        t = output.get("tails")
        if (set(output) != {"edge","support","tails"}
                or (output["edge"] is not None and not integer(output["edge"],4))
                or output["edge"] != data["edge"]
                or not integer(n) or (n and not triple(t)) or (not n and t is not None)):
            raise bad


def triple(items):
    return isinstance(items,list) and len(items) == 3 and all(pair(p,True) for p in items)


def oracle_joint(payload):
    return run(payload["stage"],payload["data"])


def replay_joint(execute, panels):
    results = []
    for i in range(len(PANELS)):
        history = []
        for op in OPS:
            payload = joint_plan(i,op,history,panels)
            result = execute(payload)
            shape(payload,result)
            history.append(result)
        results.append(history)
    return results


def project(op, value):
    def exact(p):
        return Fraction(*p) if p is not None else None

    if op == "combine":
        return {**value,"expect":[exact(p) for p in value["expect"]]}
    if op == "adjust":
        return [None if row is None else list(map(exact,row)) for row in value["tails"]]
    if op == "stress":
        tails = value["tails"]
        return {**value,"tails":list(map(exact,tails)) if tails is not None else None}
    return value


def joint_metrics(left, right):
    by_op = {op:0 for op in OPS}
    for l,r in zip(left,right,strict=True):
        for op,a,b in zip(OPS,l,r,strict=True):
            by_op[op] += project(op,a) != project(op,b)
    return {"stages":len(OPS)*len(PANELS),"mismatches":sum(by_op.values()),"by_op":by_op}
