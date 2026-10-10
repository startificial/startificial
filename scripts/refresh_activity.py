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
    import math
    import random
    p = {"bg": "#101421", "ink": "#f0eee9", "muted": "#9fa9b9", "line": "#374257", "mint": "#8ee4c5", "violet": "#b2a2ff", "gold": "#f1c587", "blue": "#91c9f4", "soft": "#192334"} if dark else {"bg": "#faf8f3", "ink": "#253042", "muted": "#697384", "line": "#cbd0d8", "mint": "#247d69", "violet": "#7162b6", "gold": "#a87225", "blue": "#377dba", "soft": "#eeeae1"}
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="900" height="535" viewBox="0 0 900 535" role="img" aria-labelledby="title desc">', '<title id="title">JJ — a work constellation</title>', '<desc id="desc">A personal work map linking JJ to high-level StackAI work and four public projects. The orbit has one segment for each week of publicly visible GitHub activity; brighter, thicker segments indicate more contributions. Project connections are thematic, not dependencies.</desc>', f'<rect x=".5" y=".5" width="899" height="534" rx="16" fill="{p["bg"]}" stroke="{p["line"]}"/>', '<style>.pulse{animation:breathe 5s ease-in-out infinite}@keyframes breathe{0%,100%{opacity:.25}50%{opacity:.7}}@media(prefers-reduced-motion:reduce){.pulse{animation:none}}</style>', '<g font-family="-apple-system, BlinkMacSystemFont, Segoe UI, sans-serif">']

    def txt(x, y, value, size=14, color=None, weight=400, anchor="start", mono=False):
        font = ' font-family="ui-monospace, SFMono-Regular, Consolas, monospace"' if mono else ''
        out.append(f'<text x="{x}" y="{y}" font-size="{size}" fill="{color or p["ink"]}" font-weight="{weight}" text-anchor="{anchor}"{font}>{escape(str(value))}</text>')

    def path(d, color=None, width=1, extra=''):
        out.append(f'<path d="{d}" fill="none" stroke="{color or p["line"]}" stroke-width="{width}" {extra}/>')

    def circle(x, y, r, fill, stroke=None, extra=''):
        out.append(f'<circle cx="{x}" cy="{y}" r="{r}" fill="{fill}" stroke="{stroke or fill}" {extra}/>')

    # Quiet background stars are decorative; only the labelled orbit encodes data.
    rng = random.Random(17)
    for _ in range(55):
        x, y = rng.randrange(35, 866), rng.randrange(118, 472)
        circle(x, y, rng.choice([.7, 1, 1.2]), p['muted'], extra='opacity=".17"')
    txt(35, 37, 'JJ / STARTIFICIAL', 11, p['muted'], mono=True)
    txt(35, 77, 'A map of what I build.', 29, weight=550)
    txt(35, 103, 'Agents, data, and the systems behind them.', 14, p['muted'])
    txt(865, 37, 'WORK CONSTELLATION / 01', 10, p['muted'], anchor='end', mono=True)

    cx, cy = 430, 300
    circle(cx, cy, 156, 'none', p['line'], 'stroke-dasharray="2 9" opacity=".5"')
    circle(cx, cy, 130, 'none', p['line'], 'stroke-width=".6" opacity=".5"')
    path('M324 247 Q290 232 255 200', p['violet'], 1.2)
    path('M532 246 Q600 210 659 194', p['mint'], 1.2)
    path('M540 345 Q597 370 659 382', p['blue'], 1.2)
    path('M330 358 Q271 398 204 407', p['gold'], 1.2)
    path('M451 413 Q464 440 492 458', p['mint'], 1.2)
    # Secondary bridges describe shared interests, never internal architecture.
    path('M255 200 Q358 139 659 194', extra='stroke-dasharray="3 6" opacity=".45"')
    path('M659 194 Q702 277 659 382', extra='stroke-dasharray="3 6" opacity=".45"')
    path('M204 407 Q296 469 492 458', extra='stroke-dasharray="3 6" opacity=".45"')

    weeks = data['weekly_contributions']
    maximum = max(1, *(w['count'] for w in weeks))
    for i, week in enumerate(weeks):
        a = -math.pi/2 + (i + .09) * math.tau/len(weeks)
        b = -math.pi/2 + (i + .83) * math.tau/len(weeks)
        activity = math.sqrt(week['count']/maximum)
        radius = 106 + activity*10
        x1,y1 = cx+radius*math.cos(a),cy+radius*math.sin(a)
        x2,y2 = cx+radius*math.cos(b),cy+radius*math.sin(b)
        color = p['mint'] if i >= len(weeks)*.73 else p['violet']
        opacity = .2 + .8*activity
        d = f'M{x1:.2f} {y1:.2f} A{radius:.2f} {radius:.2f} 0 0 1 {x2:.2f} {y2:.2f}'
        out.append(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{2+activity*5:.2f}" opacity="{opacity:.2f}" stroke-linecap="round"><title>Week of {week["start"]}: {week["count"]} contributions</title></path>')
    circle(cx,cy,78,p['soft'])
    txt(cx, cy-7, 'JJ', 47, weight=550, anchor='middle')
    txt(cx, cy+24, 'BUILDER / EXPLORER', 9, p['muted'], anchor='middle', mono=True)
    txt(cx, cy+49, f'{data["contributions_in_calendar"]:,} contributions', 12, p['mint'], anchor='middle')
    txt(cx, 163, 'PUBLIC ACTIVITY ORBIT', 9, p['muted'], anchor='middle', mono=True)

    # Nodes are entirely custom vector marks, not fetched icons or third-party cards.
    def node(x,y,color):
        circle(x,y,23,'none',color,'opacity=".2" class="pulse"')
        circle(x,y,16,p['bg'],color,'stroke-width="1.2"')
        circle(x,y,2.5,color)

    node(255,200,p['violet'])
    path('M248 194L262 194L262 206L248 206Z M255 188V194 M255 206V212',p['violet'],1.2)
    txt(45,173,'STACKAI',10,p['violet'],mono=True)
    txt(45,197,'AI workflow products',18,weight=550)
    txt(45,221,'Product · platform · reliability',11,p['muted'])

    node(659,194,p['mint'])
    path('M647 194H651L654 187L658 201L662 187L665 194H671',p['mint'],1.3)
    txt(698,171,'VOICE',10,p['mint'],mono=True)
    txt(698,195,'Open Voice',19,weight=550)
    txt(698,218,'Voice agent interfaces',12,p['muted'])

    node(659,382,p['blue'])
    for x,y in [(651,376),(666,374),(665,390)]:
        circle(x,y,2,p['blue'])
    path('M651 376L666 374L665 390L651 376',p['blue'],1)
    txt(698,361,'MEMORY',10,p['blue'],mono=True)
    txt(698,385,'Volatile Memory',18,weight=550)
    txt(698,408,'How agents remember',12,p['muted'])

    node(204,407,p['gold'])
    path('M195 407L204 399L213 407 M198 406V415H210V406',p['gold'],1.2)
    txt(45,382,'AUTOMATION',10,p['gold'],mono=True)
    txt(45,406,'House Search',18,weight=550)
    txt(45,430,'Data → useful action',12,p['muted'])

    node(492,458,p['mint'])
    path('M481 461H503 M484 456Q484 448 491 451Q499 445 502 455',p['mint'],1.2)
    txt(533,445,'AGENTS + TOOLS',10,p['mint'],mono=True)
    txt(533,469,'Weather Agent',18,weight=550)
    txt(533,489,'Small workflows, real utility',12,p['muted'])

    path('M35 505H865',width=.6)
    txt(35,524,'Orbit: one week per segment · brighter = more contributions',10,p['muted'])
    txt(865,524,f'PUBLIC DATA / {data["updated"]}',9,p['muted'],anchor='end',mono=True)
    out.extend(['</g>', '</svg>'])
    return '\n'.join(out) + '\n'

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
    from datetime import date, timedelta
    weekly = {}
    for day in days:
        dt = date.fromisoformat(day["date"])
        sunday = dt - timedelta(days=(dt.weekday() + 1) % 7)
        key = sunday.isoformat()
        weekly[key] = weekly.get(key, 0) + day["count"]
    data["weekly_contributions"] = [{"start": key, "count": value} for key, value in sorted(weekly.items())]
    data["methodology"] += " The work constellation links are thematic, not dependencies. Its activity orbit uses one segment per calendar week; segment brightness and thickness increase with the square root of that week's contribution count relative to the maximum week."
    charts = {f"activity-{theme}.svg": render(data, theme == "dark") for theme in ("light", "dark")}
    assets = ROOT / "assets"
    assets.mkdir(exist_ok=True)
    for name, svg in charts.items():
        (assets / name).write_text(svg)
    (assets / "activity-data.json").write_text(json.dumps(data, indent=2) + "\n")
    print(f'Updated charts: {data["contributions_in_calendar"]} contributions, {data["public_repository_count"]} public repos')


if __name__ == "__main__":
    main()
