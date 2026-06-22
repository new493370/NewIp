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

MAX_CIDR_EXPAND = 3000
LARGE_CIDR_SAMPLE = 3000

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

def sample_network(net, count):
    hosts = int(net.num_addresses)
    if hosts <= 2:
        return []
    usable = hosts - 2
    count = min(count, usable)
    picked = set()
    while len(picked) < count:
        idx = random.randint(1, usable)
        picked.add(str(net.network_address + idx))
    return picked

def write_ip(fh, ip, seen):
    ip = str(ip).strip()
    if not ip:
        return 0
    if ip in seen:
        return 0
    seen.add(ip)
    fh.write(ip + "\n")
    return 1

def process_line(line, fh, seen):
    line = line.strip()
    if not line:
        return 0
    try:
        if "/" in line:
            net = ipaddress.ip_network(line, strict=False)
            if net.num_addresses <= MAX_CIDR_EXPAND:
                count = 0
                for ip in net.hosts():
                    count += write_ip(fh, ip, seen)
                return count
            else:
                sampled = sample_network(net, LARGE_CIDR_SAMPLE)
                count = 0
                for ip in sampled:
                    count += write_ip(fh, ip, seen)
                return count
        else:
            ipaddress.ip_address(line)
            return write_ip(fh, line, seen)
    except:
        return 0

def clean_ips():
    ensure_output()
    
    history = load_history()
    seen = set()
    total = 0
    processed = 0
    changed = False
    
    if os.path.exists(OUTPUT_FILE) and os.path.getsize(OUTPUT_FILE) > 0:
        with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
            for line in f:
                ip = line.strip()
                if ip:
                    seen.add(ip)
        print(f"✅ LOADED {len(seen)} EXISTING CLEAN IPS")
        return len(seen)
    
    index = load_source_index()
    cfg = load_config()
    urls = cfg.get("sources", [])
    
    if not urls:
        print("❌ NO SOURCES FOUND")
        return 0
    
    current_index = index - 1
    if current_index < 0:
        current_index = len(urls) - 1
    
    ips = load_bank(current_index)
    
    if not ips:
        print(f"❌ NO IPS IN BANK {current_index + 1}")
        return 0
    
    print(f"📂 SOURCE {current_index + 1}: {len(ips)} آیپی")
    
    try:
        with open(TEMP_FILE, "w", encoding="utf-8") as dst:
            for ip in ips:
                processed += 1
                total += process_line(ip, dst, seen)
                if processed % 10000 == 0:
                    print(f"LINES={processed} IPS={total}")
    except:
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
