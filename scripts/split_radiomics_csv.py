"""
Split a radiomics image CSV into morph, intensity, and texture tables.

Given an input file such as ``radiomics__T1CE(BMETS-T1CE)__image.csv`` with columns
``PatientID, radVar1, radVar2, ...``, this script writes three copies:

- ``__morph.csv`` : PatientID + radVar1  .. radVar29
- ``__int.csv``   : PatientID + radVar30 .. radVar79
- ``__text.csv``  : PatientID + radVar80 .. last radVar column
"""

import argparse
from pathlib import Path
from typing import Dict, Optional

import pandas as pd


def _radvar_columns(start: int, end: int) -> list:
    return [f"radVar{i}" for i in range(start, end + 1)]

input_csv = r"C:\Mahdi\PhD\ProjetElodie\data\csv\latest\radiomics__T1CE(BMETS-T1CE)__image.csv"
output_dir = r"C:\Mahdi\PhD\ProjetElodie\data\csv\latest"
input_csv = Path(input_csv)
if not input_csv.exists():
    raise FileNotFoundError(f"Input CSV not found: {input_csv}")

output_dir = Path(output_dir) if output_dir else input_csv.parent
output_dir.mkdir(parents=True, exist_ok=True)

df = pd.read_csv(input_csv)

if "PatientID" not in df.columns:
    raise ValueError('Input CSV must contain a "PatientID" column.')

morph_cols = ["PatientID"] + _radvar_columns(1, 29)
int_cols = ["PatientID"] + _radvar_columns(30, 79)

radvar_nums = sorted(
    int(col.replace("radVar", ""))
    for col in df.columns
    if col.startswith("radVar")
)
if not radvar_nums:
    raise ValueError("Input CSV must contain radVar columns.")
text_cols = ["PatientID"] + _radvar_columns(80, radvar_nums[-1])

missing = {
    "morph": [c for c in morph_cols if c not in df.columns],
    "int": [c for c in int_cols if c not in df.columns],
    "text": [c for c in text_cols if c not in df.columns],
}
for name, cols in missing.items():
    if cols:
        raise ValueError(f"Missing columns for {name} copy: {cols[:5]}{'...' if len(cols) > 5 else ''}")

stem = input_csv.name.replace("__image.csv", "")
outputs = {
    "morph": output_dir / f"{stem}__morph.csv",
    "int": output_dir / f"{stem}__int.csv",
    "text": output_dir / f"{stem}__text.csv",
}

csv_kwargs = {"index": False, "na_rep": "NaN"}
df[morph_cols].to_csv(outputs["morph"], **csv_kwargs)
df[int_cols].to_csv(outputs["int"], **csv_kwargs)
df[text_cols].to_csv(outputs["text"], **csv_kwargs)


