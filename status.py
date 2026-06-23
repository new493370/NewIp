import os
from cursor import load_cursor

INPUT_FILE = "output/clean_ips.txt"

def read_count(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return sum(1 for line in f if line.strip())
    except:
        return 0

def total_ips():
    return read_count(INPUT_FILE)

def current_cursor():
    return load_cursor()

def scan_completed():
    total = total_ips()
    if total == 0:
        return False
    cursor = current_cursor()
    return cursor >= total

def progress():
    total = total_ips()
    cursor = current_cursor()
    if total <= 0:
        return {"total": 0, "cursor": cursor, "percent": 0}
    percent = round((cursor / total) * 100, 2)
    if percent > 100:
        percent = 100
    return {"total": total, "cursor": cursor, "percent": percent}

def print_status():
    p = progress()
    print(f'TOTAL={p["total"]} CURSOR={p["cursor"]} PROGRESS={p["percent"]}%')
    if scan_completed():
        print("SCAN COMPLETE")
    else:
        print("SCAN RUNNING")

if __name__ == "__main__":
    print_status()
