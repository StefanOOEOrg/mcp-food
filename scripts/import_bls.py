"""Import BLS 4.0 (Max Rubner-Institut, CC BY 4.0) into food.items.

Run from the repo root: venv/bin/python scripts/import_bls.py <BLS_4_0_Daten_2025_DE.xlsx>
(the table is downloadable from blsdb.de). Existing BLS rows are updated in place.
"""
import sys
from pathlib import Path

import openpyxl

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import db  # noqa: E402  pylint: disable=wrong-import-position

CODES = {
    "ENERCC": "kcal_100g", "PROT625": "protein_100g", "CHO": "carbs_100g", "FAT": "fat_100g",
    "FIBT": "fiber_100g", "SUGAR": "sugar_100g", "FASAT": "satfat_100g", "NACL": "salt_100g",
    "ALC": "alcohol_100g",
}


def column_map(header: tuple) -> dict[str, int]:
    """Our column names → the value column of each BLS component (header starts with its code)."""
    out = {}
    for idx, title in enumerate(header):
        code = str(title or "").split(" ", maxsplit=1)[0]
        if code in CODES and "[" in str(title):
            out[CODES[code]] = idx
    return out


def number(value) -> float | None:
    """The cell as a number with two decimals, None when it is empty or not numeric."""
    try:
        return round(float(value), 2)
    except (TypeError, ValueError):
        return None


def main() -> None:
    """Read the first sheet and upsert every row as a BLS item."""
    sheet = openpyxl.load_workbook(sys.argv[1], read_only=True).worksheets[0]
    rows = sheet.iter_rows(values_only=True)
    cols = column_map(next(rows))
    db.init_schema()
    count = 0
    for row in rows:
        if not row[0]:
            continue
        item = {"source": "bls", "source_ref": row[0], "name": row[1], "brand": None}
        item.update({name: number(row[idx]) for name, idx in cols.items()})
        db.upsert_item(item)
        count += 1
    print(f"BLS: {count} foods imported")


if __name__ == "__main__":
    main()
