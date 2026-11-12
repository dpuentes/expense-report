import subprocess
import sys
import tempfile
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path

from report.expenses import Expense, ReportError, parse_row, read_expenses, summary, totals_by_month

ROW = {"date": "2026-10-03", "description": "Taxi", "amount": "12.50", "currency": "usd"}


def write_csv(text: str) -> Path:
    f = tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, encoding="utf-8")
    f.write(text)
    f.close()
    return Path(f.name)


class ParseRow(unittest.TestCase):
    def test_reads_a_row(self) -> None:
        self.assertEqual(parse_row(ROW, 2), Expense(date(2026, 10, 3), "Taxi", Decimal("12.50"), "USD"))

    def test_bad_date_names_the_line(self) -> None:
        with self.assertRaisesRegex(ReportError, "line 7"):
            parse_row({**ROW, "date": "03/10/2026"}, 7)

    def test_bad_amount(self) -> None:
        with self.assertRaises(ReportError):
            parse_row({**ROW, "amount": "twelve"}, 2)

    def test_bad_currency(self) -> None:
        with self.assertRaisesRegex(ReportError, "3-letter"):
            parse_row({**ROW, "currency": "dollars"}, 2)


class ReadAndSummarise(unittest.TestCase):
    def test_reads_a_file(self) -> None:
        path = write_csv("date,description,amount,currency\n2026-10-03,Taxi,12.50,USD\n2026-10-05,Lunch,9,EUR\n")
        self.assertEqual([e.currency for e in read_expenses(path)], ["USD", "EUR"])

    def test_error_line_counts_the_header(self) -> None:
        path = write_csv("date,description,amount,currency\n2026-10-03,Taxi,x,USD\n")
        with self.assertRaisesRegex(ReportError, "line 2"):
            read_expenses(path)

    def test_summary(self) -> None:
        expenses = [parse_row(ROW, 2), parse_row({**ROW, "date": "2026-09-30"}, 3)]
        self.assertEqual(summary(expenses), "2 expenses from 2026-09-30 to 2026-10-03")

    def test_summary_of_nothing(self) -> None:
        self.assertEqual(summary([]), "No expenses.")

    def test_totals_by_month_sums_per_currency(self) -> None:
        expenses = [
            parse_row(ROW, 2),
            parse_row({**ROW, "amount": "10.00", "date": "2026-10-09"}, 3),
            parse_row({**ROW, "amount": "2.50", "date": "2026-10-20", "currency": "eur"}, 4),
        ]
        self.assertEqual(
            totals_by_month(expenses),
            {"2026-10": {"EUR": Decimal("2.50"), "USD": Decimal("22.50")}},
        )

    def test_totals_by_month_order(self) -> None:
        expenses = [
            parse_row(ROW, 2),
            parse_row({**ROW, "date": "2026-09-01", "currency": "gbp"}, 3),
            parse_row({**ROW, "date": "2026-09-02", "currency": "eur"}, 4),
        ]
        result = totals_by_month(expenses)
        self.assertEqual(list(result), ["2026-09", "2026-10"])
        self.assertEqual(list(result["2026-09"]), ["EUR", "GBP"])

    def test_totals_by_month_of_nothing(self) -> None:
        self.assertEqual(totals_by_month([]), {})


class Cli(unittest.TestCase):
    def run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run([sys.executable, "-m", "report", *args], capture_output=True, text=True)

    def test_prints_the_summary(self) -> None:
        out = self.run_cli("data/sample.csv")
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn("expenses from", out.stdout)

    def test_bad_file_exits_1(self) -> None:
        self.assertEqual(self.run_cli("missing.csv").returncode, 1)

    CSV = (
        "date,description,amount,currency\n"
        "2026-10-03,Taxi,7,GBP\n"
        "2026-09-05,Lunch,9,EUR\n"
        "2026-09-02,Gift,30.50,USD\n"
        "2026-09-09,Tea,3,EUR\n"
    )

    def test_by_month_prints_blocks(self) -> None:
        out = self.run_cli("--by-month", str(write_csv(self.CSV)))
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(
            out.stdout,
            "4 expenses from 2026-09-02 to 2026-10-03\n"
            "2026-09\n  EUR 12.00\n  USD 30.50\n2026-10\n  GBP 7.00\n",
        )

    def test_without_flag_only_summary(self) -> None:
        out = self.run_cli(str(write_csv(self.CSV)))
        self.assertEqual(out.stdout, "4 expenses from 2026-09-02 to 2026-10-03\n")

    def test_by_month_with_no_expenses(self) -> None:
        out = self.run_cli(str(write_csv("date,description,amount,currency\n")), "--by-month")
        self.assertEqual(out.stdout, "No expenses.\n")


if __name__ == "__main__":
    unittest.main()
