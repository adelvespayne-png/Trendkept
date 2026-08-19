"""How Vesper addresses you — guaranteed, not merely requested.

    python -m vesper.address "The trend filter is no longer met."

The system prompt asks her to say "sir". That works nearly always, which is
not the same as always: a model under load, on a backup provider, or three
tool-rounds deep will occasionally forget, and "nearly always" is exactly the
thing that gets noticed. So the prompt sets the habit and this enforces it.

The rule is deliberately narrow. It adds the address once, to the first
sentence, and only when it is genuinely missing. It never rewrites a
sentence, never adds a second one, and never touches text that already has
it — an assistant that said "sir" twice in a line would be worse than one
that occasionally forgot.
"""

from __future__ import annotations

import re
import sys
from typing import Optional

#: Sentence-ending punctuation, followed by a space or the end of the text.
#: The lookahead keeps "3.5" and "e.g." from being read as sentence ends.
_END = re.compile(r"[.!?](?=\s|$)")

#: A line that is markup rather than speech — a bullet, a heading, a fence,
#: a numbered step. Inserting mid-list reads as a mistake, so these are
#: skipped when looking for somewhere to put the address.
_MARKUP = re.compile(r"^\s*(?:```|[-*+•]\s|#{1,6}\s|\d+[.)]\s|>\s)")


def has_address(text: str, term: str = "sir") -> bool:
    """Is the user already being addressed? Whole word, any case."""
    if not text or not term:
        return False
    return re.search(r"\b" + re.escape(term) + r"\b", text, re.I) is not None


def ensure(text: Optional[str], term: str = "sir") -> Optional[str]:
    """Return `text` with the user addressed exactly once.

    Idempotent, so it is safe to call on the same string twice — which
    happens, because both the brain and the speaker enforce it and a reply
    normally passes through both.
    """
    if not text or not term:
        return text
    if has_address(text, term):
        return text

    lines = text.split("\n")

    # Prefer the first line that is actually speech. A reply that opens with
    # a heading or a bullet gets the address on its first prose line instead,
    # which is where a person would have put it.
    in_fence = False
    for i, line in enumerate(lines):
        if line.lstrip().startswith("```"):
            # Lines inside a fence look like prose but are code. Addressing
            # one produces `python -m vesper.main, sir`, which is both absurd
            # and, if anyone pasted it, broken.
            in_fence = not in_fence
            continue
        if in_fence or not line.strip() or _MARKUP.match(line):
            continue
        lines[i] = _address_line(line, term)
        return "\n".join(lines)

    # No prose at all — a bare list, or a code block. Announce it above,
    # rather than wedging the word into the markup.
    return f"{term.capitalize()}:\n" + text


def _address_line(line: str, term: str) -> str:
    """Put the address at the end of this line's first sentence."""
    m = _END.search(line)
    if m:
        head, punct, tail = line[:m.start()], line[m.start()], line[m.end():]
        return head.rstrip().rstrip(",") + f", {term}" + punct + tail

    # No sentence end: the whole line is one unpunctuated clause.
    stripped = line.rstrip()
    trailing = line[len(stripped):]

    # A colon or dash introduces what follows, so it has to stay at the end —
    # "Three open positions, sir:" and not "Three open positions, sir".
    # Dropping it would orphan the list underneath.
    if stripped.endswith((":", ";", "\u2014", "\u2013")):
        connector, body = stripped[-1], stripped[:-1].rstrip()
        return f"{body}, {term}{connector}{trailing}"

    # A trailing comma is replaced rather than kept, or the line would read
    # "Right, sir," with a comma going nowhere.
    if stripped.endswith(","):
        return f"{stripped[:-1].rstrip()}, {term}{trailing}"

    # Anything else — including a closing quote or bracket — keeps its ending
    # and takes the address after it: `She said "no", sir`.
    return f"{stripped}, {term}{trailing}"


def main(argv=None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    term = "sir"
    if args and args[0] == "--term":
        term, args = args[1], args[2:]
    text = " ".join(args) or "The trend filter is no longer met."
    print(ensure(text, term))
    return 0


if __name__ == "__main__":
    sys.exit(main())
