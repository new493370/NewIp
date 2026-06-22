import ipaddress
import json
import os
import random
from datetime import datetime

BANK_DIR = "output/banks"
OUTPUT_FILE = "output/clean_ips.txt"
TEMP_FILE = "output/clean_ips.tmp"
HISTORY_FILE = "output/clean_history.json"
SOURCE_INDEX_FILE = "output/source_index.txt"

MAX_CIDR_EXPAND = 0
LARGE_CIDR_SAMPLE = 0


def load_config():
    try:
        with open("config.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}


def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}
    return {}


def save_history(history):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2)


def ensure_output():
    os.makedirs("output", exist_ok=True)
    os.makedirs(BANK_DIR, exist_ok=True)


def load_source_index():
    if os.path.exists(SOURCE_INDEX_FILE):
        try:
            with open(SOURCE_INDEX_FILE, "r", encoding="utf-8") as f:
                return int(f.read().strip())
        except:
            return 0
    return 0


def get_bank_path(index):
    return os.path.join(BANK_DIR, f"source_{index}.txt")


def load_bank(index):
    path = get_bank_path(index)
    if os.path.exists(path) and os.path.getsize(path) > 0:
        try:
            with open(path, "r", encoding="utf-8") as f:
                return [line.strip() for line in f if line.strip()]
        except:
            return []
    return []


def load_all_banks():
    all_ips = []
    cfg = load_config()
    urls = cfg.get("sources", [])
    
    for i in range(len(urls)):
        ips = load_bank(i)
        if ips:
            all_ips.extend(ips)
    
    return all_ips


def write_ip(fh, ip, seen, count):
    ip = str(ip).strip()
    if not ip:
        return count
    if ip in seen:
        return count
    seen.add(ip)
    fh.write(ip + "\n")
    count += 1
    if count % 100000 == 0:
        print(f"  PROCESSED {count} IPS")
    return count


def process_line(line, fh, seen, count):
    line = line.strip()
    if not line:
        return count
    try:
        if "/" in line:
            net = ipaddress.ip_network(line, strict=False)
            for ip in net.hosts():
                count = write_ip(fh, ip, seen, count)
            return count
        else:
            ipaddress.ip_address(line)
            return write_ip(fh, line, seen, count)
    except:
        return count


def clean_ips():
    ensure_output()
    
    history = load_history()
    seen = set()
    total = 0
    processed = 0
    changed = False
    
    if os.path.exists(OUTPUT_FILE):
        os.remove(OUTPUT_FILE)
    
    all_ips = load_all_banks()
    
    if not all_ips:
        print("❌ NO IPS FOUND IN ANY BANK")
        return 0
    
    print(f"📂 TOTAL IPS FROM ALL BANKS: {len(all_ips)}")
    
    try:
        with open(TEMP_FILE, "w", encoding="utf-8") as dst:
            count = 0
            for ip in all_ips:
                processed += 1
                count = process_line(ip, dst, seen, count)
                if processed % 1000 == 0:
                    print(f"LINES={processed} IPS={count}")
            total = count
    except Exception as e:
        print(f"ERROR: {e}")
        return 0
    
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        for ip in sorted(seen):
            f.write(ip + "\n")
    
    if os.path.exists(TEMP_FILE):
        os.remove(TEMP_FILE)
    
    current_time = datetime.now().isoformat()
    
    if "last_clean" not in history or history.get("total_ips", 0) != total:
        history["last_clean"] = current_time
        history["total_ips"] = total
        history["processed_lines"] = processed
        changed = True
    
    save_history(history)
    
    print(f"CLEAN IPS={total}")
    return total


if __name__ == "__main__":
    clean_ips()
