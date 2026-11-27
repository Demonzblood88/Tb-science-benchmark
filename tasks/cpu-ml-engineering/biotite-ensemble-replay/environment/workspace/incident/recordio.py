"""Access to raw archive records and the upstream CPU encoder."""

from pathlib import Path

import gemmi
import numpy as np
from biotite.structure.alphabet.encoder import Encoder

ATOMS = ("CA", "CB", "N", "C")
STATES = "acdefghiklmnpqrstvwy"
ROOT = Path(__file__).resolve().parents[1]


def read_entry(entry):
    return gemmi.cif.read_file(str(ROOT / "tests/structure/data/pdb" / (entry + ".cif"))).sole_block()


def model_ids(block):
    column = block.find_values("_atom_site.pdbx_PDB_model_num")
    return sorted({int(value) for value in column})


def identity_columns(block):
    return [
        tuple(row) for row in block.find("_pdbx_poly_seq_scheme.", [
            "asym_id", "seq_id", "pdb_strand_id", "pdb_seq_num", "pdb_ins_code"
        ])
    ]


def encode(coords):
    """Input (polymer positions, CA/CB/N/C, xyz); output a masked vector."""
    if len(coords) < 3:
        return np.ma.masked_all(len(coords), dtype=np.int32)
    with np.errstate(invalid="ignore", divide="ignore"):
        return Encoder().encode(*np.asarray(coords, dtype=np.float32).transpose(1, 0, 2))
