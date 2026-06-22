import os

LIVE_BANK_FILE = "output/live_bank.txt"

def ensure_output():
    os.makedirs(
        "output",
        exist_ok=True
    )

def normalize(item):
    return str(
        item
    ).strip()

def read_live_bank():
    ensure_output()

    if not os.path.exists(
        LIVE_BANK_FILE
    ):
        print(f"[LIVEBANK] File {LIVE_BANK_FILE} does not exist, returning empty set")
        return set()

    try:
        with open(
            LIVE_BANK_FILE,
            "r",
            encoding="utf-8"
        ) as f:
            lines = [normalize(line) for line in f if normalize(line)]
            print(f"[LIVEBANK] Read {len(lines)} existing entries from {LIVE_BANK_FILE}")
            return set(lines)
    except Exception as e:
        print(f"[LIVEBANK] ERROR reading {LIVE_BANK_FILE}: {e}")
        return set()

def live_exists(item):
    item = normalize(item)

    if not item:
        return False

    exists = item in read_live_bank()
    print(f"[LIVEBANK] Check existence for {item}: {exists}")
    return exists

def append_live(items):
    ensure_output()

    if not items:
        print("[LIVEBANK] No items to append, creating empty file if not exists")
        if not os.path.exists(LIVE_BANK_FILE):
            try:
                with open(LIVE_BANK_FILE, "w", encoding="utf-8") as f:
                    pass
                print(f"[LIVEBANK] Created empty {LIVE_BANK_FILE}")
            except Exception as e:
                print(f"[LIVEBANK] ERROR creating empty file: {e}")
                return 0
        return 0

    print(f"[LIVEBANK] Attempting to append {len(items)} items to {LIVE_BANK_FILE}")

    existing = read_live_bank()
    new_items = []

    for item in items:
        item = normalize(item)

        if not item:
            print("[LIVEBANK] Skipping empty/normalized item")
            continue

        if item in existing:
            continue

        existing.add(item)
        new_items.append(item)

    if not new_items:
        print(f"[LIVEBANK] No new items to append (all {len(items)} already exist)")
        return 0

    print(f"[LIVEBANK] Adding {len(new_items)} new items to {LIVE_BANK_FILE}")

    try:
        with open(
            LIVE_BANK_FILE,
            "a",
            encoding="utf-8"
        ) as f:
            for item in new_items:
                f.write(
                    item + "\n"
                )

        print(f"[LIVEBANK] Successfully appended {len(new_items)} items to {LIVE_BANK_FILE}")
        return len(new_items)

    except Exception as e:
        print(f"[LIVEBANK] ERROR appending to {LIVE_BANK_FILE}: {e}")
        return 0

def replace_live(items):
    ensure_output()

    print(f"[LIVEBANK] Replacing entire contents of {LIVE_BANK_FILE} with {len(items)} items")

    data = sorted(
        {
            normalize(x)
            for x in items
            if normalize(x)
        }
    )

    print(f"[LIVEBANK] Normalized and deduplicated to {len(data)} unique items")

    try:
        with open(
            LIVE_BANK_FILE,
            "w",
            encoding="utf-8"
        ) as f:
            f.write(
                "\n".join(data)
            )

        print(f"[LIVEBANK] Successfully replaced {LIVE_BANK_FILE} with {len(data)} items")
        return len(data)

    except Exception as e:
        print(f"[LIVEBANK] ERROR replacing {LIVE_BANK_FILE}: {e}")
        return 0

def dedupe_live_bank():
    ensure_output()

    print(f"[LIVEBANK] Deduplicating {LIVE_BANK_FILE}")

    if not os.path.exists(LIVE_BANK_FILE):
        print(f"[LIVEBANK] File {LIVE_BANK_FILE} does not exist, creating empty")
        try:
            with open(LIVE_BANK_FILE, "w", encoding="utf-8") as f:
                pass
            print(f"[LIVEBANK] Created empty {LIVE_BANK_FILE}")
            return 0
        except Exception as e:
            print(f"[LIVEBANK] ERROR creating empty file: {e}")
            return 0

    data = sorted(
        read_live_bank()
    )

    print(f"[LIVEBANK] Read {len(data)} unique entries from {LIVE_BANK_FILE}")

    try:
        with open(
            LIVE_BANK_FILE,
            "w",
            encoding="utf-8"
        ) as f:
            f.write(
                "\n".join(data)
            )

        print(f"[LIVEBANK] Successfully deduplicated {LIVE_BANK_FILE}, {len(data)} entries remain")
        return len(data)

    except Exception as e:
        print(f"[LIVEBANK] ERROR deduplicating {LIVE_BANK_FILE}: {e}")
        return 0

def live_count():
    count = len(
        read_live_bank()
    )
    print(f"[LIVEBANK] Current count: {count} entries in {LIVE_BANK_FILE}")
    return count

def read_live_lines():
    lines = sorted(
        read_live_bank()
    )
    print(f"[LIVEBANK] Returning {len(lines)} sorted entries from {LIVE_BANK_FILE}")
    return lines

def clear_live_bank():
    ensure_output()

    print(f"[LIVEBANK] Clearing {LIVE_BANK_FILE}")

    try:
        with open(
            LIVE_BANK_FILE,
            "w",
            encoding="utf-8"
        ) as f:
            f.write("")

        print(f"[LIVEBANK] Successfully cleared {LIVE_BANK_FILE}")
    except Exception as e:
        print(f"[LIVEBANK] ERROR clearing {LIVE_BANK_FILE}: {e}")

if __name__ == "__main__":
    print("[LIVEBANK] Running livebank.py standalone")
    count = dedupe_live_bank()
    print(f"[LIVEBANK] LIVE={count}")
