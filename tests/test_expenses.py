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
        csv_path = write_csv("date,description,amount,currency\n2026-10-03,Taxi,9.10,USD\n2026-10-05,Lunch,9,EUR\n")
        js = '[{"date":"2026-10-03","description":"Taxi","amount":9.10,"currency":"USD"},'
        js += '{"date":"2026-10-05","description":"Lunch","amount":9,"currency":"EUR"}]'
        got = read_expenses(write_csv(js, ".json"))
        self.assertEqual(got, read_expenses(csv_path))
        self.assertEqual(got[0].amount, Decimal("9.10"))

    def test_xml_matches_csv(self) -> None:
        def rec(d: str, desc: str, a: str, c: str) -> str:
            return f"<expense><date>{d}</date><description>{desc}</description><amount>{a}</amount><currency>{c}</currency></expense>"
        xml = "<expenses>" + rec("2026-10-03", "Taxi", "9.10", "USD") + rec("2026-10-05", "Lunch", "9", "EUR") + "</expenses>"
        csv_path = write_csv("date,description,amount,currency\n2026-10-03,Taxi,9.10,USD\n2026-10-05,Lunch,9,EUR\n")
        self.assertEqual(read_expenses(write_csv(xml, ".xml")), read_expenses(csv_path))

    def test_extension_is_case_insensitive(self) -> None:
        self.assertEqual(read_expenses(write_csv("[]", ".JSON")), [])

    def test_unsupported_extensions(self) -> None:
        with self.assertRaisesRegex(ReportError, "Excel.*not supported yet"):
            read_expenses(write_csv("", ".xlsx"))
        with self.assertRaisesRegex(ReportError, r"\.txt"):
            read_expenses(write_csv("", ".txt"))

    def test_json_error_names_the_line(self) -> None:
        js = '[{"date":"2026-10-03","description":"a","amount":1,"currency":"USD"},'
        js += '{"date":"2026-10-03","description":"b","amount":"x","currency":"USD"}]'
        with self.assertRaisesRegex(ReportError, "line 3"):
            read_expenses(write_csv(js, ".json"))

    def test_empty_json_and_xml(self) -> None:
        for text, suffix in (("[]", ".json"), ("<expenses/>", ".xml")):
            got = read_expenses(write_csv(text, suffix))
            self.assertEqual(got, [])
            self.assertEqual(summary(got), "No expenses.")

    def test_malformed_json_and_xml(self) -> None:
        for text, suffix in (("[{", ".json"), ('{"a": 1}', ".json"), ("<a>", ".xml")):
            with self.assertRaises(ReportError):
                read_expenses(write_csv(text, suffix))

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

    def test_reads_a_json_file(self) -> None:
        path = write_csv('[{"date":"2026-10-03","description":"a","amount":1,"currency":"USD"}]', ".json")
        out = self.run_cli(str(path))
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(out.stdout.splitlines()[0], "1 expenses from 2026-10-03 to 2026-10-03")

    def test_bad_file_exits_1(self) -> None:
        self.assertEqual(self.run_cli("missing.csv").returncode, 1)


if __name__ == "__main__":
    unittest.main()
