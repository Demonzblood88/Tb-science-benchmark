"""Independent archive oracle and real incident witness extraction."""

import collections
import json
import sys
from pathlib import Path

import gemmi
import numpy as np
from biotite.structure.alphabet.encoder import Encoder

ARCHIVE = Path("/opt/seed/tests/structure/data/pdb")
ALPHABET = "acdefghiklmnpqrstvwy"
FIELDS = ("label_asym_id label_seq_id label_atom_id label_alt_id occupancy Cartn_x Cartn_y "
          "Cartn_z pdbx_PDB_model_num auth_asym_id auth_seq_id pdbx_PDB_ins_code")
ATOMS = ("CA", "CB", "N", "C")


def archive(entry):
    return gemmi.cif.read_file(str(ARCHIVE / (entry + ".cif"))).sole_block()


def atoms(block):
    table = block.find("_atom_site.", FIELDS.split())
    return (tuple(row) for row in table)


def layout(block):
    output = collections.defaultdict(list)
    for chain, index, author, number, insert in block.find("_pdbx_poly_seq_scheme.", [
            "asym_id", "seq_id", "pdb_strand_id", "pdb_seq_num", "pdb_ins_code"]):
        output[chain].append((int(index), author, number, insert))
    return output


def grouped(block, chain):
    groups = collections.defaultdict(list)
    all_models = set()
    for label, index, atom, alt, occ, x, y, z, model, author, number, insert in atoms(block):
        model = int(model)
        all_models.add(model)
        if label == chain and index.isdigit() and atom in ATOMS:
            groups[model, int(index)].append((atom, alt, float(occ), (float(x), float(y), float(z))))
    return groups, sorted(all_models)


def choice(records):
    sites = {alt for _, alt, _, _ in records} - {".", "?"}
    score = {alt: sum(occ for _, code, occ, _ in records if code == alt) for alt in sites}
    selected = min(sites, key=lambda alt: (-score[alt], alt)) if sites else None
    result = {}
    for atom in ATOMS:
        options = [(code == selected, occ, xyz) for name, code, occ, xyz in records
                   if name == atom and (code in (".", "?") or code == selected)]
        if options:
            result[atom] = max(options)[-1]
    return result


def states(entry, chain, block=None):
    block = archive(entry) if block is None else block
    ids = sorted({row[0] for row in layout(block)[chain]})
    rows, models = grouped(block, chain)
    out = np.full((len(models), len(ids)), -1, dtype=np.int16)
    encoder = Encoder()
    for i, model in enumerate(models):
        if len(ids) < 3:
            continue
        coords = np.full((4, len(ids), 3), np.nan, dtype=np.float32)
        for j, index in enumerate(ids):
            record = choice(rows[model, index])
            for k, atom in enumerate(ATOMS):
                if atom in record:
                    coords[k, j] = record[atom]
        with np.errstate(invalid="ignore", divide="ignore"):
            encoded = encoder.encode(*coords)
        out[i] = encoded.astype(np.int16).filled(-1)
    return ids, models, out


def oracle(requests):
    result = {}
    for req in requests:
        ids, models, matrix = states(req["entry"], req["chain"])
        pos = {site: i for i, site in enumerate(ids)}
        no_state = np.full(len(models), -1)

        def column(site):
            return matrix[:, pos[site]] if site in pos else no_state

        def distribution(values):
            counts = collections.Counter(values)
            support = sum(counts.values())
            return {"support": support, "mass": {k: v / support for k, v in counts.items()}}

        result[req["id"]] = {
            "models": len(models),
            "sites": {str(site): distribution(ALPHABET[i] for i in column(site) if i >= 0)
                      for site in req["sites"]},
            "pairs": {f"{a},{b}": distribution(ALPHABET[i] + ALPHABET[j]
                      for i, j in zip(column(a), column(b)) if i >= 0 and j >= 0)
                      for a, b in req["pairs"]},
        }
    return result


def describe(entry, chain):
    block = archive(entry)
    identity = layout(block)[chain]
    groups, models = grouped(block, chain)
    ids = sorted({row[0] for row in identity})
    first = models[0]
    observed = {i for i in ids if any(row[0] == "CA" for row in groups[first, i])}
    mismatch = [row for row in identity if row[2] not in (".", "?") and str(row[0]) != row[2]]
    aliases = sorted({row[1] for row in identity})
    alternatives = [i for i in ids if len({r[1] for r in groups[first, i]} - {".", "?"}) > 1]
    return {"entry": entry, "chain": chain, "length": len(ids), "models": len(models),
            "aliases": aliases, "shifted": len(mismatch), "missing": len(ids) - len(observed),
            "alternate_sites": alternatives[:10]}


def inspect_entries(entries):
    for entry in entries:
        block = archive(entry)
        for chain, rows in layout(block).items():
            if len(rows) < 12 or not any(r[0] == chain and r[1].isdigit() and r[2] == "CA"
                                        for r in atoms(block)):
                continue
            print(json.dumps(describe(entry, chain)))


def request(ident, entry, chain, sites, pairs):
    return {"id": ident, "entry": entry, "chain": chain, "sites": sites, "pairs": pairs}


def panel(tag, entry, chain):
    ids, models, matrix = states(entry, chain)
    # Each ordered pair and site is a projection of archived positions.
    # Keep the entire registered chain; pair adjacent and distant observed positions.
    starts = ids[:-1:4]
    pairs = [[site, site + 1] for site in starts]
    pairs.extend([[ids[i], ids[-i-1]] for i in range(1, min(len(ids)//2, 24))])
    return request(tag, entry, chain, ids, pairs)


if __name__ == "__main__":
    inspect_entries(sys.argv[1:])
