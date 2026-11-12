"""Read expenses from a CSV, JSON or XML file (date,description,amount,currency) and summarise them."""

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
            data = json.load(f, parse_float=str)
    except json.JSONDecodeError as exc:
        raise ReportError(f"invalid JSON ({exc})") from exc
    if not isinstance(data, list) or not all(isinstance(r, dict) for r in data):
        raise ReportError("JSON must be an array of objects")
    return [{k: v if isinstance(v, str) else str(v) for k, v in r.items()} for r in data]


def _rows_xml(path: Path) -> list[dict[str, str]]:
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError as exc:
        raise ReportError(f"invalid XML ({exc})") from exc
    return [{field.tag: field.text or "" for field in item} for item in root]


READERS = {".csv": _rows_csv, ".json": _rows_json, ".xml": _rows_xml}


def read_expenses(path: Path) -> list[Expense]:
    ext = path.suffix.lower()
    if ext == ".xlsx":
        raise ReportError("Excel (.xlsx) is not supported yet")
    if ext not in READERS:
        raise ReportError(f"unsupported file extension {ext!r}; use .csv, .json or .xml")
    return [parse_row(row, n) for n, row in enumerate(READERS[ext](path), start=2)]


def summary(expenses: list[Expense]) -> str:
    if not expenses:
        return "No expenses."
    days = sorted(e.day for e in expenses)
    return f"{len(expenses)} expenses from {days[0].isoformat()} to {days[-1].isoformat()}"
