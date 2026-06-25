#!/usr/bin/env python3
"""
WC 2026 Bracket — Daily Update Script
--------------------------------------
1. Calls Claude API with the bracket skill prompt
2. Extracts the generated HTML
3. Pushes it to GitHub Pages as index.html

Usage:
  python update_bracket.py

Required env vars:
  ANTHROPIC_API_KEY   — your Anthropic API key
  GITHUB_TOKEN        — GitHub personal access token (repo scope)
  GITHUB_REPO         — e.g. hugocytam/wc2026-bracket
"""

import os
import base64
import json
import datetime
import sys
import anthropic
import requests

# ── CONFIG ────────────────────────────────────────────────────────────────
GITHUB_REPO  = os.environ.get("GITHUB_REPO", "hugocytam/wc2026-bracket")
GITHUB_FILE  = "index.html"
GITHUB_BRANCH = "main"
COMMIT_MSG   = f"Auto-update bracket — {datetime.date.today().isoformat()}"

PROMPT = """Refresh the WC 2026 bracket.

Follow the wc2026-bracket skill exactly:
1. Fetch yesterday's results, today's schedule (with verified kickoff times ET), 
   current tournament odds from Polymarket/FanDuel, and PELE model match probabilities.
2. Verify bracket chain from references/bracket-chain.md — do not change pairings.
3. Recompute PDI for all teams based on confirmed group positions.
4. Render the full HTML with all 5 tabs: Bracket, Today·[DATE], Insights·[YESTERDAY], 
   Full GT Analysis, Methodology.
5. Run the validation gate (Step 4.5) before outputting — verify all kickoff times are 
   sourced, each team appears once in Today tab, bracket chain is correct.
6. Output ONLY the raw HTML — no markdown, no code fences, no explanation. 
   Start with <!DOCTYPE html> and end with </html>.
"""

# ── CLAUDE API ─────────────────────────────────────────────────────────────
def generate_html() -> str:
    print("⏳ Calling Claude API to regenerate bracket...")
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=16000,
        messages=[{"role": "user", "content": PROMPT}],
        tools=[{"type": "web_search_20250305", "name": "web_search"}],
    )

    # Extract text content from response
    html = ""
    for block in message.content:
        if block.type == "text":
            html += block.text

    # Strip any accidental markdown fences
    html = html.strip()
    if html.startswith("```"):
        html = html.split("```", 2)[-1]
        if html.startswith("html"):
            html = html[4:]
    if html.endswith("```"):
        html = html[:-3]
    html = html.strip()

    if not html.startswith("<!DOCTYPE"):
        print("❌ Claude didn't return valid HTML. Response preview:")
        print(html[:500])
        sys.exit(1)

    print(f"✅ HTML generated ({len(html):,} chars)")
    return html


# ── GITHUB API ─────────────────────────────────────────────────────────────
def get_current_sha() -> str | None:
    """Get the SHA of the current index.html (needed for updates)."""
    token = os.environ["GITHUB_TOKEN"]
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{GITHUB_FILE}"
    r = requests.get(url, headers={
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json"
    })
    if r.status_code == 200:
        return r.json()["sha"]
    elif r.status_code == 404:
        return None  # File doesn't exist yet
    else:
        print(f"❌ GitHub GET failed: {r.status_code} {r.text}")
        sys.exit(1)


def push_to_github(html: str) -> str:
    """Push index.html to GitHub, return the live URL."""
    token = os.environ["GITHUB_TOKEN"]
    sha = get_current_sha()

    payload = {
        "message": COMMIT_MSG,
        "content": base64.b64encode(html.encode("utf-8")).decode("utf-8"),
        "branch": GITHUB_BRANCH,
    }
    if sha:
        payload["sha"] = sha  # Required for updates

    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{GITHUB_FILE}"
    r = requests.put(url, headers={
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json",
        "Content-Type": "application/json",
    }, data=json.dumps(payload))

    if r.status_code in (200, 201):
        action = "updated" if sha else "created"
        print(f"✅ index.html {action} on GitHub")
        username = GITHUB_REPO.split("/")[0]
        repo = GITHUB_REPO.split("/")[1]
        return f"https://{username}.github.io/{repo}/"
    else:
        print(f"❌ GitHub PUT failed: {r.status_code}")
        print(r.text)
        sys.exit(1)


# ── MAIN ───────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # Check env vars
    missing = [v for v in ["ANTHROPIC_API_KEY", "GITHUB_TOKEN"] if not os.environ.get(v)]
    if missing:
        print(f"❌ Missing env vars: {', '.join(missing)}")
        print("   Set them with: export ANTHROPIC_API_KEY=... GITHUB_TOKEN=...")
        sys.exit(1)

    print(f"🚀 WC 2026 Bracket Daily Update — {datetime.date.today()}")
    print(f"   Repo: {GITHUB_REPO}")
    print()

    html = generate_html()
    url  = push_to_github(html)

    print()
    print(f"🌐 Live at: {url}")
    print("   GitHub Pages deploys in ~30 seconds.")
