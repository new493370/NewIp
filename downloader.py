import json
import requests

OUTPUT_FILE = "output/ip_bank.txt"

def load_config():
    with open("config.json", "r", encoding="utf-8") as f:
        return json.load(f)

def fetch_source(url):
    try:
        r = requests.get(url, timeout=30)
        if r.ok:
            return r.text.splitlines()
    except:
        pass
    return []

def download_sources():
    cfg = load_config()
    all_ips = []
    for url in cfg.get("sources", []):
        all_ips.extend(fetch_source(url))
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(all_ips))

if __name__ == "__main__":
    download_sources()
