#!/usr/bin/env python3
"""
Generate GitHub Streak Stats SVG
Theme: Dark background #0d1117, Red accent #E11D48
Clean, self-hosted, deterministic SVG.
"""

import os
import sys
import json
import urllib.request
from datetime import datetime, date, timedelta

def get_env_token():
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        # Try git credential helper if running locally
        try:
            import subprocess
            p = subprocess.Popen(["git", "credential", "fill"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
            out, _ = p.communicate(input="url=https://github.com\n")
            for line in out.splitlines():
                if line.startswith("password="):
                    token = line.split("=", 1)[1]
                    break
        except Exception:
            pass
    return token

def run_graphql(query, variables, token):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": variables}).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "User-Agent": "GitHub-Streak-Generator",
            "Content-Type": "application/json"
        }
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))

def fetch_streak_data(username, token):
    # 1. Fetch contribution years & user creation date
    q_years = """
    query($login: String!) {
      user(login: $login) {
        createdAt
        contributionsCollection {
          contributionYears
        }
      }
    }
    """
    res_years = run_graphql(q_years, {"login": username}, token)
    if "errors" in res_years or "data" not in res_years or not res_years["data"]["user"]:
        raise ValueError(f"Failed to fetch user data: {res_years.get('errors')}")

    user_data = res_years["data"]["user"]
    created_at_str = user_data["createdAt"]
    created_dt = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
    years = user_data["contributionsCollection"]["contributionYears"]

    # 2. Fetch all daily contributions
    days_map = {}
    total_contributions = 0

    for y in sorted(years):
        q_cal = f"""
        query($login: String!) {{
          user(login: $login) {{
            contributionsCollection(from: "{y}-01-01T00:00:00Z", to: "{y}-12-31T23:59:59Z") {{
              contributionCalendar {{
                totalContributions
                weeks {{
                  contributionDays {{
                    contributionCount
                    date
                  }}
                }}
              }}
            }}
          }}
        }}
        """
        res_cal = run_graphql(q_cal, {"login": username}, token)
        cal = res_cal["data"]["user"]["contributionsCollection"]["contributionCalendar"]
        total_contributions += cal["totalContributions"]
        for w in cal["weeks"]:
            for d in w["contributionDays"]:
                days_map[d["date"]] = d["contributionCount"]

    sorted_dates = sorted(days_map.keys())
    today_str = date.today().isoformat()
    yesterday_str = (date.today() - timedelta(days=1)).isoformat()

    history = [(d, days_map[d]) for d in sorted_dates if d <= today_str]

    # Calculate Longest Streak
    longest_streak = 0
    longest_start = ""
    longest_end = ""
    curr_run = 0
    curr_start = ""

    for d, count in history:
        if count > 0:
            if curr_run == 0:
                curr_start = d
            curr_run += 1
            if curr_run > longest_streak:
                longest_streak = curr_run
                longest_start = curr_start
                longest_end = d
        else:
            curr_run = 0

    # Calculate Current Streak
    current_streak = 0
    current_start = ""
    current_end = ""

    idx = len(history) - 1
    if idx >= 0:
        last_d, last_c = history[idx]
        check_idx = None
        if last_c > 0:
            check_idx = idx
        elif idx > 0 and history[idx - 1][1] > 0 and history[idx - 1][0] == yesterday_str:
            check_idx = idx - 1

        if check_idx is not None:
            current_end = history[check_idx][0]
            i = check_idx
            while i >= 0 and history[i][1] > 0:
                current_streak += 1
                current_start = history[i][0]
                i -= 1

    return {
        "total": total_contributions,
        "current_streak": current_streak,
        "current_start": current_start,
        "current_end": current_end,
        "longest_streak": longest_streak,
        "longest_start": longest_start,
        "longest_end": longest_end,
        "first_contrib": created_dt.strftime("%b %d, %Y"),
    }

def format_date_range(start_str, end_str):
    if not start_str or not end_str:
        return ""
    start_d = date.fromisoformat(start_str)
    end_d = date.fromisoformat(end_str)
    if start_d.year == end_d.year:
        return f"{start_d.strftime('%b %d')} - {end_d.strftime('%b %d')}"
    return f"{start_d.strftime('%b %d, %Y')} - {end_d.strftime('%b %d, %Y')}"

