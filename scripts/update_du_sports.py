import json
import re
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

DENVER = ZoneInfo("America/Denver")
today = datetime.now(DENVER).date()
end = today + timedelta(days=14)

url = (
    "https://denverpioneers.com/calendar/print/month/0/"
    f"{(today - timedelta(days=1)).strftime('%m-%d-%Y')}/"
    f"{end.strftime('%m-%d-%Y')}/null"
)

class CalendarParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tag = None
        self.text = []
        self.blocks = []

    def handle_starttag(self, tag, attrs):
        if tag in ("h2", "h3", "h4", "h5", "p", "li"):
            self.tag = tag
            self.text = []

    def handle_data(self, data):
        if self.tag:
            self.text.append(data)

    def handle_endtag(self, tag):
        if tag == self.tag:
            value = " ".join(" ".join(self.text).split())
            if value:
                self.blocks.append((tag, value))
            self.tag = None

request = Request(url, headers={
    "User-Agent": "Mozilla/5.0 (compatible; LevelUpPlanner/1.0)"
})

with urlopen(request, timeout=30) as response:
    html = response.read().decode("utf-8", errors="replace")

parser = CalendarParser()
parser.feed(html)

games = []
current_date = None

for tag, value in parser.blocks:
    date_match = re.fullmatch(
        r"(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday), "
        r"([A-Za-z]+ \d{1,2}, \d{4})",
        value
    )
    if date_match:
        current_date = datetime.strptime(
            date_match.group(2), "%B %d, %Y"
        ).date()
        continue

    if tag != "h5" or current_date is None:
        continue

    if not (today <= current_date < end):
        continue

    matchup = re.split(
        r"\s+(?:All Day|TBD|\d{1,2}:\d{2}\s*[ap]\.m\.|\d{1,2}\s*[ap]\.m\.)",
        value,
        maxsplit=1,
        flags=re.IGNORECASE
    )[0].strip()

    if not matchup:
        continue

    match = re.search(r"\s(vs|at)\s", matchup)
    if match:
        sport = matchup[:match.start()].strip()
        opponent = matchup[match.end():].strip()
        location = "Home" if match.group(1) == "vs" else "Away"
    else:
        sport = matchup
        opponent = ""
        location = "See official calendar"

    time_match = re.search(
        r"(All Day|TBD|\d{1,2}(?::\d{2})?\s*[ap]\.m\.\s*MT)",
        value,
        flags=re.IGNORECASE
    )

    games.append({
        "date": current_date.isoformat(),
        "sport": sport,
        "matchup": matchup,
        "time": time_match.group(1) if time_match else "",
        "venue": location
    })

if not games:
    raise RuntimeError(
        "No events were parsed. Check whether DU changed its calendar format."
    )

games.sort(key=lambda game: (game["date"], game["time"]))

with open("du-sports.json", "w", encoding="utf-8") as file:
    json.dump({
        "updated": datetime.now(timezone.utc).isoformat(),
        "games": games
    }, file, indent=2)

print(f"Saved {len(games)} DU events.")
