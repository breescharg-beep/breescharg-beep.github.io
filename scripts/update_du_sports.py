"""Update the DU sports schedule using the official calendar API."""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

DENVER = ZoneInfo("America/Denver")
BASE = "https://denverpioneers.com/api/v2/Calendar/from/{start}/to/{end}"


def main():
    today = datetime.now(DENVER).date()
    end = today + timedelta(days=14)

    start_date = today - timedelta(days=1)
    end_date = today + timedelta(days=15)

    def format_date(date):
        return f"{date.month}-{date.day}-{date.year}"

    url = BASE.format(
        start=format_date(start_date),
        end=format_date(end_date),
    )

    print("Fetching DU Athletics calendar:", url)

    request = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json",
        },
    )

    with urlopen(request, timeout=30) as response:
        calendar = json.load(response)

    if not isinstance(calendar, list):
        raise RuntimeError("Unexpected calendar response")

    games = []
    seen = set()

    for day in calendar:
        for event in day.get("events", []):
            date_text = str(
                event.get("date") or day.get("date") or ""
            )[:10]

            try:
                date = datetime.strptime(
                    date_text, "%Y-%m-%d"
                ).date()
            except ValueError:
                continue

            if not today <= date < end:
                continue

            sport_info = event.get("sport") or {}
            opponent_info = event.get("opponent") or {}

            sport = sport_info.get("title") or "DU Athletics"
            opponent = (
                opponent_info.get("title")
                or event.get("eventName")
                or "Event"
            )

            indicator = event.get("locationIndicator", "")
            at_vs = event.get("atVs", "")

            if indicator == "H" or at_vs == "vs":
                venue = "Home"
                connector = "vs"
            elif indicator == "A" or at_vs == "at":
                venue = "Away"
                connector = "at"
            else:
                venue = "Neutral / See calendar"
                connector = "vs"

            time = event.get("time") or (
                "All Day" if event.get("allDay") else "TBD"
            )

            identity = event.get("id") or (
                date_text, sport, opponent, time
            )

            if identity in seen:
                continue

            seen.add(identity)

            games.append({
                "date": date_text,
                "sport": sport,
                "matchup": f"{sport} {connector} {opponent}",
                "time": time,
                "venue": venue,
            })

    games.sort(
        key=lambda game: (
            game["date"],
            game["time"],
            game["sport"],
        )
    )

    print(f"Found {len(games)} upcoming DU events")

    if not games:
        raise RuntimeError(
            "No upcoming DU events found; existing feed unchanged"
        )

    output = {
        "updated": datetime.now(timezone.utc).isoformat(),
        "games": games,
    }

    Path("du-sports.json").write_text(
        json.dumps(output, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print(f"Saved {len(games)} upcoming DU events")


if __name__ == "__main__":
    main()
