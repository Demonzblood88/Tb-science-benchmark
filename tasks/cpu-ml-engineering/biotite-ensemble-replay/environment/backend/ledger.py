"""Signed acceptance records for one service instance."""

import hashlib
import hmac
import json
import decision_protocol as decision
import os
from pathlib import Path

from policy import ACTIONS, LANES
from flow import FLOW_OPS, PANELS, check_envelope, plan, sampling_profile
from joint_protocol import JOINT_OPS, branch, joint_plan, shape
from terminal_probe import FILES

STATE = Path("/var/lib/opsd")
ZERO = "0" * 64
LOG = STATE / "actions.jsonl"
KEY = STATE / "key"
DEPLOY = STATE / "deployed"
TERMINAL = STATE / "terminal.json"


def canonical(record):
    return json.dumps(record, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def atomic(path, data):
    scratch = path.with_name("." + path.name + "." + os.urandom(8).hex())
    fd = os.open(scratch, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(data)
    scratch.replace(path)


def signature(key, record):
    return hmac.new(key, canonical(record), "sha256").hexdigest()


def bundle_digest(source):
    return hashlib.sha256(canonical({name: hashlib.sha256(data).hexdigest()
                                     for name, data in source.items()})).hexdigest()


def content_digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def deploy_source(source):
    DEPLOY.mkdir(exist_ok=True, mode=0o700)
    for name, contents in source.items():
        atomic(DEPLOY / name, contents)
    return bundle_digest(source)


def load_source():
    return {name: (DEPLOY / name).read_bytes() for name in FILES}


class Ledger:
    def __init__(self):
        self.key = os.urandom(32)
        atomic(KEY, self.key)
        atomic(LOG, b"")
        self.sequence = 0
        self.previous = ZERO

    def add(self, op, lane, **detail):
        self.sequence += 1
        record = {"seq": self.sequence, "previous": self.previous, "op": op,
                  "lane": lane, "detail": detail, "accepted": op != "wrong-recovery"}
        self.previous = signature(self.key, record)
        record["mac"] = self.previous
        with LOG.open("ab") as stream:
            stream.write(canonical(record) + b"\n")


def audit(digest, panels, joint, decisions):
    key = KEY.read_bytes()
    previous = ZERO
    chain = []
    for seq, row in enumerate(LOG.read_bytes().splitlines(), 1):
        record = json.loads(row)
        mac = record.pop("mac")
        if (record["seq"] != seq or record["previous"] != previous
                or not hmac.compare_digest(mac, signature(key, record))):
            raise ValueError("unsigned or discontinuous receipt")
        previous = mac
        if record["op"] == "reproduce":
            chain.clear()
        elif record["op"] == "restart":
            chain = chain[:1]
            continue
        elif record["op"] == "wrong-recovery":
            if not chain or chain[-1]["op"] != "diagnose":
                raise ValueError("wrong recovery without a diagnosis")
            chain.pop()
            continue
        chain.append(record)

    expected = [("reproduce", None)] + [(op, lane) for lane, _ in enumerate(LANES)
                                        for op in ACTIONS]
    for panel in range(len(PANELS)):
        if panel:
            expected.append(("route", None))
        expected.extend((op, None) for op in FLOW_OPS)
    expected.extend((op, None) for _ in PANELS for op in JOINT_OPS)
    expected.extend((op,None) for op in decision.OPS)
    expected += [("promote", None), ("submit", None)]
    if [(r["op"], r["lane"]) for r in chain] != expected:
        raise ValueError("ordered release gates incomplete")
    if not isinstance(panels, list) or len(panels) != len(PANELS):
        raise ValueError("missing chained panels")
    if not isinstance(joint,list) or len(joint) != len(PANELS):
        raise ValueError("missing joint panels")
    if not isinstance(decisions,list) or len(decisions)!=len(decision.WORK):
        raise ValueError("missing decision artifacts")
    flow_index = 0
    joint_index = 0
    decision_index = 0
    for row in chain:
        action, lane, detail = row["op"], row["lane"], row["detail"]
        if action in ("deploy", "validate", "reconcile", "seal", "promote", "submit"):
            if detail.get("digest") != digest:
                raise ValueError("release used different snapshots")
        if action in ("validate", "reconcile") and not detail.get("clean"):
            raise ValueError("release accepted an unsuccessful validation")
        if action == "recover" and detail != {"family": LANES[lane][4]}:
            raise ValueError("recovery family disagrees with the observed fault")
        if action == "route":
            panel = flow_index // len(FLOW_OPS)
            prior = panels[panel - 1]
            if detail != {"digest": digest, "panel": panel, "profile": sampling_profile(prior),
                          "previous": content_digest(prior[-1])}:
                raise ValueError("route receipt disagrees with the previous calibration")
        if action in FLOW_OPS:
            panel, stage = divmod(flow_index, len(FLOW_OPS))
            history = panels[panel]
            if not isinstance(history, list) or len(history) != len(FLOW_OPS):
                raise ValueError("panel has missing artifacts")
            payload = plan(panel, stage, history, panels[panel - 1] if panel else None)
            output = history[stage]
            check_envelope(payload, output)
            if detail != {"digest": digest, "panel": panel, "input": content_digest(payload),
                          "output": content_digest(output)}:
                raise ValueError("receipt disagrees with the chained artifacts")
            flow_index += 1
        if action in JOINT_OPS:
            panel,j = divmod(joint_index,len(JOINT_OPS))
            history = joint[panel]
            if not isinstance(history,list) or len(history) != len(JOINT_OPS)-1:
                raise ValueError("missing joint artifacts")
            if action == "isolate":
                expected = {"digest":digest,"panel":panel,"block":branch(history),
                            "previous":content_digest(history[3])}
            else:
                payload = joint_plan(panel,action,history,panels)
                output = history[j if j < 4 else j-1]
                shape(payload,output)
                expected = {"digest":digest,"panel":panel,"input":content_digest(payload),
                            "output":content_digest(output)}
            if detail != expected:
                raise ValueError("receipt disagrees with the joint audit artifacts")
            joint_index += 1
        if action in decision.OPS:
            want = {"digest":digest}
            if action == "catalogue":
                want["catalogue"]=content_digest(list(decision.WITNESS_IDS))
            elif action == "receipt":
                want["evidence"]=content_digest(decision.receipts()[decision_index-1])
            elif action == "bind":
                want["rule"]=decisions[0]["rule"]
            elif action == "withdraw":
                want["excluded"]=decision.withdrawal(decisions,panels,joint)
                want["allocation"]=content_digest(decisions[2])
            else:
                payload=decision.build(action,decisions,panels,joint)
                value=decisions[decision.WORK.index(action)]
                decision.shape(payload,value)
                want.update(input=content_digest(payload),output=content_digest(value))
            if detail!=want:
                raise ValueError("receipt disagrees with the downstream decision artifacts")
            decision_index+=1
    return len(chain)
