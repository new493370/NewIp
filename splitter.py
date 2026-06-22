import json
import os
from datetime import datetime

from cursor import (
    load_cursor,
    save_cursor,
    reset_cursor
)

INPUT_FILE = "output/clean_ips.txt"
OUTPUT_FILE = "output/current_part.txt"
COUNT_CACHE = "output/line_count_cache.txt"
LAST_TOTAL_FILE = "output/last_total.txt"
SPLIT_HISTORY_FILE = "output/split_history.json"

_CONFIG_CACHE = None
_CONFIG_MTIME = None


def load_config():
    global _CONFIG_CACHE, _CONFIG_MTIME
    
    config_path = "config.json"
    
    if not os.path.exists(config_path):
        return {}
    
    current_mtime = os.path.getmtime(config_path)
    
    if _CONFIG_CACHE is not None and _CONFIG_MTIME == current_mtime:
        return _CONFIG_CACHE
    
    try:
        with open(
            config_path,
            "r",
            encoding="utf-8"
        ) as f:
            _CONFIG_CACHE = json.load(f)
            _CONFIG_MTIME = current_mtime
            return _CONFIG_CACHE
    except:
        return {}


def get_cached_count(path):
    if not os.path.exists(COUNT_CACHE):
        return None
    
    try:
        with open(COUNT_CACHE, "r") as f:
            cached_total, cached_mtime = f.read().strip().split(",")
            if float(cached_mtime) == os.path.getmtime(path):
                return int(cached_total)
    except:
        pass
    
    return None


def count_lines(path):
    cached = get_cached_count(path)
    
    if cached is not None:
        return cached
    
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
    
    try:
        with open(COUNT_CACHE, "w") as f:
            f.write(f"{total},{os.path.getmtime(path)}")
    except:
        pass
    
    return total


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


def read_chunk(
    path,
    start,
    size
):
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


def should_reset_cursor(total, old_total):
    if old_total is None:
        return True
    if total > old_total:
        return True
    if total < old_total:
        return True
    return False


def load_split_history():
    if os.path.exists(SPLIT_HISTORY_FILE):
        try:
            with open(SPLIT_HISTORY_FILE, "r") as f:
                return json.load(f)
        except:
            return {}
    return {}


def save_split_history(history):
    with open(SPLIT_HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2)


def split_file(
    infile=INPUT_FILE
):
    cfg = load_config()
    
    batch_size = cfg.get(
        "batch_size",
        20000
    )
    
    total = count_lines(
        infile
    )
    
    if total <= 0:
        write_lines(
            OUTPUT_FILE,
            []
        )
        
        reset_cursor()
        
        print(
            "NO CLEAN IPS"
        )
        
        return OUTPUT_FILE
    
    old_total = None
    if os.path.exists(LAST_TOTAL_FILE):
        try:
            with open(LAST_TOTAL_FILE, "r") as f:
                old_total = int(f.read().strip())
        except:
            pass
    
    if should_reset_cursor(total, old_total):
        reset_cursor()
        with open(LAST_TOTAL_FILE, "w") as f:
            f.write(str(total))
        print(
            f"RESET CURSOR - "
            f"NEW TOTAL: {total} "
            f"(OLD: {old_total})"
        )
    
    cursor = load_cursor()
    
    if cursor < 0:
        cursor = 0
    
    if cursor >= total:
        cursor = 0
        save_cursor(0)
    
    chunk = read_chunk(
        infile,
        cursor,
        batch_size
    )
    
    if not chunk:
        cursor = 0
        save_cursor(0)
        chunk = read_chunk(
            infile,
            0,
            batch_size
        )
    
    next_cursor = cursor + len(chunk)
    
    if next_cursor >= total:
        next_cursor = 0
        save_cursor(0)
        print("SCAN CYCLE COMPLETE - RESETTING")
    else:
        save_cursor(next_cursor)
    
    write_lines(
        OUTPUT_FILE,
        chunk
    )
    
    percent = round(
        (
            next_cursor / total
        ) * 100,
        2
    )
    
    if percent > 100:
        percent = 100
    
    history = load_split_history()
    history["last_split"] = datetime.now().isoformat()
    history["total_ips"] = total
    history["batch_size"] = batch_size
    history["cursor"] = cursor
    history["next_cursor"] = next_cursor
    history["progress"] = percent
    save_split_history(history)
    
    print(
        f"TOTAL={total} "
        f"CURSOR={cursor} "
        f"END={next_cursor} "
        f"PART={len(chunk)} "
        f"PROGRESS={percent}%"
    )
    
    return OUTPUT_FILE


if __name__ == "__main__":
    split_file()
