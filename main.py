import requests
import re
import random

URLS = [
    "https://scansearch.net/en/resources/ip-ranges/ir/",
    "https://scanitex.com/en/resources/ip-ranges/ir",
    "https://www.cloudflare.com/ips",
]

# صفحات fetus
for i in range(1, 10):
    URLS.append(
        f"https://ipv4.fetus.jp/ir?_lang=en-US&cidr-page=2&list-page={i}"
    )

CIDR_RE = re.compile(
    r"\b(?:25[0-5]|2[0-4]\d|1?\d?\d)"
    r"(?:\.(?:25[0-5]|2[0-4]\d|1?\d?\d)){3}"
    r"/(?:3[0-2]|[12]?\d)\b"
)

cidrs = set()

headers = {
    "User-Agent": "Mozilla/5.0"
}

for url in URLS:
    try:
        print("Fetching:", url)
        text = requests.get(url, headers=headers, timeout=30).text
        cidrs.update(CIDR_RE.findall(text))
    except Exception as e:
        print("Skip:", e)

cidrs = list(cidrs)
random.shuffle(cidrs)

with open("iran_ipv4.txt", "w") as f:
    f.write("\n".join(cidrs))

print(f"Done. {len(cidrs)} IPv4 CIDRs saved.")
