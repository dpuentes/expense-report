import subprocess
import sys
import tempfile
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path

from report.expenses import Expense, ReportError, parse_row, read_expenses, summary

ROW = {"date": "2026-10-03", "description": "Taxi", "amount": "12.50", "currency": "usd"}


def write_csv(text: str, suffix: str = ".csv") -> Path:
    f = tempfile.NamedTemporaryFile("w", suffix=suffix, delete=False, encoding="utf-8")
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

    def test_json_matches_csv(self) -> None:
        js = '[{"date": "2026-10-03", "description": "Taxi", "amount": "12.50", "currency": "usd"}]'
        self.assertEqual(read_expenses(write_csv(js, ".json")), [parse_row(ROW, 2)])

    def test_json_numbers_keep_their_text(self) -> None:
        js = '[{"date": "2026-10-03", "description": "A", "amount": 9.10, "currency": "EUR"},' \
             ' {"date": "2026-10-03", "description": "B", "amount": 12, "currency": "EUR"}]'
        amounts = [str(e.amount) for e in read_expenses(write_csv(js, ".json"))]
        self.assertEqual(amounts, ["9.10", "12"])

    def test_xml_matches_csv(self) -> None:
        xml = ("<expenses><expense><date>2026-10-03</date><description>Taxi</description>"
               "<amount>12.50</amount><currency>usd</currency></expense></expenses>")
        self.assertEqual(read_expenses(write_csv(xml, ".xml")), [parse_row(ROW, 2)])

    def test_extension_is_case_insensitive(self) -> None:
        self.assertEqual(read_expenses(write_csv("[]", ".JSON")), [])

    def test_empty_json(self) -> None:
        self.assertEqual(summary(read_expenses(write_csv("[]", ".json"))), "No expenses.")

    def test_bad_json_value_names_the_line(self) -> None:
        js = '[{"date": "2026-10-03", "description": "A", "amount": "x", "currency": "EUR"}]'
        with self.assertRaisesRegex(ReportError, "line 2"):
            read_expenses(write_csv(js, ".json"))

    def test_unsupported_extension(self) -> None:
        for suffix in (".xlsx", ".txt"):
            with self.assertRaisesRegex(ReportError, r"not supported yet.*\.xlsx"):
                read_expenses(write_csv("", suffix))

    def test_malformed_json(self) -> None:
        with self.assertRaisesRegex(ReportError, "JSON"):
            read_expenses(write_csv("[{", ".json"))

    def test_summary(self) -> None:
        expenses = [parse_row(ROW, 2), parse_row({**ROW, "date": "2026-09-30"}, 3)]
        self.assertEqual(summary(expenses), "2 expenses from 2026-09-30 to 2026-10-03")

    def test_summary_of_nothing(self) -> None:
        self.assertEqual(summary([]), "No expenses.")


class Cli(unittest.TestCase):
    def run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run([sys.executable, "-m", "report", *args], capture_output=True, text=True)

    def test_prints_the_summary(self) -> None:
        out = self.run_cli("data/sample.csv")
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn("expenses from", out.stdout)

    def test_json_file(self) -> None:
        path = write_csv('[{"date": "2026-10-03", "description": "A", "amount": 1, "currency": "EUR"}]', ".json")
        out = self.run_cli(str(path))
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertTrue(out.stdout.startswith("1 expenses from"))

    def test_xlsx_exits_1(self) -> None:
        out = self.run_cli(str(write_csv("", ".xlsx")))
        self.assertEqual(out.returncode, 1)
        self.assertIn("error:", out.stderr)
        self.assertIn("not supported", out.stderr)

    def test_bad_file_exits_1(self) -> None:
        self.assertEqual(self.run_cli("missing.csv").returncode, 1)


if __name__ == "__main__":
    unittest.main()
