"""Configuration — everything tunable, loaded from .env.

No secrets in code. `.env.example` is the checked-in template; `.env` is
yours and git-ignored.

Every subsystem can be switched off here, and anything that needs hardware
or a key you haven't supplied switches itself off at startup rather than
crashing the assistant.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

LOG = logging.getLogger("vesper.config")

ROOT = Path(__file__).resolve().parent.parent


def _load_dotenv(path: Path) -> None:
    """Minimal .env reader — avoids a dependency for ten lines of parsing.

    Values already present in the real environment win, so a shell export
    can override the file (useful in systemd units and CI).
    """
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


_load_dotenv(ROOT / ".env")


def _ensure_ca_bundle() -> None:
    """Give OpenSSL a CA bundle it can actually read.

    Some Windows Pythons — the install-manager ones especially — end up
    without a usable certificate store, and then HTTPS fails with

        CERTIFICATE_VERIFY_FAILED: unable to get local issuer certificate

    for *some* hosts and not others, depending on which root signed them.
    That is a maddening thing to debug, because the assistant plainly
    reaches the internet and yet one service refuses to work.

    `certifi` ships a current bundle and is already present as a transitive
    dependency. Pointing OpenSSL at it via SSL_CERT_FILE fixes every urllib
    call in one place, rather than threading a context through each of them.

    An SSL_CERT_FILE you set yourself always wins.
    """
    if os.environ.get("SSL_CERT_FILE"):
        return
    try:
        import certifi
    except Exception:
        return
    try:
        where = certifi.where()
    except Exception:
        return
    if where and Path(where).is_file():
        os.environ["SSL_CERT_FILE"] = where
        LOG.debug("using certifi's CA bundle: %s", where)


_ensure_ca_bundle()


def reload_env(path: Path = None) -> None:
    """Re-read `.env` after something has written it at runtime.

    The load above happens once, when this module is first imported. The
    launcher writes a `.env` on a first run — which is *after* that — so
    without this the Config built a moment later would not see the token it
    had just generated, and a brand-new install would report no token and
    refuse to serve its own map.
    """
    _load_dotenv(path or (ROOT / ".env"))


def _bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def _float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


@dataclass
class Config:
    # --- reasoning -------------------------------------------------------
    anthropic_api_key: str = field(
        default_factory=lambda: os.environ.get("ANTHROPIC_API_KEY", ""))
    # Claude Opus 5. Thinking is on by default on this model; effort is the
    # depth/cost dial. Do not add temperature/top_p — they are rejected.
    model: str = field(
        default_factory=lambda: os.environ.get("VESPER_MODEL", "claude-opus-5"))
    # How hard it thinks: low | medium | high | xhigh | max. High is the
    # sweet spot for an assistant you ask real questions — medium answers
    # trivia fine but gets shallow the moment a question has depth to it.
    effort: str = field(
        default_factory=lambda: os.environ.get("VESPER_EFFORT", "high"))
    max_tokens: int = field(default_factory=lambda: _int("VESPER_MAX_TOKENS", 8000))
    # Live web search and page fetching, run on Anthropic's servers. Without
    # this it only knows what it was trained on, so "what happened today" and
    # anything recent is beyond it.
    web_enabled: bool = field(default_factory=lambda: _bool("WEB_ENABLED", True))
    # The ladder. When one model is rate-limited, overloaded, or out of
    # credit, the next one takes the turn. These all speak the same API and
    # use the same tools, so stepping down costs cleverness and nothing else.
    # Any rung named `omniroute` (or `gateway`) hands that turn to the
    # fallback gateway instead of Anthropic, so the two can interleave.
    models: str = field(default_factory=lambda: os.environ.get(
        "VESPER_MODELS", "omniroute"))

    # --- web search -------------------------------------------------------
    # Anthropic's own web_search runs on their servers, so it cannot follow
    # Vesper onto a backup provider. This is a search tool that lives here and
    # therefore works on every rung.
    #   auto  -> brave if keyed, else tavily if keyed, else duckduckgo
    #   none  -> no local search tool at all
    search_provider: str = field(
        default_factory=lambda: os.environ.get("SEARCH_PROVIDER", "auto"))
    brave_api_key: str = field(
        default_factory=lambda: os.environ.get("BRAVE_API_KEY", ""))
    tavily_api_key: str = field(
        default_factory=lambda: os.environ.get("TAVILY_API_KEY", ""))
    search_results: int = field(default_factory=lambda: _int("SEARCH_RESULTS", 6))

    def search_backend(self) -> str:
        """Which backend is actually usable, given the keys present."""
        want = (self.search_provider or "auto").lower()
        if want == "none":
            return ""
        if want == "auto":
            if self.brave_api_key:
                return "brave"
            if self.tavily_api_key:
                return "tavily"
            return "duckduckgo"
        if want == "brave" and not self.brave_api_key:
            return "duckduckgo"
        if want == "tavily" and not self.tavily_api_key:
            return "duckduckgo"
        return want

    # --- the fallback gateway --------------------------------------------
    # When every Claude model above is rate-limited or out of credit, the turn
    # goes here. Anything OpenAI-compatible works; the default is OmniRoute
    # (github.com/diegosouzapw/OmniRoute), a gateway you run locally that
    # fans out across hundreds of providers and handles switching itself when
    # one runs dry — which is the whole job we want from this rung.
    #
    #   npm install -g omniroute      then leave it running
    #
    # It has no tools, so in this mode Vesper can think and talk but not act.
    fallback_enabled: bool = field(
        default_factory=lambda: _bool("FALLBACK_ENABLED", True))
    fallback_base: str = field(default_factory=lambda: os.environ.get(
        "FALLBACK_BASE", "http://localhost:20128/v1/chat/completions"))
    # OmniRoute's own routing aliases, taken from a running instance's
    # /v1/models rather than its README: reasoning first, then its general
    # "smart" pick, then the one that sticks to free tiers.
    fallback_models: str = field(default_factory=lambda: os.environ.get(
        "FALLBACK_MODELS", "auto/best-reasoning,auto/smart,auto/best-free"))
    fallback_token: str = field(
        default_factory=lambda: os.environ.get("FALLBACK_TOKEN", ""))

    # --- GitHub Models (an alternative gateway) ---------------------------
    # Point FALLBACK_BASE at GitHub instead of OmniRoute and Vesper will read
    # GitHub's catalogue and pick the best model from each maker itself.
    github_token: str = field(
        default_factory=lambda: os.environ.get("GITHUB_TOKEN", ""))
    github_ladder: str = field(
        default_factory=lambda: os.environ.get("GITHUB_LADDER", ""))
    github_ladder_size: int = field(
        default_factory=lambda: _int("GITHUB_LADDER_SIZE", 6))
    github_catalog: str = field(default_factory=lambda: os.environ.get(
        "GITHUB_CATALOG", "https://models.github.ai/catalog/models"))
    github_cache: Path = field(
        default_factory=lambda: ROOT / os.environ.get("GITHUB_CACHE",
                                                      "github_models.json"))
    # --- health ----------------------------------------------------------
    # A wearable's numbers, compared against your own baseline. Backends:
    #   file  a JSON/CSV your device exports — works with anything
    #   oura  Oura v2 API
    #   none  off
    health_backend: str = field(
        default_factory=lambda: os.environ.get("HEALTH_BACKEND", "none"))
    health_file: Path = field(
        default_factory=lambda: ROOT / os.environ.get("HEALTH_FILE", "health_input.json"))
    oura_token: str = field(default_factory=lambda: os.environ.get("OURA_TOKEN", ""))
    health_history: Path = field(
        default_factory=lambda: ROOT / os.environ.get("HEALTH_HISTORY", "health.json"))
    health_interval: float = field(
        default_factory=lambda: _float("HEALTH_INTERVAL", 1800.0))
    health_baseline_days: int = field(
        default_factory=lambda: _int("HEALTH_BASELINE_DAYS", 14))
    # A session this far above your recent normal is the thing worth flagging:
    # the trigger for exertional trouble is the jump, not the absolute effort.
    health_load_sigmas: float = field(
        default_factory=lambda: _float("HEALTH_LOAD_SIGMAS", 2.5))

    # Health questions and health alerts go to THESE models, never to the
    # free gateway — a rotating cast of providers is the wrong place for this.
    # Blank means: refuse to answer rather than send it somewhere else.
    health_models: str = field(default_factory=lambda: os.environ.get(
        "HEALTH_MODELS", "claude-opus-5"))
    symptom_log: Path = field(
        default_factory=lambda: ROOT / os.environ.get("SYMPTOM_LOG", "symptoms.jsonl"))

    # What counts as a red flag is between you and your doctor, so all four
    # lists live here rather than in the code. Within a rule `+` means AND
    # and `|` means OR; rules are separated by commas.
    #
    # These are a starting point across the things that put people in
    # hospital quickly — not a medical document, and worth going through
    # with your GP so they match you rather than a generic adult.
    redflag_emergency: str = field(default_factory=lambda: os.environ.get(
        "REDFLAG_EMERGENCY",
        # cardiac
        "chest + pain|tight|tightness|crushing|pressure,"
        "pain + arm|jaw|neck + spread|spreading|radiat,"
        # stroke — FAST
        "face + droop|drooping|numb,"
        "speech + slurred|slurring|can't speak|cannot speak,"
        "arm|leg + numb|weak + one side|left side|right side|suddenly,"
        "sudden + confusion|vision loss|worst headache|blinding headache,"
        # breathing / anaphylaxis
        "can't breathe|cannot breathe|struggling to breathe|gasping,"
        "throat + closing|swelling|tight,"
        "lips|tongue|face + swelling|swollen,"
        # collapse and bleeding
        "passed out|fainted|blacked out|collapsed|unconscious,"
        "bleeding + heavy|won't stop|will not stop|soaking,"
        "seizure|fitting|convulsion,"
        # sepsis-ish
        "rash + doesn't fade|does not fade|glass test,"
        "fever|temperature + confused|confusion|drowsy|slurred"))
    redflag_crisis: str = field(default_factory=lambda: os.environ.get(
        "REDFLAG_CRISIS",
        "kill myself|end my life|end it all|don't want to be here|"
        "dont want to be here|want to die|suicidal|self harm|hurt myself|"
        "no point going on|better off without me"))
    redflag_urgent: str = field(default_factory=lambda: os.environ.get(
        "REDFLAG_URGENT",
        # rhabdomyolysis
        "urine|pee|peeing|wee|weeing + dark|brown|cola|tea|red|black,"
        "not passing|no urine|not been|barely + urine|pee|weeing,"
        "swelling|swollen + bad|severe|really|very|huge,"
        "can't move|cannot move|can't walk|cannot walk,"
        # cardiac / circulation, short of emergency
        "palpitations,heart + racing|pounding|skipping|irregular,"
        "breathless + lying down|at rest|walking,"
        "calf + pain|swollen|hot,"
        # infection
        "fever|temperature + 39|40|shivering|rigors,"
        "wound + hot|red|spreading|pus,"
        # neuro / abdominal
        "headache + sudden|worst|vomiting,"
        "vision + blurred|double|lost,"
        "abdominal|stomach|belly + severe|rigid|worst,"
        "vomiting + blood|coffee,"
        "stool|poo + black|tarry|blood"))
    redflag_watch: str = field(default_factory=lambda: os.environ.get(
        "REDFLAG_WATCH",
        "muscle|legs|arms|shoulders|back + pain|sore|ache|aching|hurts,"
        "weak|weakness,swollen|swelling,stiff,cramp|cramping,"
        "nausea|nauseous|sick,vomit|vomiting|threw up,dizzy|lightheaded,"
        "headache,tired|exhausted|wiped|drained,"
        "dark|brown + urine|pee,"
        "poor sleep|couldn't sleep|not sleeping|insomnia|slept badly|sleeping badly|bad sleep|barely slept,"
        "low mood|anxious|anxiety|panicky|stressed"))

    # --- alerts -----------------------------------------------------------
    # Speaking aloud only reaches you if you are in the room. This pushes to
    # your phone too, so a red flag finds you in the garden or asleep.
    #   ntfy     free, no account, an app on both stores
    #   webhook  POST the JSON somewhere of your own
    #   none     off
    alert_backend: str = field(
        default_factory=lambda: os.environ.get("ALERT_BACKEND", "none"))
    ntfy_server: str = field(
        default_factory=lambda: os.environ.get("NTFY_SERVER", "https://ntfy.sh"))
    # Anyone who knows the topic can read your alerts, so make it long and
    # unguessable — it is a password, not a name.
    ntfy_topic: str = field(default_factory=lambda: os.environ.get("NTFY_TOPIC", ""))
    alert_webhook: str = field(
        default_factory=lambda: os.environ.get("ALERT_WEBHOOK", ""))
    # The least severe thing worth buzzing your phone for. `watch` sends
    # everything logged; `urgent` only sends what needs seeing today.
    alert_min_level: str = field(
        default_factory=lambda: os.environ.get("ALERT_MIN_LEVEL", "urgent"))

    # --- music ------------------------------------------------------------
    # PKCE, so there is no client secret to keep anywhere. Playback control
    # needs Spotify Premium — that is Spotify's rule; a free account can see
    # what is playing but not change it.
    spotify_client_id: str = field(
        default_factory=lambda: os.environ.get("SPOTIFY_CLIENT_ID", ""))
    spotify_auth_port: int = field(
        default_factory=lambda: _int("SPOTIFY_AUTH_PORT", 8888))
    # Live credentials to your account. Git-ignored, and written 0600.
    spotify_token_path: Path = field(
        default_factory=lambda: ROOT / os.environ.get("SPOTIFY_TOKENS",
                                                      "spotify_tokens.json"))

    # --- how she addresses you -------------------------------------------
    # Used in every reply, on every path. The system prompt asks for it and
    # `address.py` guarantees it, because "nearly always" is exactly the
    # thing that gets noticed. Blank switches it off entirely.
    address: str = field(
        default_factory=lambda: os.environ.get("ADDRESS", "sir"))

    # --- wake word -------------------------------------------------------
    wake_enabled: bool = field(default_factory=lambda: _bool("WAKE_ENABLED", True))
    # The SPOKEN trigger, which is not the same thing as the name. A wake word
    # is a trained model, so this cannot be renamed the way everything else
    # was: openWakeWord ships four phrases and "hey vesper" is not one of
    # them. You can train it — free, about an hour, in a browser — and then
    # set WAKE_MODEL=hey_vesper.onnx. See WAKE_WORD.md.
    #
    # Until then the default is "hey jarvis", which is the closest ready-made
    # phrase. Anything unloadable stops with an explanation rather than
    # falling back to a phrase you are not saying.
    wake_model: str = field(
        default_factory=lambda: os.environ.get("WAKE_MODEL", "hey_jarvis"))
    # Blank means "derive it from whichever model is loaded", which is what
    # keeps the interface from telling you to say one thing while the
    # detector listens for another. Set it only to override the wording.
    wake_phrase: str = field(
        default_factory=lambda: os.environ.get("WAKE_PHRASE", ""))
    wake_threshold: float = field(
        default_factory=lambda: _float("WAKE_THRESHOLD", 0.5))

    # --- conversation -----------------------------------------------------
    # After Vesper answers it keeps listening for this long, so a follow-up
    # needs no wake word. This is most of what separates talking to someone
    # from operating a machine. 0 turns it off.
    follow_up_seconds: float = field(
        default_factory=lambda: _float("FOLLOW_UP_SECONDS", 25.0))
    # Talking over it stops it mid-sentence.
    barge_in: bool = field(default_factory=lambda: _bool("BARGE_IN", True))
    # How much louder than the room (or than its own voice) you must be for
    # that to count. Lower if it ignores you; raise if it cuts itself off.
    barge_in_over: float = field(
        default_factory=lambda: _float("BARGE_IN_OVER", 3.0))

    # --- speech ----------------------------------------------------------
    stt_enabled: bool = field(default_factory=lambda: _bool("STT_ENABLED", True))
    stt_model: str = field(default_factory=lambda: os.environ.get("STT_MODEL", "base.en"))
    stt_device: str = field(default_factory=lambda: os.environ.get("STT_DEVICE", "cpu"))
    stt_compute_type: str = field(
        default_factory=lambda: os.environ.get("STT_COMPUTE_TYPE", "int8"))
    # How long a pause ends the command, and the hard ceiling on one command.
    stt_silence_seconds: float = field(
        default_factory=lambda: _float("STT_SILENCE_SECONDS", 1.2))
    stt_max_seconds: float = field(
        default_factory=lambda: _float("STT_MAX_SECONDS", 15.0))

    tts_backend: str = field(default_factory=lambda: os.environ.get("TTS_BACKEND", "piper"))
    piper_model: str = field(
        default_factory=lambda: os.environ.get("PIPER_MODEL", "en_GB-alan-medium"))
    elevenlabs_api_key: str = field(
        default_factory=lambda: os.environ.get("ELEVENLABS_API_KEY", ""))
    elevenlabs_voice_id: str = field(
        default_factory=lambda: os.environ.get("ELEVENLABS_VOICE_ID", ""))
    # Their model names change and old ones get retired. Blank uses a
    # sensible current default; set it if they reject that one.
    elevenlabs_model: str = field(
        default_factory=lambda: os.environ.get("ELEVENLABS_MODEL", ""))

    # --- vision ----------------------------------------------------------
    vision_enabled: bool = field(default_factory=lambda: _bool("VISION_ENABLED", False))
    camera_index: int = field(default_factory=lambda: _int("CAMERA_INDEX", 0))
    yolo_model: str = field(default_factory=lambda: os.environ.get("YOLO_MODEL", "yolov8n.pt"))
    # Detection is throttled: seeing the room twice a second is plenty, and
    # running YOLO on every frame is what makes these systems expensive.
    vision_interval: float = field(
        default_factory=lambda: _float("VISION_INTERVAL", 2.0))
    vision_confidence: float = field(
        default_factory=lambda: _float("VISION_CONFIDENCE", 0.45))

    # --- home assistant --------------------------------------------------
    ha_enabled: bool = field(default_factory=lambda: _bool("HA_ENABLED", False))
    ha_url: str = field(default_factory=lambda: os.environ.get("HA_URL", ""))
    ha_token: str = field(default_factory=lambda: os.environ.get("HA_TOKEN", ""))
    ha_poll_interval: float = field(
        default_factory=lambda: _float("HA_POLL_INTERVAL", 10.0))

    # --- news ------------------------------------------------------------
    # Headlines are polled into the world state, so Vesper always has them
    # without searching. Comma-separated RSS/Atom URLs — add your own.
    news_enabled: bool = field(default_factory=lambda: _bool("NEWS_ENABLED", True))
    news_feeds: str = field(default_factory=lambda: os.environ.get(
        "NEWS_FEEDS",
        "https://feeds.bbci.co.uk/news/rss.xml,"
        "https://feeds.bbci.co.uk/news/business/rss.xml"))
    news_interval: float = field(
        default_factory=lambda: _float("NEWS_INTERVAL", 900.0))   # 15 minutes
    news_per_feed: int = field(default_factory=lambda: _int("NEWS_PER_FEED", 10))
    news_keep: int = field(default_factory=lambda: _int("NEWS_KEEP", 12))
    # How many headlines go into the prompt each turn. All of them would be
    # accurate and expensive; the top few are what "keeping up" actually means.
    news_in_context: int = field(default_factory=lambda: _int("NEWS_IN_CONTEXT", 6))
    # Words that make a new headline worth waking the brain over. Keep this
    # tight: every match costs a model call, and most news is not urgent.
    news_watch: str = field(default_factory=lambda: os.environ.get(
        "NEWS_WATCH", "breaking,emergency,evacuat,earthquake,explosion,"
                      "crash,collapse,resign,war,strike,recall,outage"))

    # --- phone bridge ----------------------------------------------------
    # An HTTP endpoint so your phone can ask the laptop things. Off unless
    # you set a token: it spends API credit, so it never opens unauthenticated.
    server_enabled: bool = field(default_factory=lambda: _bool("SERVER_ENABLED", False))
    # 0.0.0.0 so the phone on your wifi can reach it. On an untrusted network
    # (a café, a shared flat) set 127.0.0.1 and reach it over Tailscale instead.
    server_host: str = field(default_factory=lambda: os.environ.get("SERVER_HOST", "0.0.0.0"))
    server_port: int = field(default_factory=lambda: _int("SERVER_PORT", 8765))
    server_token: str = field(default_factory=lambda: os.environ.get("SERVER_TOKEN", ""))
    # Whether the laptop says the answer out loud when the phone asks. Off:
    # you're usually not in the room.
    server_speak_aloud: bool = field(
        default_factory=lambda: _bool("SERVER_SPEAK_ALOUD", False))

    # --- behaviour -------------------------------------------------------
    # Proactive speech is opt-in. An assistant that talks at you unprompted
    # is the fastest way to get itself switched off.
    proactive_enabled: bool = field(
        default_factory=lambda: _bool("PROACTIVE_ENABLED", True))
    # Minimum gap between unprompted remarks, whatever the triggers say.
    proactive_cooldown: float = field(
        default_factory=lambda: _float("PROACTIVE_COOLDOWN", 120.0))

    map_path: Path = field(
        default_factory=lambda: ROOT / os.environ.get("MAP_PATH", "map.json"))
    state_path: Path = field(
        default_factory=lambda: ROOT / os.environ.get("STATE_PATH", "state.json"))
    log_path: Path = field(
        default_factory=lambda: ROOT / os.environ.get("LOG_PATH", "conversations.jsonl"))
    log_level: str = field(default_factory=lambda: os.environ.get("LOG_LEVEL", "INFO"))

    def describe(self) -> str:
        """One-line-per-subsystem summary, printed at boot."""
        def mark(on: bool) -> str:
            return "on " if on else "off"
        return "\n".join([
            f"  reasoning   {mark(bool(self.anthropic_api_key))} "
            f"{self.model} (effort={self.effort})",
            f"  wake word   {mark(self.wake_enabled)} {self.wake_model}",
            f"  speech in   {mark(self.stt_enabled)} faster-whisper {self.stt_model}",
            f"  speech out  on  {self.tts_backend}",
            f"  vision      {mark(self.vision_enabled)} {self.yolo_model} "
            f"every {self.vision_interval:g}s",
            f"  home        {mark(self.ha_enabled)} {self.ha_url or '(no url)'}",
            f"  news        {mark(self.news_enabled)} "
            f"{len([u for u in self.news_feeds.split(',') if u.strip()])} feed(s) "
            f"every {self.news_interval / 60:g} min",
            f"  phone       {mark(self.server_enabled and bool(self.server_token))} "
            f"port {self.server_port}",
            f"  proactive   {mark(self.proactive_enabled)} "
            f"(cooldown {self.proactive_cooldown:g}s)",
        ])


def setup_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s  %(name)-18s %(levelname)-7s %(message)s",
        datefmt="%H:%M:%S",
    )
    # These are chatty and we have our own logging around them.
    for noisy in ("httpx", "httpcore", "anthropic", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


CONFIG = Config()
