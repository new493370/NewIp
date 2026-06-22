import json
import requests
import os
import time
from datetime import datetime, timedelta

OUTPUT_FILE = "output/ip_bank.txt"
HISTORY_FILE = "output/download_history.json"

def load_config():
    with open("config.json", "r", encoding="utf-8") as f:
        return json.load(f)

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
    all_ips = set()
    
    now = datetime.now()
    downloaded = False
    
    for url in cfg.get("sources", []):
        print(f"📥 {url}")
        new_ips = fetch_source(url)
        if new_ips:
            count_before = len(all_ips)
            all_ips.update(new_ips)
            count_after = len(all_ips)
            downloaded = True
            print(f"  ✅ {count_after - count_before} آیپی جدید (مجموع: {count_after})")
        else:
            print(f"  ⚠️  خطا یا خالی")
    
    if downloaded:
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            f.write("\n".join(sorted(all_ips)))
        print(f"\n💾 ذخیره شد: {len(all_ips)} آیپی")
    else:
        print(f"\nℹ️  بدون آیپی جدید")
    
    return downloaded

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
        print(f"\n⏳ انتظار {interval} ساعت تا چرخه بعدی...")
        time.sleep(interval * 3600)

if __name__ == "__main__":
    download_loop()
