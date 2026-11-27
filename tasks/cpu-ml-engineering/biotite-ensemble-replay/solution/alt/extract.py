# MUON_REFERENCE_ONLY
from itertools import groupby

import numpy as np

from recordio import ATOMS, identity_columns, model_ids


def coordinate_series(block, chain):
    sites = sorted({int(r[1]) for r in identity_columns(block) if r[0] == chain})
    lookup = {site: row for row, site in enumerate(sites)}
    models = model_ids(block)
    buffers = {model: np.full((len(sites), len(ATOMS), 3), np.nan, dtype=np.float32)
               for model in models}
    table = block.get_mmcif_category("_atom_site.", raw=True)
    keys = ("label_asym_id", "label_seq_id", "label_atom_id", "label_alt_id",
            "occupancy", "Cartn_x", "Cartn_y", "Cartn_z", "pdbx_PDB_model_num")
    records = sorted((int(model), int(pos), atom, alt, float(o), (float(x), float(y), float(z)))
                     for cid, pos, atom, alt, o, x, y, z, model in zip(*(table[k] for k in keys))
                     if cid == chain and pos.isdecimal() and int(pos) in lookup and atom in ATOMS)
    for (model, pos), items in groupby(records, key=lambda r: r[:2]):
        rows = list(items)
        by_alt = {}
        for _, _, _, alt, occupancy, _ in rows:
            if alt not in (".", "?"):
                by_alt[alt] = by_alt.get(alt, 0) + occupancy
        choices = sorted(by_alt, key=lambda alt: (-round(by_alt[alt], 8), alt))
        chosen = choices[0] if choices else ""
        for atom_index, atom in enumerate(ATOMS):
            eligible = [(alt == chosen, occ, xyz) for _, _, name, alt, occ, xyz in rows
                        if name == atom and alt in (".", "?", chosen)]
            if eligible:
                buffers[model][lookup[pos], atom_index] = max(eligible)[2]
    return [(model, sites, buffers[model]) for model in models]
