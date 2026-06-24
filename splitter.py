import json
import os

from cursor import (
    load_cursor,
    save_cursor
)

INPUT_FILE = "output/clean_ips.txt"
OUTPUT_FILE = "output/current_part.txt"
CACHE_FILE = "output/scanned_cache.txt"


def load_config():
    try:
        with open(
            "config.json",
            "r",
            encoding="utf-8"
        ) as f:
            return json.load(f)
    except:
        return {}


def load_scanned_cache():
    """بارگذاری IPهای اسکن شده از کش"""
    cache = set()
    if not os.path.exists(CACHE_FILE):
        return cache
    
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                # فرمت: ip:port:status
                parts = line.split(":")
                if len(parts) >= 2:
                    cache.add(parts[0])  # فقط IP
    except:
        pass
    
    return cache


def write_lines(
    path,
    lines
):
    with open(
        path,
        "w",
        encoding="utf-8"
    ) as f:
        f.write(
            "\n".join(lines)
        )


def count_lines(path):
    total = 0

    try:
        with open(
            path,
            "r",
            encoding="utf-8"
        ) as f:
            for line in f:
                if line.strip():
                    total += 1
    except:
        return 0

    return total


def read_chunk(
    path,
    start,
    size,
    scanned_cache
):
    """خواندن یک بخش با فیلتر IPهای اسکن شده"""
    chunk = []
    idx = 0

    try:
        with open(
            path,
            "r",
            encoding="utf-8"
        ) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                
                # اسکیپ IPهای اسکن شده
                if line in scanned_cache:
                    idx += 1
                    continue
                
                if idx < start:
                    idx += 1
                    continue
                
                chunk.append(line)
                
                if len(chunk) >= size:
                    break
                
                idx += 1
    except:
        return []
    
    return chunk


def split_file(
    infile=INPUT_FILE
):
    cfg = load_config()
    batch_size = cfg.get("batch_size", 20000)
    
    # بارگذاری کش IPهای اسکن شده
    scanned_cache = load_scanned_cache()
    
    # شمارش کل IPها
    total = count_lines(infile)
    
    if total <= 0:
        write_lines(OUTPUT_FILE, [])
        print("NO CLEAN IPS")
        return OUTPUT_FILE
    
    # محاسبه IPهای باقی‌مانده
    cursor = load_cursor()
    if cursor < 0:
        cursor = 0
    
    # پیدا کردن موقعیت شروع واقعی با در نظر گرفتن IPهای اسکن شده
    actual_start = cursor
    
    # اگر به انتها رسیدیم، دوباره از اول شروع کن
    if cursor >= total:
        cursor = 0
        save_cursor(0)
    
    # خواندن بخش بعدی
    chunk = read_chunk(
        infile,
        cursor,
        batch_size,
        scanned_cache
    )
    
    # اگر بخش خالی بود یا wrap-around
    if not chunk:
        cursor = 0
        save_cursor(0)
        chunk = read_chunk(
            infile,
            0,
            batch_size,
            scanned_cache
        )
    
    # اگر باز هم خالی بود یعنی همه IPها اسکن شده‌اند
    if not chunk:
        write_lines(OUTPUT_FILE, [])
        print("ALL IPS SCANNED - WAITING FOR NEW IPS")
        return OUTPUT_FILE
    
    # به‌روزرسانی cursor با تعداد IPهای اسکن شده
    # باید موقعیت آخرین IP خوانده شده رو پیدا کنیم
    last_ip = chunk[-1]
    idx = 0
    found = False
    
    try:
        with open(infile, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                if line == last_ip:
                    found = True
                    break
                idx += 1
    except:
        pass
    
    if found:
        next_cursor = idx + 1
    else:
        next_cursor = cursor + len(chunk)
    
    save_cursor(next_cursor)
    
    write_lines(OUTPUT_FILE, chunk)
    
    percent = round((next_cursor / total) * 100, 2)
    if percent > 100:
        percent = 100
    
    print(
        f"TOTAL={total} "
        f"CURSOR={cursor} "
        f"END={next_cursor} "
        f"PART={len(chunk)} "
        f"PROGRESS={percent}% "
        f"CACHED={len(scanned_cache)}"
    )
    
    return OUTPUT_FILE


if __name__ == "__main__":
    split_file()
