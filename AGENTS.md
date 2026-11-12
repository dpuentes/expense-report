# Expense report

A small command-line report over a CSV of expenses: `python3 -m report data/sample.csv`.
Standard library only. This file is the map of the repo: you do not need to explore beyond it.

## Map (the whole codebase is 3 files)
| File | Holds | Public names |
|---|---|---|
| `report/expenses.py` | Parsing and every calculation. Pure functions, no printing. | `Expense(day, description, amount, currency)`, `ReportError`, `parse_row(row, line)`, `read_expenses(path)`, `summary(expenses)` |
| `report/__main__.py` | The CLI: reads `argv`, calls `expenses.py`, prints. No calculations. | `main(argv) -> int` |
| `tests/test_expenses.py` | All tests. Classes `ParseRow`, `ReadAndSummarise`, `Cli`. Helpers `write_csv(text)` and `Cli.run_cli(*args)`. | |

`data/sample.csv` has 8 rows in EUR, GBP and USD. It is read-only: never edit it.

## Commands
- Test: the TEST_CMD in factory.conf, exactly as written (must pass before any PR). There is no linter.
- Run it once to see red, once to see green. Do not re-run a passing suite.

## Output contract (do not break it)
- Without new flags, the output for an existing input stays byte for byte the same, plus only what the ticket adds.
- First line is always `summary()`: `8 expenses from 2026-09-02 to 2026-10-19`, or `No expenses.`
- Money prints with two decimals (`9` prints as `9.00`). Currencies are never converted or mixed.
- Lists print in a stable order: sorted by currency code, months ascending as `YYYY-MM`.
- Exit codes: 0 ok, 1 bad input (`error: ...` on stderr), 2 wrong usage.

## Conventions
- Python 3.10+. Nothing outside the standard library is installed. Never add an import that is not stdlib.
- Money is `Decimal`, never float. Dates are `datetime.date`.
- Every behaviour change gets a unittest in `tests/`, written BEFORE the implementation.
- Tests check behaviour (return values, CLI stdout), never private helpers. Reuse `write_csv` and `run_cli`.
- One test per behaviour in the ticket, plus the empty case. Do not add tests the ticket does not need.
- Keep functions under 30 lines. Parsing lives in `report/expenses.py`, printing in `report/__main__.py`.
- Bad input raises `ReportError` naming the line; the CLI prints it and exits 1.
- A new calculation is a new pure function in `expenses.py`; `__main__.py` only formats and prints it.

## Size
- A change is at most 200 lines added plus removed (gate `gates/diff-size.sh`). Aim for under 80.
- If the ticket does not fit, deliver the smallest useful slice and list what was left out. Never fail the gate on purpose.

## Factory rules
- Phase state lives in `.factory/` as markdown files. Never put plan or review text in code comments.
- Only the paths in SCOPE (factory.conf) may change. Do not touch factory.sh, lib/, gates/, .claude/, data/ or this file.
