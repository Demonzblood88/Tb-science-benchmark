# MUON_REFERENCE_ONLY
import math
from collections import defaultdict

import numpy as np

from recordio import ATOMS


def coordinate_series(block, chain):
    scheme = block.get_mmcif_category("_pdbx_poly_seq_scheme.", raw=True)
    ids = sorted({int(i) for c, i in zip(scheme["asym_id"], scheme["seq_id"]) if c == chain})
    pos = {i: j for j, i in enumerate(ids)}
    find = block.find_values
    data = np.array(block.find("_atom_site.", ["label_asym_id", "label_seq_id",
               "label_atom_id", "label_alt_id", "occupancy", "Cartn_x", "Cartn_y",
               "Cartn_z", "pdbx_PDB_model_num"]), dtype=object)
    selected = {}
    for model in sorted({int(i) for i in find("_atom_site.pdbx_PDB_model_num")}):
        selected[model] = np.full((len(ids), 4, 3), np.nan, np.float32)
    mask = (data[:, 0] == chain) & np.isin(data[:, 1], [str(x) for x in ids])
    mask &= np.isin(data[:, 2], ATOMS)
    rows = data[mask]
    codes = defaultdict(list)
    for _, site, _, alt, occ, *_coords, model in rows:
        if alt not in (".", "?"):
            codes[int(model), int(site), alt].append(float(occ))
    alternate = {}
    for (model, site, alt), occ in codes.items():
        rank = (-math.fsum(occ), alt)
        if (model, site) not in alternate or rank < alternate[model, site]:
            alternate[model, site] = rank
    best = {}
    for _, site, atom, alt, occ, x, y, z, model in rows:
        model, site = int(model), int(site)
        preferred = alternate.get((model, site), (0, ""))[1]
        if alt not in (".", "?", preferred):
            continue
        key = (model, site, atom)
        value = (alt == preferred, float(occ), (float(x), float(y), float(z)))
        if key not in best or value > best[key]:
            best[key] = value
    for (model, site, atom), (_, _, xyz) in best.items():
        selected[model][pos[site], ATOMS.index(atom)] = xyz
    return [(model, ids, coords) for model, coords in selected.items()]
