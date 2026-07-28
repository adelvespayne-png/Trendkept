"""Turn an autopilot pass into a row of the official paper-trading log.

The log (``business/paper_log.csv``) is the public evidence file for the
paper-trading test, so this module is deliberately conservative:

* It only ever **appends** — it never rewrites or removes history.
* It is **idempotent per date**: re-running the same day does not add a
  second machine-written row. (Hand-written rows are left alone.)
* It writes through :mod:`csv`, so notes containing commas are quoted and
  the file always parses.
* It **never invents** numbers. Everything in the row is read out of the
  pass text the autopilot actually printed.

The rule from CLAUDE.md holds: never backfill a day the owner has not
evidenced. This only records passes that genuinely ran.
"""

from __future__ import annotations

import csv
import io
import os
import re
from typing import List, Optional, Sequence

HEADER = [
    "Date", "Day #", "Action", "Symbol", "Signal", "Entry", "Stop",
    "Shares", "Exit / R", "Followed rules? (Y/N)", "Note",
]

# Marks a row this module wrote, so re-runs are detectable and a human can
# always tell machine rows from transcribed ones.
ROBOT_MARK = "[auto]"


def _symbols(pattern: str, text: str) -> List[str]:
    return re.findall(pattern, text)


def summarise(pass_text: str) -> dict:
    """Pull the structured facts out of an autopilot pass printout."""
    entered = _symbols(r"submitted: \w+ \(buy \d+ ([A-Z.]+)", pass_text)
    exited = _symbols(r"EXIT ([A-Z.]+):", pass_text)
    raised = _symbols(r"RAISE STOP ([A-Z.]+):", pass_text)
    installed = _symbols(r"SET STOP ([A-Z.]+):", pass_text)
    held = _symbols(r"HOLD ([A-Z.]+):", pass_text)

    unprotected = "UNPROTECTED" in pass_text
    failed = bool(re.search(r"\bfailed\b|Alpaca error", pass_text))

    bits = []
    if exited:
        bits.append("exit " + "/".join(exited))
    if entered:
        bits.append("enter " + "/".join(entered))
    if raised:
        bits.append("raise stop " + "/".join(raised))
    if installed:
        bits.append("set stop " + "/".join(installed))
    if not bits:
        bits.append("none")
    action = "autopilot " + ", ".join(bits)

    symbols = entered + exited + raised + installed or held
    # De-duplicate, preserving order.
    seen = set()
    ordered = [s for s in symbols if not (s in seen or seen.add(s))]

    return {
        "action": action,
        "symbol": " / ".join(ordered),
        "entered": entered,
        "exited": exited,
        "raised": raised,
        "held": held,
        "unprotected": unprotected,
        "failed": failed,
    }


def _next_day_number(rows: Sequence[Sequence[str]]) -> str:
    """Next whole day number, continuing the existing sequence."""
    best = 0
    for row in rows[1:]:
        if len(row) < 2:
            continue
        m = re.match(r"(\d+)", row[1].strip())
        if m:
            best = max(best, int(m.group(1)))
    return str(best + 1)


def build_row(date: str, pass_text: str,
              rows: Sequence[Sequence[str]]) -> List[str]:
    facts = summarise(pass_text)
    note_body = " ".join(pass_text.split())
    flag = "N" if (facts["unprotected"] or facts["failed"]) else "Y"
    note = (f"{ROBOT_MARK} Autopilot pass logged automatically. "
            f"Full printout: {note_body}")
    return [
        date,
        _next_day_number(rows),
        facts["action"],
        facts["symbol"],
        "",   # Signal — the detail lives in the note; no guessing here.
        "",   # Entry  — fills happen at the next open, so not known yet.
        "",   # Stop
        "",   # Shares
        "",   # Exit / R
        flag,
        note,
    ]


def already_logged(date: str, rows: Sequence[Sequence[str]]) -> bool:
    """True if this module has already written a row for ``date``."""
    return any(
        len(r) >= 11 and r[0].strip() == date and ROBOT_MARK in r[10]
        for r in rows[1:]
    )


def append_pass(path: str, date: str, pass_text: str) -> Optional[List[str]]:
    """Append one row for ``date``. Returns the row, or None if skipped."""
    if not pass_text.strip():
        return None
    with open(path, newline="") as fh:
        rows = list(csv.reader(fh))
    if not rows:
        rows = [HEADER]
    if already_logged(date, rows):
        return None

    row = build_row(date, pass_text, rows)
    rows.append(row)

    buf = io.StringIO()
    csv.writer(buf, lineterminator="\n").writerows(rows)
    tmp = path + ".tmp"
    with open(tmp, "w") as fh:
        fh.write(buf.getvalue())
    os.replace(tmp, path)  # atomic — never leave a half-written log
    return row


def main(argv: Optional[Sequence[str]] = None) -> int:
    import argparse
    from datetime import datetime, timezone

    p = argparse.ArgumentParser(
        description="Append an autopilot pass to the paper log.")
    p.add_argument("--pass-file", required=True,
                   help="file holding the autopilot printout")
    p.add_argument("--log", default="business/paper_log.csv")
    p.add_argument("--date",
                   default=datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    args = p.parse_args(argv)

    with open(args.pass_file) as fh:
        text = fh.read()

    row = append_pass(args.log, args.date, text)
    if row is None:
        print("paper log: nothing to add (empty pass, or already logged).")
        return 0
    print(f"paper log: appended day {row[1]} — {row[2]}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
