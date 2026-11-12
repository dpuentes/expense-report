"""Read expenses from a CSV file (date,description,amount,currency) and summarise them."""

from __future__ import annotations

import csv
import json
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path


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


def _rows_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _rows_json(path: Path) -> list[dict[str, str]]:
    try:
        with path.open(encoding="utf-8") as f:
            items = json.load(f, parse_float=str, parse_int=str)
    except ValueError as exc:
        raise ReportError(f"invalid JSON ({exc})") from exc
    if not isinstance(items, list) or not all(isinstance(i, dict) for i in items):
        raise ReportError("invalid JSON (expected a list of objects)")
    return [{k: v if isinstance(v, str) else str(v) for k, v in i.items()} for i in items]


def _rows_xml(path: Path) -> list[dict[str, str]]:
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError as exc:
        raise ReportError(f"invalid XML ({exc})") from exc
    return [{c.tag: c.text or "" for c in item} for item in root.findall("expense")]


READERS = {".csv": _rows_csv, ".json": _rows_json, ".xml": _rows_xml}


def read_expenses(path: Path) -> list[Expense]:
    reader = READERS.get(path.suffix.lower())
    if reader is None:
        raise ReportError(f"file type {path.suffix!r} is not supported yet (Excel .xlsx included); use .csv, .json or .xml")
    return [parse_row(row, n) for n, row in enumerate(reader(path), start=2)]


def summary(expenses: list[Expense]) -> str:
    if not expenses:
        return "No expenses."
    days = sorted(e.day for e in expenses)
    return f"{len(expenses)} expenses from {days[0].isoformat()} to {days[-1].isoformat()}"
