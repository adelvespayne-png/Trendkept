"""Tool schemas handed to Claude.

Descriptions are prescriptive about *when* to call each tool, not just what
it does — current models reach for tools conservatively, and the trigger
condition in the description is what lifts the call rate.

`stay_silent` is the important one: when Vesper is woken by a trigger rather
than by you, saying nothing must be a first-class option, or it becomes the
assistant that comments on everything.
"""

from __future__ import annotations

from typing import Any, Dict, List


def _map_tools() -> List[Dict[str, Any]]:
    """The mainframe map. Named by what the user calls things, never by id —
    the user says "put it under Content", and asking the model to invent
    internal ids just gives it something new to get wrong."""
    return [
        {
            "name": "map_read",
            "description": (
                "Read the user's project map — an outline of every branch and "
                "point. Call this before answering anything about their "
                "projects, plans, or what they have on, and before adding to "
                "the map, so you put things in the right place."
            ),
            "input_schema": {"type": "object", "properties": {},
                             "additionalProperties": False},
        },
        {
            "name": "map_add",
            "description": (
                "Add a point to the map. Call this whenever the user wants "
                "something recorded, planned, or remembered against a project. "
                "Adding several related points in one turn is normal and good: "
                "call this once per point. To start a whole new project, add "
                "it with no parent, then add its points underneath."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "text": {"type": "string",
                             "description": "The point, in the user's own words, kept short."},
                    "parent": {"type": "string",
                               "description": ("What it goes under, as the user would "
                                               "name it. Omit for a new top-level project.")},
                },
                "required": ["text"],
                "additionalProperties": False,
            },
        },
        {
            "name": "map_update",
            "description": (
                "Change something already on the map: tick it off, reopen it, "
                "rename it, move it under a different branch, or delete it. "
                "Deleting removes everything underneath, so prefer marking done."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "What to change, as the user names it."},
                    "action": {"type": "string",
                               "enum": ["done", "reopen", "rename", "move", "delete", "link"]},
                    "value": {"type": "string",
                              "description": ("The new name for rename, the new parent for "
                                              "move, the other point for link. Ignored otherwise.")},
                },
                "required": ["name", "action"],
                "additionalProperties": False,
            },
        },
    ]


