"""Minimal streaming .xlsx reader (first worksheet) using only the standard library.

Used for K6, which ships only as .xlsx; this avoids adding openpyxl as a dependency.
"""
from __future__ import annotations

import re
import zipfile
from collections.abc import Iterator
from pathlib import Path
from xml.etree.ElementTree import iterparse

NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"


def _col_index(ref: str) -> int:
    letters = re.match(r"[A-Z]+", ref).group(0)
    n = 0
    for ch in letters:
        n = n * 26 + (ord(ch) - 64)
    return n - 1


def iter_rows(path: str | Path, sheet: str = "xl/worksheets/sheet1.xml", max_rows: int | None = None) -> Iterator[list]:
    with zipfile.ZipFile(path) as z:
        shared: list[str] = []
        if "xl/sharedStrings.xml" in z.namelist():
            with z.open("xl/sharedStrings.xml") as f:
                for _, el in iterparse(f, events=("end",)):
                    if el.tag == NS + "si":
                        shared.append("".join(t.text or "" for t in el.iter(NS + "t")))
                        el.clear()
        with z.open(sheet) as f:
            n = 0
            for _, el in iterparse(f, events=("end",)):
                if el.tag != NS + "row":
                    continue
                cells: dict[int, object] = {}
                for c in el.findall(NS + "c"):
                    ref, typ = c.get("r"), c.get("t")
                    v = c.find(NS + "v")
                    if typ == "s" and v is not None:
                        val: object = shared[int(v.text)]
                    elif typ == "inlineStr":
                        val = "".join(t.text or "" for t in c.iter(NS + "t"))
                    elif v is not None:
                        val = v.text
                    else:
                        val = None
                    cells[_col_index(ref)] = val
                el.clear()
                width = max(cells) + 1 if cells else 0
                yield [cells.get(i) for i in range(width)]
                n += 1
                if max_rows and n >= max_rows:
                    return


def read_xlsx(path: str | Path, max_rows: int | None = None):
    import pandas as pd

    rows = iter_rows(path, max_rows=max_rows)
    header = [str(h) if h is not None else f"col{i}" for i, h in enumerate(next(rows))]
    data = [r + [None] * (len(header) - len(r)) for r in rows]
    return pd.DataFrame([r[: len(header)] for r in data], columns=header)
