import os
import sys

LIVE_BANK_FILE = "output/live_bank.txt"
MAX_LIVE_BANK_SIZE_BYTES = 50 * 1024 * 1024


def ensure_output():
    os.makedirs("output", exist_ok=True)


def normalize(item):
    return str(item).strip()


def read_live_bank():
    ensure_output()
    if not os.path.exists(LIVE_BANK_FILE):
        return set()
    try:
        with open(LIVE_BANK_FILE, "r", encoding="utf-8") as f:
            return {normalize(line) for line in f if normalize(line)}
    except:
        return set()


def live_exists(item):
    item = normalize(item)
    if not item:
        return False
    return item in read_live_bank()


def append_live(items):
    ensure_output()
    if not items:
        return 0

    new_items = []
    existing = read_live_bank()

    for item in items:
        item = normalize(item)
        if not item or item in existing:
            continue
        existing.add(item)
        new_items.append(item)

    if not new_items:
        return 0

    try:
        with open(LIVE_BANK_FILE, "a", encoding="utf-8") as f:
            for item in new_items:
                f.write(item + "\n")
        _rotate_live_bank_if_needed()
        return len(new_items)
    except:
        return 0


def replace_live(items):
    ensure_output()
    data = sorted({normalize(x) for x in items if normalize(x)})
    try:
        with open(LIVE_BANK_FILE, "w", encoding="utf-8") as f:
            f.write("\n".join(data))
        return len(data)
    except:
        return 0


def dedupe_live_bank():
    ensure_output()
    data = sorted(read_live_bank())
    try:
        with open(LIVE_BANK_FILE, "w", encoding="utf-8") as f:
            f.write("\n".join(data))
        return len(data)
    except:
        return 0


def live_count():
    return len(read_live_bank())


def read_live_lines():
    return sorted(read_live_bank())


def clear_live_bank():
    ensure_output()
    with open(LIVE_BANK_FILE, "w", encoding="utf-8") as f:
        f.write("")


def _rotate_live_bank_if_needed():
    if not os.path.exists(LIVE_BANK_FILE):
        return

    file_size = os.path.getsize(LIVE_BANK_FILE)
    if file_size <= MAX_LIVE_BANK_SIZE_BYTES:
        return

    print(f"🧹 Live bank size ({file_size} bytes) exceeded limit. Rotating...")

    try:
        with open(LIVE_BANK_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()

        if not lines:
            return

        keep_count = len(lines) // 2
        if keep_count < 1:
            keep_count = 1

        with open(LIVE_BANK_FILE, "w", encoding="utf-8") as f:
            f.writelines(lines[-keep_count:])

        print(f"✅ Live bank rotated: kept {keep_count} lines (was {len(lines)})")

    except Exception as e:
        print(f"⚠️ Error rotating live bank: {e}")


if __name__ == "__main__":
    count = dedupe_live_bank()
    print(f"LIVE={count}")
