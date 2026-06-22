import json
import requests
import os
import time
from datetime import datetime

BANK_DIR = "output/banks"
SOURCE_INDEX_FILE = "output/source_index.txt"

def load_config():
    with open("config.json", "r", encoding="utf-8") as f:
        return json.load(f)

def load_source_index():
    if os.path.exists(SOURCE_INDEX_FILE):
        try:
            with open(SOURCE_INDEX_FILE, "r", encoding="utf-8") as f:
                return int(f.read().strip())
        except:
            return 0
    return 0

def save_source_index(index):
    with open(SOURCE_INDEX_FILE, "w", encoding="utf-8") as f:
        f.write(str(index))

def ensure_bank_dir():
    os.makedirs(BANK_DIR, exist_ok=True)

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

def save_bank(index, ips):
    ensure_bank_dir()
    path = get_bank_path(index)
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(sorted(ips)))

def clear_bank(index):
    path = get_bank_path(index)
    if os.path.exists(path):
        os.remove(path)

def clear_all_banks():
    if not os.path.exists(BANK_DIR):
        return
    for filename in os.listdir(BANK_DIR):
        if filename.startswith("source_") and filename.endswith(".txt"):
            path = os.path.join(BANK_DIR, filename)
            os.remove(path)
    print("🗑️  ALL BANKS CLEARED - NEW CYCLE STARTED")

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
    urls = cfg.get("sources", [])
    
    if not urls:
        print("❌ NO SOURCES FOUND")
        return False
    
    ensure_bank_dir()
    
    index = load_source_index()
    
    if index >= len(urls):
        index = 0
        save_source_index(index)
        clear_all_banks()
    
    url = urls[index]
    print(f"📥 [{index + 1}/{len(urls)}] {url}")
    
    existing_ips = load_bank(index)
    
    if existing_ips:
        print(f"  ✅ {len(existing_ips)} آیپی از بانک موجود استفاده شد")
        next_index = index + 1
        if next_index >= len(urls):
            next_index = 0
        save_source_index(next_index)
        print(f"  📌 NEXT SOURCE: {next_index + 1}/{len(urls)}")
        return True
    
    new_ips = fetch_source(url)
    
    if new_ips:
        save_bank(index, new_ips)
        print(f"  ✅ {len(new_ips)} آیپی دانلود و ذخیره شد")
        next_index = index + 1
        if next_index >= len(urls):
            next_index = 0
        save_source_index(next_index)
        print(f"  📌 NEXT SOURCE: {next_index + 1}/{len(urls)}")
        return True
    else:
        print(f"  ⚠️  خطا یا خالی")
        next_index = index + 1
        if next_index >= len(urls):
            next_index = 0
        save_source_index(next_index)
        return False

def download_loop():
    cfg = load_config()
    loop_enabled = cfg.get("loop_download", False)
    
    if not loop_enabled:
        download_sources()
        return
    
    print("🔄 چرخه دانلود فعال شد (یک بار اجرا در هر مرحله)")
    download_sources()

if __name__ == "__main__":
    download_loop()
