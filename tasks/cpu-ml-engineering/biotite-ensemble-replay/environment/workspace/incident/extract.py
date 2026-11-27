"""Load the model coordinate series for one requested chain."""

import numpy as np

from recordio import ATOMS


def coordinate_series(block, chain):
    models = {}
    fields = ["auth_asym_id", "auth_seq_id", "label_atom_id", "Cartn_x", "Cartn_y",
              "Cartn_z", "pdbx_PDB_model_num", "label_seq_id"]
    for asym, author_position, atom, x, y, z, model, position in block.find("_atom_site.", fields):
        if asym != chain or position in (".", "?") or atom not in ATOMS:
            continue
        by_site = models.setdefault(int(model), {})
        by_site.setdefault(int(author_position), {}).setdefault(atom, (float(x), float(y), float(z)))
    out = []
    for model, by_site in sorted(models.items()):
        positions = sorted(by_site)
        coords = np.full((len(positions), 4, 3), np.nan, dtype=np.float32)
        for i, pos in enumerate(positions):
            for atom, xyz in by_site[pos].items():
                coords[i, ATOMS.index(atom)] = xyz
        out.append((model, positions, coords))
    return out