def generate_svg(data):
    total = f"{data['total']:,}"
    current = str(data["current_streak"])
    longest = str(data["longest_streak"])

    total_range = f"{data['first_contrib']} - Present"
    curr_range = format_date_range(data["current_start"], data["current_end"]) if data["current_streak"] > 0 else "No active streak"
    long_range = format_date_range(data["longest_start"], data["longest_end"]) if data["longest_streak"] > 0 else "None"

    # SVG layout dimensions: 495 x 195
    # Theme: bg #0d1117, border #30363d, red accent #E11D48, text #ffffff, subtext #8b949e
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="495" height="195" viewBox="0 0 495 195" fill="none" role="img" aria-label="GitHub Streak Stats">
  <defs>
    <style>
      .card-bg {{ fill: #0d1117; stroke: #30363d; stroke-width: 1; rx: 6px; }}
      .stat-num {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif; font-size: 28px; font-weight: 700; fill: #ffffff; text-anchor: middle; }}
      .stat-label {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif; font-size: 14px; font-weight: 600; fill: #E11D48; text-anchor: middle; letter-spacing: 0.5px; }}
      .stat-range {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif; font-size: 11px; font-weight: 400; fill: #8b949e; text-anchor: middle; }}
      .separator {{ stroke: #21262d; stroke-width: 1; stroke-linecap: round; }}
      .fire-icon {{ fill: #E11D48; }}
      .fire-ring {{ stroke: #E11D48; stroke-width: 3; fill: none; }}
    </style>
  </defs>

  <rect width="493" height="193" x="1" y="1" class="card-bg" />

  <!-- Separators -->
  <line x1="165" y1="35" x2="165" y2="160" class="separator" />
  <line x1="330" y1="35" x2="330" y2="160" class="separator" />

  <!-- Column 1: Total Contributions -->
  <g transform="translate(82, 0)">
    <text x="0" y="78" class="stat-num">{total}</text>
    <text x="0" y="108" class="stat-label">Total Contributions</text>
    <text x="0" y="132" class="stat-range">{total_range}</text>
  </g>

  <!-- Column 2: Current Streak -->
  <g transform="translate(247, 0)">
    <!-- Ring indicator -->
    <circle cx="0" cy="42" r="18" class="fire-ring" opacity="0.3" />
    <!-- Fire SVG icon -->
    <path class="fire-icon" transform="translate(-10, 31) scale(0.85)" d="M12 23c6.075 0 11-4.925 11-11 0-4.52-2.73-8.41-6.63-10.13-.53-.23-1.13.1-1.2.67-.18 1.48-.96 2.82-2.18 3.65-1.22.83-2.6 1.15-3.8 2.37-1.57 1.6-2.19 3.96-2.19 6.44 0 .34.02.68.07 1.01-1.39-1.22-2.22-2.98-2.25-4.91 0-.58-.58-.98-1.12-.76C2.07 10.97 1 13.38 1 16c0 3.87 3.13 7 7 7h4zm0-2c-2.76 0-5-2.24-5-5 0-1.42.59-2.71 1.54-3.62.39-.37.49-.96.24-1.44-.24-.49-.78-.77-1.32-.69C6.63 10.42 6 11.64 6 13c0 .55.45 1 1 1s1-.45 1-1c0-1.78.93-3.4 2.45-4.29 1.1-.64 2.15-.99 3.09-1.95 1.02-1.04 1.46-2.39 1.46-3.76 2.65 1.61 4.5 4.54 4.5 7.9 0 4.97-4.03 9-9 9z"/>
    <text x="0" y="92" class="stat-num">{current}</text>
    <text x="0" y="118" class="stat-label">Current Streak</text>
    <text x="0" y="142" class="stat-range">{curr_range}</text>
  </g>

  <!-- Column 3: Longest Streak -->
  <g transform="translate(412, 0)">
    <text x="0" y="78" class="stat-num">{longest}</text>
    <text x="0" y="108" class="stat-label">Longest Streak</text>
    <text x="0" y="132" class="stat-range">{long_range}</text>
  </g>
</svg>
"""
    return svg

def main():
    username = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("GITHUB_REPOSITORY_OWNER", "Axoril1")
    output_path = sys.argv[2] if len(sys.argv) > 2 else "dist/streak.svg"

    token = get_env_token()
    if not token:
        print("Error: GITHUB_TOKEN or GH_TOKEN not found.", file=sys.stderr)
        sys.exit(1)

    print(f"Fetching streak stats for user: {username}...")
    data = fetch_streak_data(username, token)
    print(f"Data: Total={data['total']}, Current={data['current_streak']}, Longest={data['longest_streak']}")

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    svg_content = generate_svg(data)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(svg_content.strip() + "\n")

    print(f"Successfully generated streak SVG at {output_path}")

if __name__ == "__main__":
    main()
