# MUON_REFERENCE_ONLY
"""Collect a complete chain for each deposited model."""

from collections import defaultdict

import numpy as np

from recordio import ATOMS, identity_columns, model_ids


def coordinate_series(block, chain):
    positions = sorted({int(row[1]) for row in identity_columns(block) if row[0] == chain})
    index = {site: i for i, site in enumerate(positions)}
    records = defaultdict(list)
    fields = ["label_asym_id", "label_seq_id", "label_atom_id", "label_alt_id", "occupancy",
              "Cartn_x", "Cartn_y", "Cartn_z", "pdbx_PDB_model_num"]
    for asym, site, atom, alt, occ, x, y, z, model in block.find("_atom_site.", fields):
        if asym == chain and site.isdecimal() and int(site) in index and atom in ATOMS:
            records[int(model), int(site)].append((atom, alt, float(occ), tuple(map(float, (x,y,z)))))
    output = []
    for model in model_ids(block):
        coords = np.full((len(positions), 4, 3), np.nan, dtype=np.float32)
        for site in positions:
            entries = records[model, site]
            total = defaultdict(float)
            for _, alt, occ, _ in entries:
                if alt not in (".", "?"):
                    total[alt] += occ
            selected = min(total, key=lambda alt: (-total[alt], alt)) if total else None
            allowed = sorted((alt == selected, occ, xyz, atom) for atom, alt, occ, xyz in entries
                             if alt in (".", "?") or alt == selected)
            for _, _, xyz, atom in allowed:
                coords[index[site], ATOMS.index(atom)] = xyz
        output.append((model, positions, coords))
    return output
