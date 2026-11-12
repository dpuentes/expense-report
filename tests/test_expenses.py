import subprocess
import sys
import tempfile
import unittest
import zipfile
from datetime import date
from decimal import Decimal
from pathlib import Path

from report.expenses import Expense, ReportError, parse_row, read_expenses, summary

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


class Cli(unittest.TestCase):
    def run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run([sys.executable, "-m", "report", *args], capture_output=True, text=True)

    def test_prints_the_summary(self) -> None:
        out = self.run_cli("data/sample.csv")
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn("expenses from", out.stdout)

    def test_bad_file_exits_1(self) -> None:
        self.assertEqual(self.run_cli("missing.csv").returncode, 1)


def write_file(suffix: str, text: str) -> Path:
    f = tempfile.NamedTemporaryFile("w", suffix=suffix, delete=False, encoding="utf-8")
    f.write(text)
    f.close()
    return Path(f.name)


JSON_OK = (
    '[{"date": "2026-10-03", "description": "Taxi", "amount": 12.50, "currency": "usd"},'
    ' {"date": "2026-10-05", "description": "Lunch", "amount": "9", "currency": "EUR"}]'
)
XML_OK = (
    "<expenses>"
    "<expense><date>2026-10-03</date><description>Taxi</description><amount>12.50</amount><currency>usd</currency></expense>"
    "<expense><date>2026-10-05</date><description>Lunch</description><amount>9</amount><currency>EUR</currency></expense>"
    "</expenses>"
)
EXPECTED = [
    Expense(date(2026, 10, 3), "Taxi", Decimal("12.50"), "USD"),
    Expense(date(2026, 10, 5), "Lunch", Decimal("9"), "EUR"),
]


def write_xlsx(rows: list[list[object]], inline: bool = False) -> Path:
    shared: list[str] = []
    xml_rows = []
    for r, row in enumerate(rows, start=1):
        cells = []
        for c, value in enumerate(row):
            ref = f"{'ABCD'[c]}{r}"
            if isinstance(value, str) and inline:
                cells.append(f'<c r="{ref}" t="inlineStr"><is><t>{value}</t></is></c>')
            elif isinstance(value, str):
                shared.append(value)
                cells.append(f'<c r="{ref}" t="s"><v>{len(shared) - 1}</v></c>')
            else:
                cells.append(f'<c r="{ref}"><v>{value}</v></c>')
        xml_rows.append(f'<row r="{r}">{"".join(cells)}</row>')
    ns = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    sheet = f'<worksheet xmlns="{ns}"><sheetData>{"".join(xml_rows)}</sheetData></worksheet>'
    sst = f'<sst xmlns="{ns}">{"".join(f"<si><t>{s}</t></si>" for s in shared)}</sst>'
    f = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False)
    f.close()
    with zipfile.ZipFile(f.name, "w") as z:
        z.writestr("[Content_Types].xml", "<Types/>")
        z.writestr("xl/workbook.xml", f'<workbook xmlns="{ns}"/>')
        z.writestr("xl/worksheets/sheet1.xml", sheet)
        z.writestr("xl/sharedStrings.xml", sst)
    return Path(f.name)


HEADER = ["date", "description", "amount", "currency"]


class Formats(unittest.TestCase):
    def test_uppercase_csv_extension(self) -> None:
        path = write_file(".CSV", "date,description,amount,currency\n2026-10-03,Taxi,12.50,USD\n")
        self.assertEqual(len(read_expenses(path)), 1)

    def test_json(self) -> None:
        self.assertEqual(read_expenses(write_file(".json", JSON_OK)), EXPECTED)

    def test_json_number_is_decimal(self) -> None:
        self.assertEqual(str(read_expenses(write_file(".json", JSON_OK))[0].amount), "12.50")

    def test_json_bad_amount_names_line(self) -> None:
        text = JSON_OK.replace('"9"', '"x"')
        with self.assertRaisesRegex(ReportError, "line 3"):
            read_expenses(write_file(".json", text))

    def test_json_invalid(self) -> None:
        for text in ("{not json", '{"date": "2026-10-03"}'):
            with self.assertRaises(ReportError):
                read_expenses(write_file(".json", text))

    def test_xml(self) -> None:
        self.assertEqual(read_expenses(write_file(".xml", XML_OK)), EXPECTED)

    def test_xml_missing_field_and_bad_date(self) -> None:
        with self.assertRaisesRegex(ReportError, "line 3"):
            read_expenses(write_file(".xml", XML_OK.replace("<amount>9</amount>", "")))
        with self.assertRaisesRegex(ReportError, "line 2"):
            read_expenses(write_file(".xml", XML_OK.replace("2026-10-03", "bad")))

    def test_xml_malformed(self) -> None:
        with self.assertRaises(ReportError):
            read_expenses(write_file(".xml", "<expenses><expense>"))

    def test_xlsx(self) -> None:
        rows = [HEADER, ["2026-10-03", "Taxi", 12.5, "usd"], ["2026-10-05", "Lunch", 9, "EUR"]]
        self.assertEqual(read_expenses(write_xlsx(rows)), EXPECTED)

    def test_xlsx_inline_strings(self) -> None:
        rows = [HEADER, ["2026-10-03", "Taxi", 12.5, "usd"], ["2026-10-05", "Lunch", 9, "EUR"]]
        self.assertEqual(read_expenses(write_xlsx(rows, inline=True)), EXPECTED)

    def test_xlsx_bad_currency_names_row(self) -> None:
        rows = [HEADER, ["2026-10-03", "Taxi", 12.5, "usd"], ["2026-10-05", "Lunch", 9, "EURO"]]
        with self.assertRaisesRegex(ReportError, "line 3"):
            read_expenses(write_xlsx(rows))

    def test_xlsx_not_a_zip(self) -> None:
        with self.assertRaises(ReportError):
            read_expenses(write_file(".xlsx", "plain text"))

    def test_unsupported_extension(self) -> None:
        for suffix in (".txt", ".xls"):
            with self.assertRaisesRegex(ReportError, "unsupported"):
                read_expenses(write_file(suffix, "x"))


class CliFormats(unittest.TestCase):
    def run_cli(self, path: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run([sys.executable, "-m", "report", str(path)], capture_output=True, text=True)

    def test_each_format(self) -> None:
        rows = [HEADER, ["2026-10-03", "Taxi", 12.5, "usd"]]
        for path in (write_file(".json", JSON_OK), write_file(".xml", XML_OK), write_xlsx(rows)):
            out = self.run_cli(path)
            self.assertEqual(out.returncode, 0, out.stderr)
            self.assertIn("expenses from", out.stdout)

    def test_unsupported_exits_1(self) -> None:
        self.assertEqual(self.run_cli(write_file(".txt", "x")).returncode, 1)


if __name__ == "__main__":
    unittest.main()
