"""Render profile charts using only public GitHub data; no credentials needed."""

import argparse
import calendar
import json
import re
from collections import Counter
from datetime import datetime
from html import escape
from html.parser import HTMLParser
from pathlib import Path
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

OWNER = "startificial"
ROOT = Path(__file__).resolve().parents[1]


class Contributions(HTMLParser):
    def __init__(self):
        super().__init__()
        self.dates = {}
        self.counts = {}
        self.target = None
        self.text = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "td" and "data-date" in attrs:
            self.dates[attrs["id"]] = attrs["data-date"]
        if tag == "tool-tip" and attrs.get("for", "").startswith("contribution-day-"):
            self.target = attrs["for"]
            self.text = []

    def handle_data(self, data):
        if self.target:
            self.text.append(data)

    def handle_endtag(self, tag):
        if tag == "tool-tip" and self.target:
            label = "".join(self.text).strip()
            match = re.match(r"(No|[\d,]+) contributions? on ", label)
            if not match:
                raise ValueError(f"Unrecognized public contribution label: {label}")
            self.counts[self.target] = 0 if match[1] == "No" else int(match[1].replace(",", ""))
            self.target = None

    def days(self):
        if len(self.dates) < 350 or self.dates.keys() != self.counts.keys():
            raise ValueError("Incomplete contribution calendar; keeping existing charts")
        return sorted(({"date": date, "count": self.counts[key]} for key, date in self.dates.items()), key=lambda d: d["date"])


def fetch(url):
    accept = "application/json" if url.startswith("https://api.github.com/") else "text/html"
    request = Request(url, headers={"User-Agent": f"{OWNER}-profile", "Accept": accept})
    with urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8")


def load_repos():
    repos = []
    page = 1
    while True:
        batch = json.loads(fetch(f"https://api.github.com/users/{OWNER}/repos?per_page=100&page={page}&type=owner"))
        if not isinstance(batch, list):
            raise ValueError("Expected a public repository list")
        repos.extend(batch)
        if len(batch) < 100:
            return repos
        page += 1


