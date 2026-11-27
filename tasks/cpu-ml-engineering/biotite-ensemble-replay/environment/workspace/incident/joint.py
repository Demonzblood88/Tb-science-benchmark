"""Obsolete joint worker, to be repaired for the new replay contract."""


def run(stage, data):
    return {"groups": []} if stage == "assemble" else {}
