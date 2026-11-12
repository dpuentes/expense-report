"""python3 -m report <file.csv>"""

from __future__ import annotations

import sys
from pathlib import Path

from report.expenses import ReportError, read_expenses, summary, totals_by_month


def main(argv: list[str]) -> int:
    by_month = "--by-month" in argv
    args = [a for a in argv if a != "--by-month"]
    if len(args) != 1 or args[0].startswith("--"):
        print("usage: python3 -m report [--by-month] <file.csv>", file=sys.stderr)
        return 2
    try:
        expenses = read_expenses(Path(args[0]))
    except (OSError, ReportError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(summary(expenses))
    if by_month:
        for month, currencies in totals_by_month(expenses).items():
            print(month)
            for currency, total in currencies.items():
                print(f"  {currency} {total:.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