def render(data, dark):
    p = {"bg": "#0d1117", "ink": "#e6edf3", "muted": "#9da7b3", "line": "#30363d", "bar": "#7c9cf5", "accent": "#70d6ba", "track": "#21262d"} if dark else {"bg": "#ffffff", "ink": "#1f2328", "muted": "#59636e", "line": "#d8dee4", "bar": "#5273d0", "accent": "#23836d", "track": "#f0f3f6"}
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="900" height="365" viewBox="0 0 900 365" role="img" aria-labelledby="title desc">', '<title id="title">JJ — GitHub activity</title>', '<desc id="desc">Monthly profile contributions, including publicly displayed private contribution counts, and primary languages of public non-fork repositories.</desc>', f'<rect x=".5" y=".5" width="899" height="364" rx="12" fill="{p["bg"]}" stroke="{p["line"]}"/>', '<g font-family="-apple-system, BlinkMacSystemFont, Segoe UI, sans-serif">']

    def txt(x, y, value, size=14, color=None, weight=400, anchor="start"):
        out.append(f'<text x="{x}" y="{y}" font-size="{size}" fill="{color or p["ink"]}" font-weight="{weight}" text-anchor="{anchor}">{escape(str(value))}</text>')

    txt(28, 35, "WORK, IN NUMBERS", 12, p["muted"], 600)
    txt(872, 35, "@startificial", 12, p["muted"], anchor="end")
    txt(28, 79, f'{data["contributions_in_calendar"]:,}', 30, weight=600)
    txt(132, 79, "contributions in the past year", 14, p["muted"])
    txt(600, 79, data["public_repository_count"], 30, weight=600)
    txt(650, 79, "public repositories", 14, p["muted"])
    out.append(f'<path d="M28 103H872 M572 123V309" stroke="{p["line"]}"/>')
    txt(28, 137, "MONTHLY CONTRIBUTIONS", 11, p["muted"], 600)
    txt(600, 137, "PRIMARY REPOSITORY LANGUAGES", 11, p["muted"], 600)
    monthly = data["monthly_contributions"]
    maximum = max(1, *(v["count"] for v in monthly))
    for i, item in enumerate(monthly):
        x = 32 + i * 44
        height = item["count"] / maximum * 110
        color = p["accent"] if i == len(monthly) - 1 else p["bar"]
        out.append(f'<rect x="{x}" y="{276-height:.2f}" width="26" height="{max(height,1):.2f}" rx="3" fill="{color}"><title>{item["month"]}: {item["count"]} contributions</title></rect>')
        txt(x+13, 269-height, item["count"], 10, p["muted"], anchor="middle")
        label = calendar.month_abbr[int(item["month"][5:])]
        txt(x+13, 296, label, 10, p["muted"], anchor="middle")
    txt(28, 318, f'{monthly[0]["month"]} → {monthly[-1]["month"]} · current month is partial', 11, p["muted"])
    languages = list(data["primary_languages"].items())
    total = sum(count for _, count in languages)
    if len(languages) > 3:
        languages = languages[:2] + [("Other", sum(count for _, count in languages[2:]))]
    for i, (language, count) in enumerate(languages):
        y = 174 + i * 44
        txt(600, y, language, 14, weight=500)
        txt(872, y, f'{count} repos', 12, p["muted"], anchor="end")
        out.append(f'<rect x="600" y="{y+10}" width="272" height="7" rx="3.5" fill="{p["track"]}"/>')
        out.append(f'<rect x="600" y="{y+10}" width="{272 * count/max(total,1):.2f}" height="7" rx="3.5" fill="{p["bar"] if i == 0 else p["accent"]}"/>')
    txt(600, 290, "Public, non-fork repositories only.", 11, p["muted"])
    txt(600, 308, f'{data["without_detected_language"]} have no detected primary language.', 11, p["muted"])
    txt(28, 347, "Source: public GitHub profile & repository metadata", 10, p["muted"])
    txt(872, 347, f'Updated {data["updated"]}', 10, p["muted"], anchor="end")
    out.extend(["</g>", "</svg>"])
    return "\n".join(out) + "\n"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, help="Use saved public input data for verification")
    args = parser.parse_args()
    today = datetime.now(ZoneInfo("America/New_York")).date()
    if args.data_dir:
        repos = json.loads((args.data_dir / "repos.json").read_text())
        html = (args.data_dir / "contributions.html").read_text()
    else:
        repos = load_repos()
        html = fetch(f"https://github.com/users/{OWNER}/contributions")
    contributions = Contributions()
    contributions.feed(html)
    # Read counts only from the public page; never fetch private repository data.
    days = [d for d in contributions.days() if d["date"] <= today.isoformat()]
    owned = [r for r in repos if not r["fork"] and not r.get("private", False)]
    languages = Counter(r["language"] for r in owned if r["language"])
    monthly = []
    for offset in range(11, -1, -1):
        index = today.year * 12 + today.month - 1 - offset
        year, month = divmod(index, 12)
        key = f"{year}-{month+1:02d}"
        monthly.append({"month": key, "count": sum(d["count"] for d in days if d["date"].startswith(key))})
    data = {"updated": today.isoformat(), "sources": [f"https://github.com/users/{OWNER}/contributions", f"https://api.github.com/users/{OWNER}/repos"], "methodology": "Counts come from the public profile contribution calendar and include any private contribution counts the profile publicly displays. No private repository names or contents are requested. Monthly bars show the last 12 calendar months; the current month is partial. Languages count GitHub's primary language per public non-fork repository, not bytes, proficiency, or time spent.", "calendar_start": days[0]["date"], "calendar_end": days[-1]["date"], "contributions_in_calendar": sum(d["count"] for d in days), "monthly_contributions": monthly, "public_repository_count": sum(not r.get("private", False) for r in repos), "non_fork_repository_count": len(owned), "primary_languages": dict(languages.most_common()), "without_detected_language": sum(not r["language"] for r in owned)}
    charts = {f"activity-{theme}.svg": render(data, theme == "dark") for theme in ("light", "dark")}
    assets = ROOT / "assets"
    assets.mkdir(exist_ok=True)
    for name, svg in charts.items():
        (assets / name).write_text(svg)
    (assets / "activity-data.json").write_text(json.dumps(data, indent=2) + "\n")
    print(f'Updated charts: {data["contributions_in_calendar"]} contributions, {data["public_repository_count"]} public repos')


if __name__ == "__main__":
    main()