def tool_definitions(include_home: bool = True,
                     include_web: bool = True,
                     include_map: bool = True,
                     include_search: bool = True,
                     include_health: bool = False) -> List[Dict[str, Any]]:
    tools: List[Dict[str, Any]] = [
        {
            "name": "answer",
            "description": (
                "Speak a reply to the user. Call this for anything the user "
                "should hear — answering their question, confirming an "
                "action, or greeting them. Keep it to one or two spoken "
                "sentences: this is read aloud, not displayed."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "Exactly what to say, in natural spoken English.",
                    }
                },
                "required": ["text"],
                "additionalProperties": False,
            },
        },
        {
            "name": "stay_silent",
            "description": (
                "Say nothing at all. Call this when you were woken by an "
                "ambient event rather than by the user, and speaking would "
                "be noise — a routine change, something the user already "
                "knows, or anything not worth interrupting them for. "
                "Preferring this over a needless remark is correct behaviour."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "reason": {
                        "type": "string",
                        "description": "Why silence is the right call (logged, not spoken).",
                    }
                },
                "required": ["reason"],
                "additionalProperties": False,
            },
        },
        {
            "name": "get_weather",
            "description": (
                "Current weather and today's forecast for a place. Call this "
                "whenever the answer depends on real weather — the user asks "
                "about conditions, temperature, rain, or what to wear. Do not "
                "answer weather questions from memory."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "Town or city name, e.g. 'Bristol'.",
                    }
                },
                "required": ["location"],
                "additionalProperties": False,
            },
        },
        {
            "name": "create_reminder",
            "description": (
                "Write a reminder to the user's local reminder file. Call "
                "this when the user asks to be reminded of something or to "
                "note something down. Confirm afterwards with `answer`."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "What to remember, in the user's own words.",
                    },
                    "when": {
                        "type": "string",
                        "description": (
                            "When it matters, as the user said it "
                            "('tomorrow morning', '18:00'). Empty if unspecified."
                        ),
                    },
                },
                "required": ["text"],
                "additionalProperties": False,
            },
        },
        {
            "name": "list_reminders",
            "description": (
                "Read back the reminders already saved. Call this when the "
                "user asks what they have to do, what is on their list, or "
                "whether they noted something down."
            ),
            "input_schema": {
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
        },
        {
            "name": "recall_world",
            "description": (
                "Re-read the live sensor state — who is visible, what objects "
                "are in view, when there was last motion, device states. Call "
                "this when the user asks about the room right now ('is anyone "
                "in?', 'did I leave the light on?') and the summary you were "
                "given may be stale."
            ),
            "input_schema": {
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
        },
    ]

    if include_home:
        tools.append({
            "name": "set_device",
            "description": (
                "Switch a smart-home device on or off via Home Assistant. "
                "Call this only when the user clearly asked for it. Never "
                "change a device on your own initiative from an ambient "
                "trigger — mention it with `answer` instead and let them decide."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "entity_id": {
                        "type": "string",
                        "description": (
                            "Home Assistant entity id, e.g. 'light.kitchen'. "
                            "Use one you have seen in the device state; do not invent ids."
                        ),
                    },
                    "state": {
                        "type": "string",
                        "enum": ["on", "off"],
                        "description": "Desired state.",
                    },
                },
                "required": ["entity_id", "state"],
                "additionalProperties": False,
            },
        })

    if include_search:
        tools.append({
            "name": "search_web",
            "description": (
                "Search the web and get back titles, links and snippets. Call "
                "this whenever the answer depends on something current, "
                "specific, or that you would otherwise be guessing at — news, "
                "prices, whether a thing exists, what someone said. Follow a "
                "promising result with `fetch_page` to read it properly. This "
                "search runs on the user's own machine, so it works on every "
                "provider."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string",
                              "description": "What to search for, as you would type it."},
                },
                "required": ["query"],
                "additionalProperties": False,
            },
        })

    if include_health:
        tools.append({
            "name": "log_symptom",
            "description": (
                "Record how the user says their body feels, in their own "
                "words. Call this the moment they mention any physical "
                "symptom — soreness, weakness, urine colour, nausea, "
                "dizziness, chest pain — even in passing. The result "
                "contains a `level` and an `instruction` decided by local "
                "code, not by you. If an instruction comes back, say it to "
                "them EXACTLY as written: do not soften it, do not reword "
                "it, do not add your own view of whether it applies."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "text": {"type": "string",
                             "description": "What they said, in their own words."},
                },
                "required": ["text"],
                "additionalProperties": False,
            },
        })
        tools.append({
            "name": "read_body",
            "description": (
                "Today's wearable numbers against the user's own 14-day "
                "baseline, plus any symptoms logged in the last three days. "
                "Call this before answering anything about how they are "
                "feeling, their training, their recovery, or their sleep."
            ),
            "input_schema": {"type": "object", "properties": {},
                             "additionalProperties": False},
        })

    tools.append({
        "name": "fetch_page",
        "description": (
            "Fetch a web page and read its text. Call this when the user "
            "names a site, gives a URL, or you need the current contents of a "
            "specific page. This works everywhere, including when the richer "
            "web search is unavailable — so on a backup provider it is your "
            "only way to see the live web."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {"type": "string",
                        "description": "Full URL, including https://"},
            },
            "required": ["url"],
            "additionalProperties": False,
        },
    })

    if include_map:
        tools.extend(_map_tools())

    if include_web:
        # Server-side tools: these run on Anthropic's machines, not here, so
        # there is nothing for the executor to implement. They come back as
        # `server_tool_use` blocks, which the brain's loop ignores — it only
        # acts on our own `tool_use` blocks.
        tools.append({"type": "web_search_20260209", "name": "web_search"})
        tools.append({"type": "web_fetch_20260209", "name": "web_fetch"})

    return tools


# Calling either of these ends the turn — the brain stops looping.
TERMINAL_TOOLS = {"answer", "stay_silent"}
