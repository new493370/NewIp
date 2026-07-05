import re
import time
import requests
from random import SystemRandom

URLS = [
    "https://scansearch.net/en/resources/ip-ranges/ir/",
    "https://scanitex.com/en/resources/ip-ranges/ir",
    "https://www.cloudflare.com/ips",
]

for i in range(1, 11):
    URLS.append(
        f"https://ipv4.fetus.jp/ir?_lang=en-US&cidr-page=2&list-page={i}"
    )

CIDR_RE = re.compile(
    r"\b(?:25[0-5]|2[0-4]\d|1?\d?\d)"
    r"(?:\.(?:25[0-5]|2[0-4]\d|1?\d?\d)){3}"
    r"/(?:3[0-2]|[12]?\d)\b"
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/138.0 Safari/537.36"
    )
}

session = requests.Session()
session.headers.update(HEADERS)

cidrs = set()

for url in URLS:
    try:
        print(f"Fetching: {url}")
        response = session.get(url, timeout=30)
        response.raise_for_status()
        cidrs.update(CIDR_RE.findall(response.text))
    except Exception as e:
        print(f"Skip: {url} ({e})")

cidrs = sorted(cidrs)

SystemRandom().shuffle(cidrs)

with open("iran_ipv4.txt", "w", encoding="utf-8") as f:
    f.write(f"# Updated: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}\n")
    f.write("\n".join(cidrs))

print(f"Done. {len(cidrs)} IPv4 CIDRs saved.")
