from urllib.request import Request, urlopen
from html.parser import HTMLParser

url = "https://denverpioneers.com/calendar"

class TextReader(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, data):
        value = " ".join(data.split())
        if value:
            self.parts.append(value)

request = Request(url, headers={
    "User-Agent": "Mozilla/5.0"
})

with urlopen(request, timeout=30) as response:
    html = response.read().decode("utf-8", errors="replace")
    print("HTTP status:", response.status)

reader = TextReader()
reader.feed(html)

print("HTML characters:", len(html))
print("Calendar text:")
print("\n".join(reader.parts[-100:]))
