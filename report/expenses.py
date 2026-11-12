"""Read expenses from a CSV, JSON, XLSX or XML file (date,description,amount,currency) and summarise them."""

from __future__ import annotations

import csv
import json
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path


_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"


@dataclass(frozen=True)
class Expense:
    day: date
    description: str
    amount: Decimal
    currency: str


class ReportError(ValueError):
    """A row the report cannot use; the message names its line in the file."""


def parse_row(row: dict[str, str], line: int) -> Expense:
    try:
        day = date.fromisoformat(row["date"].strip())
        amount = Decimal(row["amount"].strip())
    except (KeyError, AttributeError, ValueError, InvalidOperation) as exc:
        raise ReportError(f"line {line}: cannot read date or amount ({exc})") from exc
    currency = (row.get("currency") or "").strip().upper()
    if len(currency) != 3 or not currency.isalpha():
        raise ReportError(f"line {line}: currency must be a 3-letter code, got {currency!r}")
    return Expense(day, (row.get("description") or "").strip(), amount, currency)


def _csv_rows(path: Path) -> list[tuple[int, dict[str, str]]]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(enumerate(csv.DictReader(f), start=2))


def _json_rows(path: Path) -> list[tuple[int, dict[str, str]]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"), parse_float=Decimal)
    except ValueError as exc:
        raise ReportError(f"invalid JSON ({exc})") from exc
    if not isinstance(data, list):
        raise ReportError("JSON must be a list of objects")
    rows = []
    for n, item in enumerate(data, start=2):
        if not isinstance(item, dict):
            raise ReportError(f"line {n}: record must be an object")
        rows.append((n, {k: str(v) for k, v in item.items() if v is not None}))
    return rows


def _xml_rows(path: Path) -> list[tuple[int, dict[str, str]]]:
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError as exc:
        raise ReportError(f"invalid XML ({exc})") from exc
    return [(n, {child.tag: child.text or "" for child in rec}) for n, rec in enumerate(root, start=2)]


def _xlsx_strings(z: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in z.namelist():
        return []
    root = ET.fromstring(z.read("xl/sharedStrings.xml"))
    return ["".join(t.text or "" for t in si.iter(_NS + "t")) for si in root.iter(_NS + "si")]


def _xlsx_cell(cell: ET.Element, strings: list[str]) -> tuple[str, str]:
    col = "".join(ch for ch in cell.get("r", "") if ch.isalpha())
    if cell.get("t") == "inlineStr":
        return col, "".join(t.text or "" for t in cell.iter(_NS + "t"))
    v = cell.find(_NS + "v")
    text = (v.text or "") if v is not None else ""
    return col, strings[int(text)] if cell.get("t") == "s" else text


def _xlsx_rows(path: Path) -> list[tuple[int, dict[str, str]]]:
    try:
        with zipfile.ZipFile(path) as z:
            strings = _xlsx_strings(z)
            sheet = ET.fromstring(z.read("xl/worksheets/sheet1.xml"))
    except (zipfile.BadZipFile, KeyError, ET.ParseError, IndexError, ValueError) as exc:
        raise ReportError(f"invalid xlsx file ({exc})") from exc
    table = [(int(r.get("r", 0)), dict(_xlsx_cell(c, strings) for c in r.iter(_NS + "c")))
             for r in sheet.iter(_NS + "row")]
    if not table:
        return []
    names = table[0][1]
    return [(n, {names[k]: v for k, v in cells.items() if k in names}) for n, cells in table[1:]]


_READERS = {".csv": _csv_rows, ".json": _json_rows, ".xml": _xml_rows, ".xlsx": _xlsx_rows}


def read_rows(path: Path) -> list[tuple[int, dict[str, str]]]:
    reader = _READERS.get(path.suffix.lower())
    if reader is None:
        raise ReportError(f"unsupported file format {path.suffix!r} (use .csv, .json, .xlsx or .xml)")
    return reader(path)


def read_expenses(path: Path) -> list[Expense]:
    return [parse_row(row, n) for n, row in read_rows(path)]


def summary(expenses: list[Expense]) -> str:
    if not expenses:
        return "No expenses."
    days = sorted(e.day for e in expenses)
    return f"{len(expenses)} expenses from {days[0].isoformat()} to {days[-1].isoformat()}"
