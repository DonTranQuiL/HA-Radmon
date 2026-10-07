#!/usr/bin/env python3
"""Daily check that the radmon.org endpoints Radmon uses still behave as documented.

Endpoints (see custom_components/radmon_scrape/api.py):
  * radmon.php?function=ping                    -> "pong"
  * radmon.php?function=showuserpage&user=X     -> station page with
    '<h2 class="serif">N CPM on YYYY-MM-DD HH:MM:SS</h2>' and the
    '<h3 class="serif">location at coordinates lat, lon<br>device<br></h3>' block
  * radmon.php?function=lastreading&user=X      -> "No password specified" without a
    password and "Incorrect." with a wrong one (owner mode depends on this)

Only six tiny requests a day. Results are reduced to a stable fingerprint in
.memory/radmon_api.json; an issue is opened only when a check newly fails.
Timeouts and 5xx count as transient. An optional LLM (xAI first, then
OpenRouter) adds a short impact summary.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

import requests

COMPONENT = "custom_components/radmon_scrape/"
API_URL = "https://radmon.org/radmon.php"
HEADERS = {
    "User-Agent": "HomeAssistant-Radmon-feed-watcher (+https://github.com/DonTranQuiL/HA-Radmon)"
}
TIMEOUT = 30
MEMORY_PATH = Path(".memory/radmon_api.json")
REPORT_PATH = Path("feed_watch_report.md")
# Two long-running public stations; the page check only fails if *both* look wrong.
SAMPLE_STATIONS = ("Simomax", "lImbus")
# The auth checks use a made-up station so no real account sees failed logins.
PROBE_USER = "ha-radmon-watcher-probe"

READING_RE = re.compile(
    r'<h2 class="serif">\s*-?\d+(?:\.\d+)?\s*CPM\s+on\s+\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\s*</h2>',
    re.I,
)
DETAILS_RE = re.compile(
    r'<h3 class="serif">[^<]*at coordinates\s*-?[\d.]+\s*,\s*-?[\d.]+<br>', re.I
)


class Transient(Exception):
    """Network trouble that should not open an issue."""


def get(params: dict[str, str]) -> str:
    try:
        resp = requests.get(API_URL, params=params, headers=HEADERS, timeout=TIMEOUT)
    except requests.RequestException as exc:
        raise Transient(type(exc).__name__) from exc
    if resp.status_code >= 500 or resp.status_code == 429:
        raise Transient(f"HTTP {resp.status_code}")
    if resp.status_code != 200:
        return f"HTTP {resp.status_code}"
    return resp.text


def check_ping() -> list[str]:
    text = get({"function": "ping"})
    return (
        []
        if text.strip().startswith("pong")
        else [f"ping returned {text[:80]!r} instead of 'pong'"]
    )


def check_station_page() -> list[str]:
    problems: list[list[str]] = []
    for station in SAMPLE_STATIONS:
        text = get({"function": "showuserpage", "user": station})
        found = []
        if not READING_RE.search(text):
            found.append(
                "reading line '<h2 class=\"serif\">N CPM on <date></h2>' not found"
            )
        if not DETAILS_RE.search(text):
            found.append(
                "location/coordinates block '<h3 class=\"serif\">... at coordinates lat, lon<br>' not found"
            )
        if not found:
            return []
        problems.append(found)
    return [f"{p} (stations {', '.join(SAMPLE_STATIONS)})" for p in problems[0]]


def check_lastreading_auth() -> list[str]:
    out = []
    text = get({"function": "lastreading", "user": PROBE_USER})
    if "no password" not in text.lower():
        out.append(
            f"lastreading without password no longer says 'No password specified': {text[:80]!r}"
        )
    text = get({"function": "lastreading", "user": PROBE_USER, "password": "invalid"})
    if not text.strip().lower().startswith("incorrect"):
        out.append(
            f"lastreading with an unknown station/password no longer says 'Incorrect.': {text[:80]!r}"
        )
    return out


CHECKS = {
    "ping": check_ping,
    "showuserpage": check_station_page,
    "lastreading_auth": check_lastreading_auth,
}


def llm_summary(report: str) -> str:
    try:
        from openai import OpenAI
    except ImportError:
        return ""
    if os.getenv("XAI_API_KEY"):
        client, model = (
            OpenAI(base_url="https://api.x.ai/v1", api_key=os.environ["XAI_API_KEY"]),
            "grok-4",
        )
    elif os.getenv("OPENROUTER_API_KEY"):
        client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=os.environ["OPENROUTER_API_KEY"],
        )
        model = "deepseek/deepseek-v4.1-flash"
    else:
        return ""
    prompt = (
        f"radmon.org changed behaviour that the Home Assistant integration {COMPONENT} relies on. "
        f"In at most 5 bullets, explain the user impact and what to change in api.py.\n\n{report}"
    )
    try:
        completion = client.chat.completions.create(
            model=model, messages=[{"role": "user", "content": prompt}]
        )
        return completion.choices[0].message.content or ""
    except Exception as exc:  # noqa: BLE001
        print(f"LLM summary skipped: {exc}")
        return ""


def main() -> int:
    previous: dict[str, list[str]] = {}
    if MEMORY_PATH.is_file():
        try:
            previous = json.loads(MEMORY_PATH.read_text(encoding="utf-8"))
        except ValueError:
            previous = {}
    current: dict[str, list[str]] = {}
    fresh: dict[str, list[str]] = {}
    for name, check in CHECKS.items():
        try:
            problems = check()
        except Transient as exc:
            print(f"{name:18} transient ({exc}), keeping previous state")
            current[name] = previous.get(name, [])
            continue
        current[name] = problems
        print(f"{name:18} {'ok' if not problems else 'PROBLEM'}")
        new = [p for p in problems if p not in previous.get(name, [])]
        if new:
            fresh[name] = new

    MEMORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    MEMORY_PATH.write_text(
        json.dumps(current, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    if not fresh:
        print("No breaking radmon.org changes.")
        return 0

    lines = [
        "## radmon.org change detected",
        "",
        f"The daily watcher found changes that affect `{COMPONENT}`.",
        "",
    ]
    for name, items in fresh.items():
        lines.append(f"### `{name}`")
        lines += [f"- {item}" for item in items]
        lines.append("")
    report = "\n".join(lines)
    summary = llm_summary(report)
    if summary:
        report += "\n### AI impact summary\n\n" + summary + "\n"
    REPORT_PATH.write_text(report, encoding="utf-8")
    print(report)
    env_file = os.getenv("GITHUB_ENV")
    if env_file:
        with open(env_file, "a", encoding="utf-8") as fh:
            fh.write("SCHEMA_CHANGED=true\n")
            fh.write(f"ISSUE_TITLE=radmon.org change: {', '.join(sorted(fresh))}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
