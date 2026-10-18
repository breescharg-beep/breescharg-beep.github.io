"""Refresh the DU sports feed from the structured data embedded in the official calendar."""
import json
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

URL = "https://denverpioneers.com/calendar"
DENVER = ZoneInfo("America/Denver")


class NuxtDataReader(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_data = False
        self.parts = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "script" and attrs.get("id") == "__NUXT_DATA__":
            self.in_data = True

    def handle_data(self, data):
        if self.in_data:
            self.parts.append(data)

    def handle_endtag(self, tag):
        if tag == "script":
            self.in_data = False


def extract_events(html):
    reader = NuxtDataReader()
    reader.feed(html)
    if not reader.parts:
        raise RuntimeError("DU calendar did not include its embedded schedule data")

    # Nuxt serializes its application state as an indexed JSON array.
    # References in objects point to other entries in this array.
    nodes = json.loads("".join(reader.parts))
    cache = {}

    def resolve(index):
        if not isinstance(index, int) or isinstance(index, bool):
            return index
        if index in cache:
            return cache[index]
        value = nodes[index]
        if isinstance(value, list):
            if value and isinstance(value[0], str) and value[0] in (
                "Reactive", "ShallowReactive", "Ref", "ShallowRef", "readonly", "shallowRef"
            ):
                result = resolve(value[1])
            else:
                result = [resolve(item) for item in value]
        elif isinstance(value, dict):
            result = {}
            cache[index] = result
            result.update({key: resolve(item) for key, item in value.items()})
        else:
            result = value
        cache[index] = result
        return result

    root = resolve(0)
    pinia = root.get("pinia", {})
    event_store = pinia.get("event", {})
    groups = event_store.get("events", {})
    events = []
    for group in groups.values():
        if isinstance(group, list):
            events.extend(group)
    return events


def main():
    request = Request(URL, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(request, timeout=30) as response:
        html = response.read().decode("utf-8", errors="replace")

    raw_events = extract_events(html)
    print(f"DU calendar returned {len(raw_events)} event records")

    today = datetime.now(DENVER).date()
    end = today + timedelta(days=14)
    games = []
    seen = set()

    for event in raw_events:
        if not isinstance(event, dict) or not event.get("start_date"):
            continue
        try:
            date = datetime.fromisoformat(event["start_date"].replace("Z", "+00:00")).date()
        except (ValueError, TypeError):
            continue
        if not today <= date < end:
            continue

        sport_info = event.get("sport") or {}
        opponent_info = event.get("opponent") or {}
        sport = sport_info.get("title") or sport_info.get("short_title") or "DU Athletics"
        opponent = opponent_info.get("title") or event.get("event_name") or "Event"
        indicator = event.get("location_indicator", "")
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

        matchup = f"{sport} {connector} {opponent}"
        time = event.get("time") or ("All Day" if event.get("is_all_day") else "TBD")
        identity = event.get("id") or (date.isoformat(), matchup)
        if identity in seen:
            continue
        seen.add(identity)
        games.append({
            "date": date.isoformat(),
            "sport": sport,
            "matchup": matchup,
            "time": time,
            "venue": venue,
        })

    if not games:
        raise RuntimeError("No upcoming DU events found. Existing feed left unchanged.")

    games.sort(key=lambda item: (item["date"], item["time"]))
    with open("du-sports.json", "w", encoding="utf-8") as file:
        json.dump({"updated": datetime.now(timezone.utc).isoformat(), "games": games}, file, indent=2)
    print(f"Saved {len(games)} upcoming DU events to du-sports.json")


if __name__ == "__main__":
    main()
