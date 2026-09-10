#!/usr/bin/env python3
"""Fetch the last year of GitHub contributions into data/contributions.json.

Two sources, same output shape:
  1. GraphQL contributionCalendar when a token is available (GITHUB_TOKEN /
     GH_TOKEN env, or `gh auth token` locally) — exact counts.
  2. Scrape of the public https://github.com/users/<user>/contributions page
     (no token needed) — counts parsed from the per-day tooltips.

Output: {"user", "fetched_at", "source", "days": [{"date", "count", "level"}],
         "total", "longest_streak", "current_streak"}
Usage: python scripts/fetch_contributions.py [--user AltDoug] [--out data/contributions.json] [--scrape]
"""
import argparse
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import requests
from bs4 import BeautifulSoup

LEVELS = {"NONE": 0, "FIRST_QUARTILE": 1, "SECOND_QUARTILE": 2, "THIRD_QUARTILE": 3, "FOURTH_QUARTILE": 4}
QUERY = """query($login: String!) { user(login: $login) { contributionsCollection {
  contributionCalendar { totalContributions weeks { contributionDays { date contributionCount contributionLevel } } } } } }"""


def token() -> str | None:
    for var in ("GITHUB_TOKEN", "GH_TOKEN"):
        if os.environ.get(var):
            return os.environ[var]
    if shutil.which("gh"):
        r = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True)
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
    return None


def via_graphql(user: str, tok: str) -> list[dict]:
    r = requests.post("https://api.github.com/graphql", json={"query": QUERY, "variables": {"login": user}},
                      headers={"Authorization": f"bearer {tok}"}, timeout=30)
    r.raise_for_status()
    body = r.json()
    if "errors" in body:
        raise RuntimeError(body["errors"])
    weeks = body["data"]["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
    return [{"date": d["date"], "count": d["contributionCount"], "level": LEVELS[d["contributionLevel"]]}
            for w in weeks for d in w["contributionDays"]]


def via_scrape(user: str) -> list[dict]:
    r = requests.get(f"https://github.com/users/{user}/contributions",
                     headers={"User-Agent": "Mozilla/5.0 (profile-art bot)"}, timeout=30)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    tips = {t.get("for"): t.get_text(" ", strip=True) for t in soup.find_all("tool-tip")}
    days = []
    for cell in soup.select("td.ContributionCalendar-day[data-date]"):
        tip = tips.get(cell.get("id"), "")
        m = re.match(r"(\d[\d,]*|No) contribution", tip)
        count = 0 if not m or m.group(1) == "No" else int(m.group(1).replace(",", ""))
        days.append({"date": cell["data-date"], "count": count, "level": int(cell.get("data-level", 0))})
    if not days:
        raise RuntimeError("no day cells found — GitHub markup changed?")
    return sorted(days, key=lambda d: d["date"])


def streaks(days: list[dict]) -> tuple[int, int]:
    longest = run = 0
    for d in days:
        run = run + 1 if d["count"] else 0
        longest = max(longest, run)
    recent = list(reversed(days))
    if recent and recent[0]["count"] == 0:
        recent = recent[1:]  # today isn't over yet; an empty today doesn't break the streak
    current = 0
    for d in recent:
        if not d["count"]:
            break
        current += 1
    return longest, current


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--user", default="AltDoug")
    ap.add_argument("--out", default="data/contributions.json")
    ap.add_argument("--scrape", action="store_true", help="force the tokenless HTML path")
    a = ap.parse_args()

    tok = None if a.scrape else token()
    source = "graphql" if tok else "scrape"
    try:
        days = via_graphql(a.user, tok) if tok else via_scrape(a.user)
    except Exception as e:  # noqa: BLE001 — fall back once, loudly
        if not tok:
            raise
        print(f"graphql failed ({e}); falling back to scrape", file=sys.stderr)
        source, days = "scrape", via_scrape(a.user)

    longest, current = streaks(days)
    out = {
        "user": a.user,
        "fetched_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": source,
        "days": days,
        "total": sum(d["count"] for d in days),
        "longest_streak": longest,
        "current_streak": current,
    }
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(out, indent=1) + "\n")
    print(f"wrote {a.out}: {len(days)} days, {out['total']} contributions, "
          f"longest streak {longest}, current {current} (via {source})")


if __name__ == "__main__":
    main()
