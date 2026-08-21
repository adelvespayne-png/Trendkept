"""How hard to think about this one.

Treating every question the same is what makes an assistant feel stupid in
both directions at once. "What's the time" gets a committee; "should I
restructure the pricing" gets a shrug. Both are the same failure — no
judgement about what the question deserves.

Three depths:

  REFLEX   — answerable from the room, the clock, the map or memory, with
             no model call at all. Instant, free, and correct.
  QUICK    — a normal question. One model call, small prompt, no tools.
  DEEP     — a question with real substance. Full tools, and a second
             pass that checks the answer against the question before it
             is spoken.

The router is deliberately dumb and readable. A model deciding how hard to
think is a model call to save a model call, which is both slower and one
more thing that can be wrong — and being wrong here is invisible, because
a shallow answer to a deep question still *looks* like an answer.
"""

from __future__ import annotations

import re
from typing import Optional

REFLEX, QUICK, DEEP = "reflex", "quick", "deep"

#: Questions with a right answer that Vesper already holds. No model can
#: beat a clock at telling the time, and every one of them is slower.
_REFLEX = (
    (re.compile(r"^\s*(?:what(?:'s| is) the )?time\b|^\s*what time", re.I),
     "time"),
    (re.compile(r"^\s*(?:what(?:'s| is) (?:the |today'?s )?date"
                r"|what day is it|what'?s today)", re.I), "date"),
    (re.compile(r"\b(?:what do you (?:know|remember) about me"
                r"|what have you got on me"
                r"|what do you remember)\b", re.I), "memory"),
    (re.compile(r"\b(?:are you (?:there|awake|listening)|you there)\b", re.I),
     "ping"),
)

#: Marks of a question that deserves the full treatment. Length alone is a
#: bad signal -- "should I sell V?" is nine characters and consequential --
#: so this looks for the SHAPE of a question with stakes.
_DEEP = re.compile(
    r"\b(?:why|how come|explain|compare|versus|vs\b|trade-?off|"
    r"should i|worth it|pros and cons|analyse|analyze|review|critique|"
    r"strategy|decide|decision|plan|design|implic|consequence|risk of|"
    r"what if|walk me through|think through|break down|in depth|"
    r"help me (?:think|decide|work out)|"
    r"which (?:is|one|would)|better to)\b", re.I)

#: Anything about money, the body, or a rule change gets depth whatever it
#: looks like. These are the questions where a glib answer costs something.
_ALWAYS_DEEP = re.compile(
    r"\b(?:risk|position size|stop loss|drawdown|churn|pricing|revenue|"
    r"invest|portfolio|my rules?|the rules?|"
    r"symptom|pain|kidney|rhabdo|hospital|doctor|"
    r"legal|fca|compliance|contract)\b", re.I)


def classify(text: Optional[str], channel: str = "voice") -> str:
    """What depth this question deserves."""
    said = " ".join((text or "").split())
    if not said:
        return QUICK

    for pattern, _what in _REFLEX:
        if pattern.search(said):
            return REFLEX

    if _ALWAYS_DEEP.search(said) or _DEEP.search(said):
        return DEEP

    # A long, multi-clause question is usually a real one even without a
    # keyword. A short one usually isn't.
    words = said.split()
    if len(words) >= 25 or said.count("?") > 1:
        return DEEP
    return QUICK


def reflex_kind(text: Optional[str]) -> Optional[str]:
    """Which reflex applies, if any."""
    said = " ".join((text or "").split())
    for pattern, what in _REFLEX:
        if pattern.search(said):
            return what
    return None


#: Added to the prompt when a question has earned real thought. Not a
#: chain-of-thought incantation -- an instruction to do the specific
#: things a careful person does and a hurried one skips.
DEEP_INSTRUCTIONS = """This question deserves real thought. Before you answer:

- Work out what is actually being asked, including the thing behind the
  question if there is one.
- Consider at least two readings or approaches, and say which you took.
- Name what would have to be true for your answer to be wrong.
- Use what you know about the user. A generic answer to a personal
  question is a wrong answer.
- If a number or a fact decides it, get it — look it up or read the map —
  rather than reasoning around the gap.

Then answer plainly. Show the conclusion, not the deliberation: the
thinking should be visible in how good the answer is, not in a recital of
the steps."""

#: The second pass. Cheap, and it catches the specific failure that makes
#: an assistant feel unintelligent -- confidently answering a slightly
#: different question than the one asked.
CHECK_PROMPT = """You answered a question. Check the answer before it is spoken.

The question: {question}

Your answer: {answer}

Check, honestly:
1. Does it answer what was ASKED, or something adjacent?
2. Is anything stated as fact that you are actually unsure of?
3. Is there an obvious follow-up you should have pre-empted?
4. Is it the right length for the question?

If the answer is good, reply exactly: GOOD
Otherwise reply with the improved answer and nothing else — no preamble,
no explanation of what you changed."""
