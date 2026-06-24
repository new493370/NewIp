import json
import os

from cursor import (
    load_cursor,
    save_cursor
)

from cache import load_cache, already_scanned

INPUT_FILE = "output/clean_ips.txt"
OUTPUT_FILE = "output/current_part.txt"


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


def split_file(
    infile=INPUT_FILE
):

    cfg = load_config()

    batch_size = cfg.get(
        "batch_size",
        20000
    )

    ports = cfg.get("ports", [])

    total = count_lines(
        infile
    )

    if total <= 0:

        write_lines(
            OUTPUT_FILE,
            []
        )

        print(
            "NO CLEAN IPS"
        )

        return OUTPUT_FILE

    scanned_cache = load_cache()

    available_ips = []
    line_idx = 0

    try:
        with open(infile, "r", encoding="utf-8") as f:
            for line in f:
                ip = line.strip()
                if not ip:
                    continue

                if any(already_scanned(scanned_cache, ip, port) for port in ports):
                    line_idx += 1
                    continue

                available_ips.append(ip)
                line_idx += 1

                if len(available_ips) >= batch_size:
                    break
    except:
        pass

    if not available_ips:
        print("NO NEW IPS AVAILABLE")
        write_lines(OUTPUT_FILE, [])
        save_cursor(total)
        return OUTPUT_FILE

    cursor = load_cursor()
    next_cursor = cursor + len(available_ips)
    if next_cursor > total:
        next_cursor = total

    save_cursor(next_cursor)

    write_lines(OUTPUT_FILE, available_ips)

    percent = round(
        (
            next_cursor / total
        ) * 100,
        2
    )

    if percent > 100:
        percent = 100

    print(
        f"TOTAL={total} "
        f"NEW={len(available_ips)} "
        f"PROGRESS={percent}%"
    )

    return OUTPUT_FILE


if __name__ == "__main__":
    split_file()
