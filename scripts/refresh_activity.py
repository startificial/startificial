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


def render(data):
    import math
    p = {'bg':'#090909','panel':'#111110','ink':'#dededb','muted':'#8b8b87','line':'#2b2b29','green':'#19c55a'}
    out = ['<svg xmlns="http://www.w3.org/2000/svg" width="900" height="622" viewBox="0 0 900 622" role="img" aria-labelledby="title desc">', '<title id="title">JJ — work overview</title>', '<desc id="desc">A work graph with JJ, high-level StackAI themes, and four public projects, styled with dark panels, monospace labels, and green accents. Each segment in the activity orbit represents one week of publicly displayed GitHub contributions; brighter, thicker segments mean more activity. Connections represent shared interests.</desc>', f'<rect x=".5" y=".5" width="899" height="621" fill="{p["bg"]}" stroke="{p["line"]}"/>', '<g font-family="-apple-system, BlinkMacSystemFont, Segoe UI, Arial, sans-serif">']

    def text(x,y,value,size=14,color=None,weight=400,anchor='start',mono=False,spacing=None):
        extra = ' font-family="ui-monospace, SFMono-Regular, Menlo, Consolas, monospace"' if mono else ''
        if spacing is not None:
            extra += f' letter-spacing="{spacing}"'
        out.append(f'<text x="{x}" y="{y}" font-size="{size}" fill="{color or p["ink"]}" font-weight="{weight}" text-anchor="{anchor}"{extra}>{escape(str(value))}</text>')

    def box(x,y,w,h,fill=None,stroke=None,extra=''):
        out.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{fill or p["panel"]}" stroke="{stroke or p["line"]}" {extra}/>')

    def line(d,color=None,width=1,extra=''):
        out.append(f'<path d="{d}" fill="none" stroke="{color or p["line"]}" stroke-width="{width}" {extra}/>')

    def dot(x,y,r=2.5,color=None):
        out.append(f'<circle cx="{x}" cy="{y}" r="{r}" fill="{color or p["green"]}"/>')

    def digital(x,y,value,height=28,color=None):
        # A vector seven-segment face keeps the counters crisp without remote fonts.
        shapes = {'a':[(3,0),(15,0),(18,3),(15,5),(3,5),(0,3)], 'g':[(3,17),(15,17),(18,20),(15,22),(3,22),(0,20)], 'd':[(3,35),(15,35),(18,38),(15,40),(3,40),(0,38)], 'f':[(0,4),(5,7),(5,15),(0,18)], 'b':[(13,7),(18,4),(18,18),(13,15)], 'e':[(0,22),(5,25),(5,33),(0,36)], 'c':[(13,25),(18,22),(18,36),(13,33)]}
        digits = {'0':'abcdef','1':'bc','2':'abged','3':'abgcd','4':'fgbc','5':'afgcd','6':'afgecd','7':'abc','8':'abcdefg','9':'abfgcd'}
        scale=height/40
        out.append(f'<g transform="translate({x} {y}) scale({scale})" fill="{color or p["ink"]}">')
        for i,char in enumerate(str(value)):
            for segment in digits[char]:
                points=' '.join(f'{px+i*25},{py}' for px,py in shapes[segment])
                out.append(f'<polygon points="{points}"/>')
        out.append('</g>')

    # Top bar follows the reference's plain, square-edged application chrome.
    box(0.5,0.5,899,49,p['bg'])
    box(18,13,24,24,'#222221','#30302e')
    text(30,29,'JJ',9,anchor='middle',mono=True)
    text(54,25,'JJ',13,weight=550)
    text(54,40,'startificial',10,p['muted'],mono=True)
    line('M168 15V35')
    line('M188 18H201V31H188Z M192 18V31',p['muted'],1.2)
    text(211,30,'Work overview',13)
    dot(757,26,3)
    text(770,30,'PUBLIC PROFILE',10,p['green'],mono=True)
    text(20,84,'Work overview',24,weight=600)
    text(880,81,f'UPDATED {data["updated"]}',10,p['muted'],anchor='end',mono=True)

    cards=[(20,'PUBLIC REPOSITORIES',data['public_repository_count'],'Projects and experiments on GitHub'),(313,'FEATURED PROJECTS',4,'Voice · memory · automation · agents'),(606,'PRIMARY LANGUAGES',len(data['primary_languages']),' / '.join(data['primary_languages']))]
    for x,label,value,caption in cards:
        box(x,105,274,88)
        text(x+16,127,label,10,p['muted'],mono=True,spacing='.8')
        digital(x+16,139,f'{value:02d}',27,p['green'] if label=='FEATURED PROJECTS' else p['ink'])
        text(x+16,181,caption,10,p['muted'],mono=True)
        # Small reference-style corner marks are decorative, not state indicators.
        line(f'M{x+251} 119h7v7h-7Z',p['green'] if label=='FEATURED PROJECTS' else p['muted'],.9)

    box(20,213,552,360)
    box(590,213,290,360)
    text(38,240,'Work graph',16,weight=500)
    text(554,239,'SHARED INTERESTS',9,p['muted'],anchor='end',mono=True)
    line('M20 255H572 M590 255H880')
    text(608,240,'Activity orbit',16,weight=500)
    dot(856,235,3)

    # Orthogonal connectors organize themes, not implementation dependencies.
    line('M193 384H232V307H278',p['green'],1.1,extra='opacity=".75"')
    line('M232 384V397H278',p['green'],1.1,extra='opacity=".75"')
    line('M232 397V487H278',p['green'],1.1,extra='opacity=".75"')
    line('M232 351H480V367',p['green'],1.1,extra='opacity=".45"')
    line('M232 441H480V457',p['green'],1.1,extra='opacity=".45"')
    for x,y in [(232,384),(232,351),(232,441)]:
        dot(x,y,2)

    box(42,348,151,73,'#151513','#474744')
    box(54,361,28,28,'#242423','#393937')
    text(68,380,'JJ',11,weight=600,anchor='middle',mono=True)
    text(94,378,'JJ',18,weight=600)
    text(54,407,'@startificial',11,p['muted'],mono=True)
    text(42,441,'BUILDER / EXPLORER',9,p['muted'],mono=True)

    box(278,279,276,56)
    line('M293 295h11v11h-11Z M298 291V295 M298 306V310',p['muted'],1.1)
    text(314,300,'STACKAI',10,p['muted'],mono=True)
    text(294,320,'Product · platform · reliability',13)
    box(490,289,52,18,'#0c1b11','#184e2b',extra='rx="9"')
    text(516,302,'FOCUS',9,p['green'],anchor='middle',mono=True)
    dot(278,307,2)

    projects=[(278,367,124,'VOICE','Open Voice','TS'),(414,367,140,'MEMORY','Volatile Memory','PY'),(278,457,124,'AUTOMATION','House Search','PY'),(414,457,140,'AGENTS','Weather Agent','TS')]
    for x,y,w,theme,name,language in projects:
        box(x,y,w,60)
        text(x+12,y+19,theme,9,p['muted'],mono=True)
        text(x+12,y+43,name,12.5,weight=500)
        text(x+w-10,y+19,language,9,p['green'],anchor='end',mono=True)
    for x,y in [(278,397),(278,487),(480,367),(480,457)]:
        dot(x,y,2)
    text(38,552,'AI products / agent systems / practical tools',10,p['muted'],mono=True)

    cx,cy=735,369
    weeks=data['weekly_contributions']
    maximum=max(1,*(w['count'] for w in weeks))
    for radius in [77,101]:
        out.append(f'<circle cx="{cx}" cy="{cy}" r="{radius}" fill="none" stroke="{p["line"]}" stroke-width=".8"/>')
    for i,week in enumerate(weeks):
        a=-math.pi/2+(i+.12)*math.tau/len(weeks)
        b=-math.pi/2+(i+.80)*math.tau/len(weeks)
        activity=math.sqrt(week['count']/maximum)
        radius=89
        x1,y1=cx+radius*math.cos(a),cy+radius*math.sin(a)
        x2,y2=cx+radius*math.cos(b),cy+radius*math.sin(b)
        color=p['green'] if week['count'] else '#30302d'
        opacity=.25+.75*activity if week['count'] else 1
        out.append(f'<path d="M{x1:.2f} {y1:.2f}A89 89 0 0 1{x2:.2f} {y2:.2f}" fill="none" stroke="{color}" stroke-width="{2+activity*4:.2f}" opacity="{opacity:.2f}"><title>Week of {week["start"]}: {week["count"]} contributions</title></path>')
    for angle in [0,math.pi/2,math.pi,3*math.pi/2]:
        x1,y1=cx+107*math.cos(angle),cy+107*math.sin(angle)
        x2,y2=cx+112*math.cos(angle),cy+112*math.sin(angle)
        line(f'M{x1:.2f} {y1:.2f}L{x2:.2f} {y2:.2f}',p['muted'])
    value=str(data['contributions_in_calendar'])
    digital(cx-(len(value)*25-7)*.85/2,346,value,34)
    text(cx,402,'CONTRIBUTIONS',9,p['muted'],anchor='middle',mono=True,spacing='.8')
    line('M608 487H862')
    text(608,511,'WINDOW',9,p['muted'],mono=True)
    text(862,511,'PAST YEAR',10,anchor='end',mono=True)
    text(608,536,'SIGNALS',9,p['muted'],mono=True)
    text(862,536,f'{len(weeks)} WEEKS',10,anchor='end',mono=True)
    text(608,556,'SOURCE',9,p['muted'],mono=True)
    text(862,556,'PUBLIC GITHUB PROFILE',9,anchor='end',mono=True)

    line('M20 590H880')
    dot(25,606,2)
    text(35,610,'Brighter orbit segments = more contributions that week.',10,p['muted'],mono=True)
    text(880,610,'JJ / STARTIFICIAL',10,p['muted'],anchor='end',mono=True)
    out.extend(['</g>','</svg>'])
    return '\n'.join(out)+'\n'


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
    data = {"updated": today.isoformat(), "sources": [f"https://github.com/users/{OWNER}/contributions", f"https://api.github.com/users/{OWNER}/repos"], "methodology": "Counts come from the public profile contribution calendar and include any private contribution counts the profile publicly displays. No private repository names or contents are requested. Monthly totals in this data cover the last 12 calendar months; the current month is partial. Languages count GitHub's primary language per public non-fork repository, not bytes, proficiency, or time spent.", "calendar_start": days[0]["date"], "calendar_end": days[-1]["date"], "contributions_in_calendar": sum(d["count"] for d in days), "monthly_contributions": monthly, "public_repository_count": sum(not r.get("private", False) for r in repos), "non_fork_repository_count": len(owned), "primary_languages": dict(languages.most_common()), "without_detected_language": sum(not r["language"] for r in owned)}
    from datetime import date, timedelta
    weekly = {}
    for day in days:
        dt = date.fromisoformat(day["date"])
        sunday = dt - timedelta(days=(dt.weekday() + 1) % 7)
        key = sunday.isoformat()
        weekly[key] = weekly.get(key, 0) + day["count"]
    data["weekly_contributions"] = [{"start": key, "count": value} for key, value in sorted(weekly.items())]
    data["methodology"] += " The work graph links indicate shared interests, not implementation dependencies. Its activity orbit uses one segment per calendar week; segment brightness and thickness increase with the square root of that week's contribution count relative to the maximum week."
    charts = {"work-console.svg": render(data)}
    assets = ROOT / "assets"
    assets.mkdir(exist_ok=True)
    for name, svg in charts.items():
        (assets / name).write_text(svg)
    (assets / "activity-data.json").write_text(json.dumps(data, indent=2) + "\n")
    print(f'Updated charts: {data["contributions_in_calendar"]} contributions, {data["public_repository_count"]} public repos')


if __name__ == "__main__":
    main()
