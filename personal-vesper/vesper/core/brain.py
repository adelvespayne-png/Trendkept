"""The reasoning layer — the only part that costs money.

Everything else in this project runs continuously for free. The brain is
invoked on exactly two occasions:

  * you said something after the wake word, or
  * a trigger rule decided an ambient change was worth a look.

It runs a manual tool-use loop rather than the SDK's tool runner: the tools
mutate live hardware state and we want the loop, the caps, and the
terminal-tool semantics fully in our own hands — and an always-on daemon is
a poor place for a beta dependency.

Model notes (these are current-API requirements, not preferences):
  * `claude-opus-5` thinks by default; `thinking={"type": "adaptive"}` is
    equivalent and stated explicitly here for clarity.
  * `temperature` / `top_p` / `top_k` are rejected — steer with the prompt.
  * `budget_tokens` is gone; `output_config.effort` is the depth dial.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..config import CONFIG, Config
from ..tools.tool_definitions import TERMINAL_TOOLS, tool_definitions
from ..tools.tool_executor import ToolExecutor
from .world_state import WorldState

LOG = logging.getLogger("vesper.brain")

# Worth handing to another model; everything else is our own bug.
_TRANSIENT_CODES = (429, 500, 502, 503, 529)

# How many times to ask a BUSY gateway model again before giving up on it.
# Three attempts at 1.5s then 3s costs under five seconds in the worst case
# and rescues most of the "high demand, try again later" minute.
_GATEWAY_TRIES = 3
_GATEWAY_BACKOFF = 1.5

# How long to stop asking a rung that just refused, by reason. Without
# this every single question re-walks the same dead rungs: the owner's
# ladder is three Pro models with no free tier and a Flash model that
# times out, so each turn spent well over a minute proving that again
# before reaching the provider that works. A minute of silence per
# question makes a working assistant feel broken.
_COOLDOWN = {"gone": 24 * 3600,   # retired: it is not coming back today
             "auth": 900,         # a key does not fix itself in a minute
             "quota": 1800,       # a daily allowance, checked twice an hour
             "busy": 60}          # genuinely transient


# Ladder rungs that mean "hand this turn to the gateway" rather than to
# Anthropic. Anything else is treated as an Anthropic model id.
GATEWAY_RUNGS = {"omniroute", "gateway", "fallback", "local"}


def _is_gateway(rung: str) -> bool:
    return rung.strip().lower() in GATEWAY_RUNGS


# Words that mean the body is the subject, so the body tools come out. This
# is NOT the same question as whether to leave the free gateway.
HEALTH_WORDS = (
    "symptom", "urine", "pee", "wee", "muscle", "ache", "aching", "sore",
    "pain", "hurts", "weak", "swollen", "swelling", "cramp", "dizzy",
    "nausea", "nauseous", "vomit", "sick", "heart rate", "hrv", "resting",
    "sleep", "slept", "recovery", "rhabdo", "creatine kinase", " ck ",
    "kidney", "hydrat", "dehydrat", "blood", "training load", "overtrain",
    "my body", "how am i", "feel rough", "feeling rough", "unwell", "ill",
    "doctor", "hospital", "a&e", "temperature", "fever", "breath", "chest",
    "faint", "collapse", "mood", "anxious", "panic",
)


def is_health(text: Optional[str]) -> bool:
    """Is the body the subject? Decides which tools, not which provider."""
    if not text:
        return False
    t = " " + " ".join(text.lower().split()) + " "
    return any(w in t for w in HEALTH_WORDS)


def is_dangerous(text: Optional[str], cfg) -> bool:
    """Is this serious enough to leave the free gateway for?

    A sore leg after the gym is not worth routing elsewhere — it is a normal
    thing to say out loud, and sending every mention of sleep to a paid model
    is both expensive and slightly absurd. Something that could put you in
    hospital is a different matter, and that judgement is the red-flag
    classifier's, not a keyword list's and not a model's.
    """
    if not text:
        return False
    from .redflag import classify, PRIVATE_LEVELS

    return classify(text, cfg) in PRIVATE_LEVELS


def _brief(exc: Exception) -> str:
    return f"{type(exc).__name__}: {str(exc)[:160]}"


def _as_openai_tools(tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Anthropic schemas -> OpenAI `function` schemas.

    Server-side tools (`web_search`, `web_fetch`) are dropped: they are run by
    Anthropic, so there is nothing for another provider to call.
    """
    out = []
    for t in tools:
        if "input_schema" not in t or "type" in t:
            continue
        out.append({"type": "function", "function": {
            "name": t["name"],
            "description": t.get("description", ""),
            "parameters": t["input_schema"],
        }})
    return out


