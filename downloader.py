import json
import requests
import os
import time
from datetime import datetime

OUTPUT_FILE = "output/ip_bank.txt"
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
    
    index = load_source_index()
    
    if index >= len(urls):
        index = 0
        save_source_index(index)
    
    url = urls[index]
    print(f"📥 [{index + 1}/{len(urls)}] {url}")
    
    new_ips = fetch_source(url)
    
    if new_ips:
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            f.write("\n".join(sorted(new_ips)))
        print(f"  ✅ {len(new_ips)} آیپی دانلود شد")
        
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
    
    print("🔄 چرخه دانلود فعال شد")
    
    while True:
        print("\n" + "="*50)
        print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("🔄 شروع چرخه جدید دانلود")
        print("="*50)
        
        download_sources()
        
        interval = cfg.get("download_interval_hours", 24)
        if interval > 0:
            print(f"\n⏳ انتظار {interval} ساعت تا چرخه بعدی...")
            time.sleep(interval * 3600)
        else:
            print("\n⏳ انتظار 1 ساعت تا چرخه بعدی...")
            time.sleep(3600)

if __name__ == "__main__":
    download_loop()
