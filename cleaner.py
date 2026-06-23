import ipaddress
import json
import os
import random

INPUT_FILE = "output/ip_bank.txt"
OUTPUT_FILE = "output/clean_ips.txt"
TEMP_FILE = "output/clean_ips.tmp"

MAX_CIDR_EXPAND = 4096
LARGE_CIDR_SAMPLE = 1024


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


def ensure_output():
    os.makedirs(
        "output",
        exist_ok=True
    )


def sample_network(
    net,
    count
):
    hosts = int(
        net.num_addresses
    )

    if hosts <= 2:
        return []

    usable = hosts - 2
    count = min(
        count,
        usable
    )

    picked = set()

    while len(picked) < count:
        idx = random.randint(
            1,
            usable
        )
        picked.add(
            str(
                net.network_address + idx
            )
        )

    return picked


def write_ip(
    fh,
    ip,
    seen
):
    ip = str(ip).strip()

    if not ip:
        return 0

    if ip in seen:
        return 0

    seen.add(ip)
    fh.write(ip + "\n")
    return 1


def process_line(
    line,
    fh,
    seen
):
    line = line.strip()

    if not line:
        return 0

    try:

        if "/" in line:

            net = ipaddress.ip_network(
                line,
                strict=False
            )

            if net.num_addresses <= MAX_CIDR_EXPAND:

                count = 0

                for ip in net.hosts():
                    count += write_ip(
                        fh,
                        ip,
                        seen
                    )

                return count

            else:

                sampled = sample_network(
                    net,
                    LARGE_CIDR_SAMPLE
                )

                count = 0

                for ip in sampled:
                    count += write_ip(
                        fh,
                        ip,
                        seen
                    )

                return count

        else:

            ipaddress.ip_address(
                line
            )

            return write_ip(
                fh,
                line,
                seen
            )

    except:
        return 0


def clean_ips():

    ensure_output()

    seen = set()
    total = 0
    processed = 0

    try:

        with open(
            INPUT_FILE,
            "r",
            encoding="utf-8"
        ) as src, open(
            TEMP_FILE,
            "w",
            encoding="utf-8"
        ) as dst:

            for line in src:

                processed += 1

                total += process_line(
                    line,
                    dst,
                    seen
                )

                if processed % 10000 == 0:
                    print(
                        f"LINES={processed} "
                        f"IPS={total}"
                    )

    except:
        return

    os.replace(
        TEMP_FILE,
        OUTPUT_FILE
    )

    print(
        f"CLEAN IPS={total}"
    )


if __name__ == "__main__":
    clean_ips()