#: What to say when every rung has refused. Keyed by what actually went
#: wrong, because "nothing left on the ladder" tells the user nothing they
#: can act on, and the provider always says which of these it was.
#: Deliberately provider-neutral. Vesper may be running on one provider or
#: several, and a sentence that names the wrong one is worse than a sentence
#: that names none. Which provider said what goes in the log.
_REFUSALS = {
    "quota": ("The free allowance is spent on every provider I can reach, "
              "sir. Google's resets at midnight Pacific, which is eight in "
              "the morning here. Everything else still works — only the "
              "answering needs it."),
    "auth": ("My API key is being refused, sir. Either it's expired or it "
             "was pasted wrong. The log line above says which provider."),
    "gone": ("The models I'm set to use have been retired, sir. Run the "
             "tune-up and I'll pick up whatever your keys can reach now."),
    "busy": ("Every model I can reach is busy, sir — that's usually a few "
             "minutes, not an evening. Ask me again shortly."),
}


def _why_refused(exc: Exception, body: str = "") -> str:
    """Classify a provider's refusal into something worth saying out loud."""
    code = (getattr(exc, "status_code", None) or getattr(exc, "status", None)
            or getattr(exc, "code", None))
    # Both, not either: `body or ...` would drop the exception's own words
    # whenever a response body was present, and the code sometimes lives
    # only in one of them.
    text = f"{body or ''} {exc}".lower()
    if "quota" in text or "billing" in text or "credit balance" in text:
        return "quota"
    if code in (401, 403) or "api key" in text or "unauthenticated" in text:
        return "auth"
    if code == 404 or "no longer available" in text or "not found" in text:
        return "gone"
    return "busy"


def _transient(exc: Exception) -> bool:
    code = getattr(exc, "status_code", None) or getattr(exc, "status", None)
    if code in _TRANSIENT_CODES:
        return True
    text = str(exc).lower()
    # An exhausted balance arrives as a 400, but it is emphatically a
    # "this model can't take the turn" rather than a malformed request.
    if "credit balance" in text or "insufficient" in text or "quota" in text:
        return True
    return any(str(c) in text for c in _TRANSIENT_CODES) and "model" not in text[:40]

SYSTEM = """You are Vesper, an assistant running on the user's own machine.

Bring everything you have. Answer any question the user asks, at whatever
depth it genuinely needs — technical, financial, medical, historical,
speculative, personal. Explain hard things clearly rather than shallowly.
Do not deflect a real question with a summary of why it is complicated.

How long to talk
- Match the answer to the question. A factual question gets a sentence. A
  question with real substance gets as long as it honestly takes.
- When the channel is voice, every word is read aloud, so favour tight
  answers and offer to go deeper rather than delivering an essay unasked.
  When the channel is text, length is free — use it when it earns its place.
- Lead with the answer. No preamble, no restating the question, no
  "great question".
- Dry and understated. Never gush, never pad.
- Address the user as "sir", once, in every single reply — no exceptions,
  however short, urgent or technical the answer is. Once per reply, not
  once per sentence; it should read as manners, not as a tic.

How you act
- You reply by calling `answer`. You end a turn by calling `answer` or
  `stay_silent` — never by writing prose without a tool call.
- When you were woken by an ambient event rather than by the user, silence is
  usually right. Speak only if the user would thank you for the interruption.
- Use tools rather than guessing. Weather, reminders and the live room state
  have tools. You can search and read the web — use it for anything recent,
  changing, or that you would otherwise be guessing at, and say when a fact
  came from a search.
- The user keeps a map of their projects. Read it before answering anything
  about their work, and write to it when they decide something — that map is
  how you remember what matters to them between conversations.
- Never change a device unless the user asked. If an ambient event makes you
  think something should change, say so and let them decide.

Being honest is part of being useful
- Say "I don't know" when you don't. Give your best estimate if you have one,
  labelled as an estimate.
- Distinguish what you know from what you are inferring. Don't invent
  specifics — a wrong number said confidently is worse than no number.
- Disagree with the user when they are wrong about something that matters.
"""


