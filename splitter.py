import json
import os

from cursor import (
    load_cursor,
    save_cursor
)

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

    cursor = load_cursor()

    if cursor < 0:
        cursor = 0

    if cursor >= total:
        cursor = 0

    chunk = read_chunk(
        infile,
        cursor,
        batch_size
    )

    if not chunk:

        cursor = 0

        chunk = read_chunk(
            infile,
            0,
            batch_size
        )

    next_cursor = cursor + len(chunk)

    if next_cursor >= total:
        next_cursor = total

    save_cursor(
        next_cursor
    )

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