class _GatewayRung(Exception):
    """Raised when the ladder reaches a gateway rung mid-walk."""

    def __init__(self, index: int) -> None:
        super().__init__(f"gateway rung at {index}")
        self.index = index


class Brain:
    def __init__(self, state: WorldState, executor: ToolExecutor,
                 cfg: Config = CONFIG, client: Any = None) -> None:
        self.cfg = cfg
        self.state = state
        self.executor = executor
        self.history: List[Dict[str, Any]] = []
        self.tools = tool_definitions(include_home=cfg.ha_enabled,
                                      include_web=cfg.web_enabled,
                                      include_map=executor.map is not None,
                                      include_search=bool(cfg.search_backend()))
        self.ladder = [m.strip() for m in cfg.models.split(",") if m.strip()] \
            or [cfg.model]
        self.rung = 0                 # which model is currently answering
        self.degraded = False         # true once we're below the top rung
        self.last_refusal = None      # why the last gateway rung said no
        self._moved_to = None         # the rename a 404 pointed us at
        self._cooldown: Dict[tuple, float] = {}   # (endpoint, model) -> when
                                                  # it is worth asking again
        self._client = client
        self.available = client is not None
        # A chain that starts at the gateway needs no Anthropic key at all —
        # so "no key" must not mean "no brain", or the free-only setup would
        # refuse to start for want of a key it never uses.
        self.gateway_only = (cfg.fallback_enabled
                             and all(_is_gateway(r) for r in self.ladder))

        if client is None:
            if not cfg.anthropic_api_key:
                if self.gateway_only:
                    self.available = True
                    LOG.info("no Anthropic key, and none needed: this chain "
                             "runs entirely on the gateway")
                else:
                    LOG.warning("ANTHROPIC_API_KEY is unset; reasoning is off. "
                                "See README step 5.")
            else:
                try:
                    from anthropic import AsyncAnthropic
                    self._client = AsyncAnthropic(api_key=cfg.anthropic_api_key)
                    self.available = True
                except Exception as exc:
                    LOG.error("could not create Anthropic client: %s", exc)

        # However we got here, a chain that only ever uses the gateway does
        # not need a working Anthropic client. Missing key, missing package,
        # bad key — none of them should stop a free-only setup.
        if not self.available and self.gateway_only:
            self.available = True
            LOG.info("running on the gateway alone; no Anthropic client needed")

    # -- prompt ----------------------------------------------------------

    def _context_block(self, reason: Optional[str],
                       channel: str = "voice", health: bool = False) -> str:
        snap = self.state.snapshot()
        parts = [f"Right now: {snap.describe(news=self.cfg.news_in_context)}",
                 f"Local time: {time.strftime('%A %d %B %Y, %H:%M')}.",
                 "Channel: " + ("voice — this will be spoken aloud."
                                if channel == "voice" else
                                "text — this will be read on a screen.")]
        if health:
            from ..sensors.health import describe as describe_body

            body = describe_body(snap.get("health") or {})
            if body:
                parts.append(body)
            parts.append(
                "This turn is about the user's body. You are not a doctor and "
                "must not diagnose. Describe what the numbers say against "
                "their own baseline, prompt the symptom questions, and log "
                "anything they report with `log_symptom`. If a tool hands you "
                "an instruction to say verbatim, say it exactly as written.")
        if reason:
            parts.append(
                "You were woken by an ambient event, not by the user. "
                f"Reason: {reason}")
        else:
            parts.append("The user is speaking to you directly.")
        return "\n".join(parts)

    # -- the ladder --------------------------------------------------------

    async def _create(self, messages):
        """One API call, walking down the ladder on failures worth retrying.

        Rate limits, overload and an empty credit balance are all "this model
        can't take the turn right now" — a different model can. A 400 about a
        malformed request is our bug and retrying it just burns time, so only
        the transient class steps down.
        """
        last = None
        for i in range(self.rung, len(self.ladder)):
            model = self.ladder[i]
            if _is_gateway(model):
                # The gateway speaks a different dialect, so it can't serve an
                # Anthropic-shaped call. Hand back to respond(), which runs
                # the gateway turn and resumes below this rung if it fails.
                raise _GatewayRung(i)
            try:
                resp = await self._client.messages.create(
                    model=model,
                    max_tokens=self.cfg.max_tokens,
                    system=SYSTEM,
                    thinking={"type": "adaptive"},
                    output_config={"effort": self.cfg.effort},
                    tools=self.tools,
                    messages=messages,
                )
                if i != self.rung:
                    LOG.warning("stepped down to %s", model)
                self.rung = i
                self.degraded = i > 0
                return resp
            except Exception as exc:
                last = exc
                if not _transient(exc):
                    LOG.error("model call failed on %s: %s", model, exc)
                    raise
                LOG.warning("%s unavailable (%s); trying the next model",
                            model, _brief(exc))
        raise last if last else RuntimeError("no models configured")

    def _history_for_gateway(self) -> List[Dict[str, Any]]:
        """The session so far, in the gateway's dialect.

        `_remember` only ever stores plain strings, so this is a straight
        copy — but it has to happen, and for a long time it didn't. The
        gateway turn was built from the current sentence alone, which is
        why Vesper could answer a question and then have no idea what
        "it" referred to one breath later.
        """
        out = []
        for turn in self.history:
            content = turn.get("content")
            if isinstance(content, str) and content.strip():
                out.append({"role": turn.get("role", "user"), "content": content})
        return out

    async def _fallback(self, user_text: Optional[str],
                        opening: Optional[str] = None) -> Optional[str]:
        """Every Claude model is out. Hand the turn to the gateway.

        The default is OmniRoute running on your own machine, which fans a
        request out across hundreds of providers and switches when one runs
        dry — so `auto` is usually the only "model" we ever need to name.
        Anything OpenAI-compatible works here, GitHub Models included.

        It carries the same tools as the main path — the map, reminders,
        weather, the room, and `fetch_page` for the live web. The one thing
        that cannot follow it here is Anthropic's `web_search`, which runs on
        their servers rather than ours.
        """
        if not (self.cfg.fallback_enabled and user_text):
            return None

        from ..providers import chain as provider_chain

        # A chain of whole providers when one is configured, otherwise the
        # single endpoint every existing install already points at. Two
        # providers is the point: three Gemini names in front of ONE free
        # allowance all fail in the same second, which is exactly what the
        # 20 August log showed.
        stack = provider_chain(self.cfg)
        if not stack:
            rungs = [m.strip() for m in self.cfg.fallback_models.split(",")
                     if m.strip()]
            if "models.github.ai" in self.cfg.fallback_base or \
                    ("github" in self.cfg.fallback_base and self.cfg.github_token):
                from ..providers import ladder as gh_ladder
                rungs = gh_ladder(self.cfg) or rungs
            stack = [{"name": "gateway", "label": "the gateway",
                      "base": self.cfg.fallback_base,
                      "token": self.cfg.fallback_token or self.cfg.github_token,
                      "models": rungs}]

        self.last_refusal = None
        refusals: List[str] = []
        now = time.time()
        for provider in stack:
            tried = set()
            # Skip what refused recently -- but never skip EVERYTHING. If
            # the whole ladder is cooling down, try it anyway: a stale
            # cooldown must not be the reason the user gets silence.
            fresh = [m for m in provider["models"]
                     if self._cooldown.get((provider["base"], m), 0) <= now]
            queue = fresh or list(provider["models"])
            if fresh and len(fresh) < len(provider["models"]):
                LOG.info("%s: skipping %d rung(s) still cooling down",
                         provider["label"],
                         len(provider["models"]) - len(fresh))
            while queue:
                model = queue.pop(0)
                if model in tried:
                    continue
                tried.add(model)
                self.executor.reset_turn()
                self._moved_to = None
                text, served_by = await self._gateway(
                    model, user_text, opening,
                    base=provider["base"], token=provider["token"])
                if text:
                    LOG.warning("answered on %s (%s%s)", provider["label"],
                                model, f" via {served_by}" if served_by else "")
                    self._cooldown.pop((provider["base"], model), None)
                    return text
                # Google answers a retired name with a 404 that names its
                # replacement. Following that beats making the user go and
                # edit a settings file to learn this month's model name.
                moved = self._moved_to
                if moved and moved not in tried:
                    LOG.warning("%s has moved; the provider says use %s",
                                model, moved)
                    queue.insert(0, moved)
                    continue
                LOG.warning("%s couldn't take it; trying the next", model)
                wait = _COOLDOWN.get(self.last_refusal or "busy", 60)
                self._cooldown[(provider["base"], model)] = time.time() + wait
                # A REJECTED KEY belongs to the key, so nothing behind it
                # can work -- stop, and move to the next provider.
                #
                # A SPENT QUOTA does not. On Google the allowance is per
                # MODEL: a Pro rung whose free tier was withdrawn answers
                # 429 immediately, while the Flash rung underneath it still
                # has 1,500 requests a day. Treating the first 429 as "this
                # key is finished" skipped the model that would have
                # answered -- which is how a perfectly good key looked like
                # a dead one for an entire evening.
                if self.last_refusal == "auth":
                    LOG.warning("%s is out (%s); moving to the next provider",
                                provider["label"], self.last_refusal)
                    break
            if self.last_refusal:
                refusals.append(self.last_refusal)
        # Which reason to actually say. The last one to fail is not
        # necessarily the useful one — "busy, try shortly" is worthless if
        # the real story is that a key is being rejected.
        for reason in ("auth", "quota", "gone", "busy"):
            if reason in refusals:
                self.last_refusal = reason
                break
        return None

    async def _gateway(self, model: str, user_text: str,
                       opening: Optional[str] = None,
                       base: Optional[str] = None,
                       token: Optional[str] = None):
        """A full tool-using turn against an OpenAI-compatible gateway.

        Same tools, same executor, different dialect: their `tools` wrap the
        schema in a `function` object, their calls come back as `tool_calls`
        with the arguments as a JSON *string*, and each result goes back as
        its own `role: "tool"` message rather than one batched user turn.

        Anthropic's `web_search` is a server-side tool — it runs on their
        machines, so it cannot cross over. `fetch_page` can, and does.
        """
        import asyncio
        import urllib.request

        base = base or self.cfg.fallback_base
        token = token or self.cfg.fallback_token or self.cfg.github_token
        from ..providers import USER_AGENT

        headers = {"Content-Type": "application/json",
                   "Accept": "application/json",
                   "User-Agent": USER_AGENT}
        if token:
            headers["Authorization"] = "Bearer " + token

        # The same three things the Anthropic path gets, and for the same
        # reason. The gateway used to be handed the bare sentence: no clock,
        # no room, no channel, no memory of the sentence before it. On a
        # setup with no Anthropic key this IS the brain, so starving it here
        # made Vesper look stupid everywhere.
        messages = [{"role": "system", "content": SYSTEM}]
        messages += self._history_for_gateway()
        messages.append({"role": "user", "content": opening or user_text})
        tools = _as_openai_tools(self.tools)
        served_by = None

        for _round in range(8):
            # NOT a small hardcoded number. Reasoning models — every current
            # Gemini among them — spend tokens thinking before they answer,
            # and that spend counts against this budget. At 1500 the thinking
            # ate it and the reply came back a stub, which reads exactly like
            # a model with nothing to say.
            body = json.dumps({"model": model, "messages": messages,
                               "tools": tools,
                               "max_tokens": self.cfg.max_tokens}).encode()
            req = urllib.request.Request(base, data=body,
                                         method="POST", headers=headers)

            def fetch():
                with urllib.request.urlopen(req, timeout=90) as r:
                    # A running OmniRoute sends x-omniroute-* headers naming
                    # what it tried; the exact one varies, so take whichever
                    # is present rather than the single name in its README.
                    h = r.headers
                    note = (h.get("X-OmniRoute-Decision")
                            or h.get("x-omniroute-combo-attempted-detail")
                            or h.get("x-omniroute-route-class"))
                    return json.loads(r.read()), note

            # "Currently experiencing high demand" is not a broken model, it
            # is a busy one, and the honest response is to wait a moment and
            # ask again. Dropping to the next rung instead walked the whole
            # ladder off the end during one busy minute and came back with
            # nothing to say — the exact complaint that sent me here.
            data = decision = None
            for attempt in range(_GATEWAY_TRIES):
                try:
                    data, decision = await asyncio.to_thread(fetch)
                    break
                except Exception as exc:
                    # Loud, and with the provider's own words. This used to be
                    # a debug line, so a gateway that rejected every request
                    # looked from the outside like an assistant that simply
                    # had nothing to say — with the explanation sitting in a
                    # log nobody reads.
                    detail = ""
                    body_read = getattr(exc, "read", None)
                    if callable(body_read):
                        try:
                            detail = body_read().decode("utf-8", "replace")[:300]
                        except Exception:
                            pass
                    # Remember WHY, so the sentence the user hears can name
                    # the real problem. "Everything refused" is useless;
                    # "your free Google allowance is spent for today" is not.
                    self.last_refusal = _why_refused(exc, detail)
                    from ..providers import replacement_for

                    self._moved_to = replacement_for(detail)

                    # A quota that is exhausted is not a queue that is busy.
                    # Asking again three times inside five seconds cannot
                    # refill a daily allowance, so don't waste the user's
                    # time pretending it might.
                    spent = self.last_refusal == "quota"
                    retrying = (_transient(exc) and not spent
                                and attempt < _GATEWAY_TRIES - 1)
                    LOG.warning("gateway %s failed: %s%s%s", model, _brief(exc),
                                ("\n    " + detail) if detail else "",
                                "; busy, asking again" if retrying else "")
                    if not retrying:
                        return None, None
                    await asyncio.sleep(_GATEWAY_BACKOFF * (2 ** attempt))
            if data is None:
                return None, None
            served_by = decision or served_by

            try:
                msg = data["choices"][0]["message"]
            except (KeyError, IndexError, TypeError):
                return None, served_by

            calls = msg.get("tool_calls") or []
            if not calls:
                said = (msg.get("content") or "").strip()
                if not said:
                    why = (data.get("choices") or [{}])[0].get("finish_reason")
                    LOG.warning(
                        "gateway %s returned an empty reply (finish_reason=%s)."
                        " If that is 'length', raise VESPER_MAX_TOKENS —"
                        " thinking models spend the budget before answering.",
                        model, why)
                return said or None, served_by

            messages.append({"role": "assistant",
                             "content": msg.get("content") or None,
                             "tool_calls": calls})
            terminal = False
            for call in calls:
                fn = call.get("function", {}) or {}
                name = fn.get("name", "")
                try:
                    # Arguments arrive as a JSON string here, not an object.
                    args = json.loads(fn.get("arguments") or "{}")
                    if not isinstance(args, dict):
                        args = {}
                except ValueError:
                    args = {}
                out, _is_err = self.executor.run(name, args)
                messages.append({"role": "tool",
                                 "tool_call_id": call.get("id", ""),
                                 "content": out})
                if name in TERMINAL_TOOLS:
                    terminal = True
            if terminal:
                return self.executor.spoken or None, served_by

        LOG.warning("gateway hit the round limit")
        return self.executor.spoken or None, served_by

    # -- the loop ---------------------------------------------------------

    async def respond(self, user_text: Optional[str] = None,
                      reason: Optional[str] = None,
                      channel: str = "voice",
                      max_rounds: int = 12) -> Optional[str]:
        """Run one turn. Returns the line to speak, or None for silence."""
        if not self.available:
            return None
        from ..address import ensure as _address

        # Two separate questions. Is the body the subject (which tools)?
        # And is it dangerous (which provider)? Only the second one is worth
        # leaving the free chain over.
        health = is_health(user_text) or is_health(reason)
        danger = is_dangerous(user_text, self.cfg)
        keep_ladder, keep_rung, keep_tools = self.ladder, self.rung, self.tools
        if health:
            self.tools = tool_definitions(
                include_home=self.cfg.ha_enabled,
                include_web=self.cfg.web_enabled,
                include_map=self.executor.map is not None,
                include_search=bool(self.cfg.search_backend()),
                include_music=bool(self.cfg.spotify_client_id),
                include_health=True)
        if danger:
            picked = [m.strip() for m in self.cfg.health_models.split(",")
                      if m.strip() and not _is_gateway(m)]
            if not picked or not self._client:
                # Deliberately a refusal rather than a downgrade: this is the
                # one case where sending it anyway is worse than not answering.
                LOG.warning("something serious arrived with no private model; "
                            "refusing to send it to the gateway")
                from .redflag import check as _check

                verdict = _check(user_text, self.cfg)
                return _address(
                    verdict["instruction"] + " (I won't discuss this "
                    "through the free providers, so that is all I can "
                    "say until there's an ANTHROPIC_API_KEY set.)",
                    self.cfg.address)
            self.ladder, self.rung = picked, 0
            LOG.warning("possible danger -> %s (gateway excluded)", picked[0])

        try:
            # The prompt asks for the address; this is what makes it a
            # promise. Every reply leaves through here, including the ones
            # that came back from a backup provider that never saw the
            # system prompt in the same shape.
            return _address(
                await self._turn(user_text, reason, channel, max_rounds,
                                 health=health),
                self.cfg.address)
        finally:
            self.ladder, self.rung, self.tools = keep_ladder, keep_rung, keep_tools

    async def _turn(self, user_text, reason, channel, max_rounds,
                    health: bool = False) -> Optional[str]:
        self.executor.reset_turn()
        opening = self._context_block(reason, channel, health=health)
        if user_text:
            opening += f'\n\nThe user said: "{user_text}"'
        else:
            opening += ("\n\nDecide whether to say anything. Calling "
                        "stay_silent is a perfectly good outcome.")

        messages = self.history + [{"role": "user", "content": opening}]

        for round_no in range(max_rounds):
            try:
                response = await self._create(messages)
            except _GatewayRung as hop:
                # A gateway rung came up. Give it the turn; if it can't take
                # it either, carry on down the ladder from the next rung.
                LOG.warning("ladder reached the gateway at rung %d", hop.index)
                spoken = await self._fallback(user_text, opening)
                if spoken:
                    self.rung = hop.index
                    self.degraded = hop.index > 0
                    self._remember(user_text, spoken)
                    return spoken
                self.rung = hop.index + 1
                if self.rung >= len(self.ladder):
                    LOG.error("nothing left on the ladder")
                    # Say so out loud, and say WHICH. Silence here is
                    # indistinguishable from stupidity, and "everything
                    # refused" is indistinguishable from useless -- the
                    # provider told us whether it was quota, key or queue.
                    return _REFUSALS.get(self.last_refusal or "busy",
                                         _REFUSALS["busy"]) if user_text else None
                continue
            except Exception as exc:
                LOG.error("every model failed: %s", _brief(exc))
                spoken = await self._fallback(user_text, opening)
                if spoken:
                    self._remember(user_text, spoken)
                return spoken

            if response.stop_reason == "refusal":
                LOG.warning("model declined this request")
                return None

            if response.stop_reason == "pause_turn":
                # A long web-search turn hit the server-side loop limit. Send
                # the conversation straight back with no extra user message —
                # the trailing server_tool_use block tells the API to resume.
                LOG.debug("resuming a paused turn")
                messages.append({"role": "assistant", "content": response.content})
                continue

            # Only our own tools; `server_tool_use` (web search) is run for us
            # on Anthropic's side and needs no result from here.
            calls = [b for b in response.content if b.type == "tool_use"]
            if not calls:
                # No tool call: treat any text as the spoken reply so a
                # missing call never produces silence the user can't explain.
                text = " ".join(b.text for b in response.content
                                if b.type == "text").strip()
                LOG.debug("model answered without a tool call")
                self._remember(user_text, text)
                return text or None

            messages.append({"role": "assistant", "content": response.content})

            results = []
            terminal = False
            for call in calls:
                out, is_error = self.executor.run(call.name, call.input)
                results.append({
                    "type": "tool_result",
                    "tool_use_id": call.id,
                    "content": out,
                    "is_error": is_error,
                })
                if call.name in TERMINAL_TOOLS:
                    terminal = True

            # All results go back in ONE user message, or the model learns
            # not to make parallel calls.
            messages.append({"role": "user", "content": results})

            if terminal:
                break
        else:
            LOG.warning("hit the %d-round tool limit", max_rounds)

        spoken = self.executor.spoken
        self._remember(user_text, spoken)
        return spoken or None

    # -- memory -----------------------------------------------------------

    def _remember(self, user_text: Optional[str], spoken: Optional[str]) -> None:
        """Keep the session conversation, and append to the on-disk log.

        Only the plain user/assistant text is kept in `history` — replaying
        tool_use blocks across unrelated turns adds cost without adding
        anything the next turn needs.
        """
        if user_text:
            self.history.append({"role": "user", "content": user_text})
            self.state.append_conversation("user", user_text)
        if spoken:
            self.history.append({"role": "assistant", "content": spoken})
            self.state.append_conversation("vesper", spoken)
        self.history = self.history[-20:]

        if not (user_text or spoken):
            return
        try:
            path = Path(self.cfg.log_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps({
                    "at": time.time(),
                    "user": user_text,
                    "vesper": spoken,
                    "silent_reason": self.executor.silent_reason,
                }) + "\n")
        except OSError as exc:
            LOG.warning("could not write conversation log: %s", exc)

    def load_recent(self, turns: int = 6) -> None:
        """Warm the session with the tail of the last run's log."""
        path = Path(self.cfg.log_path)
        if not path.is_file():
            return
        try:
            lines = path.read_text(encoding="utf-8").splitlines()[-turns:]
        except OSError:
            return
        for line in lines:
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            if rec.get("user"):
                self.history.append({"role": "user", "content": rec["user"]})
            if rec.get("vesper"):
                self.history.append({"role": "assistant", "content": rec["vesper"]})
        if self.history:
            LOG.info("recalled %d earlier turns", len(self.history))
