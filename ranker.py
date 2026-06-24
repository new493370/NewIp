import os

RESULT_FILE = "output/results.txt"
HTTPS_FILE = "output/https_live.txt"
BEST_FILE = "output/best_ips.txt"
DOMAINS_RAW_FILE = "output/domains_raw.txt"

TLS_BONUS = 2
KNOWN_CDN_BONUS = 2
H2_BONUS = 2
ALPN_BONUS = 1
HTTPS_BONUS = 4
RELIABILITY_BONUS = 3

FAST_LATENCY_BONUS = 3
MID_LATENCY_BONUS = 2
SLOW_LATENCY_BONUS = 1

FAST_TTFB_BONUS = 4
MID_TTFB_BONUS = 2
SLOW_TTFB_BONUS = 1

STABLE_PORTS = {
    443,
    2053,
    2083,
    2087,
    2096,
    8443
}

STABLE_PORT_BONUS = 1


def load_https():
    data = {}

    try:
        with open(
            HTTPS_FILE,
            "r",
            encoding="utf-8"
        ) as f:

            for line in f:
                line = line.strip()

                if not line:
                    continue

                parts = line.split("|")

                if len(parts) < 6:
                    continue

                try:
                    ip = parts[0]
                    port = int(parts[1])
                    status = int(parts[2])
                    ttfb = int(parts[3])
                    proto = parts[4]
                    reliability = float(parts[5])
                except:
                    continue

                key = f"{ip}:{port}"

                current = data.get(key)

                candidate = {
                    "status": status,
                    "ttfb": ttfb,
                    "proto": proto,
                    "reliability": reliability
                }

                if current is None:
                    data[key] = candidate
                    continue

                old_rel = current.get(
                    "reliability",
                    0
                )

                old_ttfb = current.get(
                    "ttfb",
                    9999
                )

                if (
                    reliability > old_rel
                    or (
                        reliability == old_rel
                        and ttfb < old_ttfb
                    )
                ):
                    data[key] = candidate

    except:
        pass

    return data


def parse_line(line):
    line = line.strip()

    if not line:
        return None

    parts = line.split("|")

    if len(parts) < 8:
        return None

    try:
        latency = int(parts[2])
    except:
        latency = 9999

    try:
        port = int(parts[1])
    except:
        return None

    tls = parts[3] == "True"

    return {
        "ip": parts[0],
        "port": port,
        "latency": latency,
        "tls": tls,
        "cdn": parts[4],
        "country": parts[5],
        "provider": parts[6],
        "alpn": parts[7]
    }


def latency_score(latency):
    if latency <= 150:
        return FAST_LATENCY_BONUS

    if latency <= 300:
        return MID_LATENCY_BONUS

    if latency <= 500:
        return SLOW_LATENCY_BONUS

    return 0


def ttfb_score(ttfb):
    if ttfb <= 300:
        return FAST_TTFB_BONUS

    if ttfb <= 700:
        return MID_TTFB_BONUS

    if ttfb <= 1200:
        return SLOW_TTFB_BONUS

    return 0


def cdn_score(cdn):
    if not cdn:
        return 0

    cdn = str(cdn).strip().lower()

    if cdn == "unknown":
        return 0

    return KNOWN_CDN_BONUS


def alpn_score(alpn):
    if not alpn:
        return 0

    alpn = str(alpn).strip().lower()

    score = ALPN_BONUS

    if alpn == "h2":
        score += H2_BONUS

    return score


def port_score(port):
    if port in STABLE_PORTS:
        return STABLE_PORT_BONUS

    return 0


def https_score(info):
    if not info:
        return 0

    score = HTTPS_BONUS

    score += ttfb_score(
        info.get(
            "ttfb",
            9999
        )
    )

    reliability = info.get(
        "reliability",
        0
    )

    if reliability >= 0.9:
        score += RELIABILITY_BONUS

    proto = str(
        info.get(
            "proto",
            ""
        )
    ).lower()

    if "h2" in proto:
        score += H2_BONUS

    return score


def score(
    item,
    https_info
):
    total = 0

    if item.get("tls"):
        total += TLS_BONUS

    total += latency_score(
        item.get(
            "latency",
            9999
        )
    )

    total += cdn_score(
        item.get(
            "cdn",
            ""
        )
    )

    total += alpn_score(
        item.get(
            "alpn",
            ""
        )
    )

    total += port_score(
        item.get(
            "port",
            0
        )
    )

    total += https_score(
        https_info
    )

    return total


def load_results():
    data = []
    seen = set()

    try:
        with open(
            RESULT_FILE,
            "r",
            encoding="utf-8"
        ) as f:

            for line in f:
                item = parse_line(line)

                if not item:
                    continue

                key = (
                    f'{item["ip"]}:'
                    f'{item["port"]}'
                )

                old = seen

                if key in old:
                    continue

                seen.add(key)
                data.append(item)

    except:
        pass

    return data


def load_domains_raw():
    domains = set()

    if not os.path.exists(
        DOMAINS_RAW_FILE
    ):
        return domains

    try:
        with open(
            DOMAINS_RAW_FILE,
            "r",
            encoding="utf-8"
        ) as f:

            for line in f:
                line = line.strip()

                if line:
                    domains.add(
                        line.lower()
                    )

    except:
        pass

    return domains


def rank_results():
    data = load_results()
    https_map = load_https()
    domains = load_domains_raw()

    ranked = []

    for item in data:

        key = (
            f'{item["ip"]}:'
            f'{item["port"]}'
        )

        https_info = https_map.get(
            key
        )

        item["https"] = https_info
        item["score"] = score(
            item,
            https_info
        )

        ranked.append(
            item
        )

    ranked.sort(
        key=lambda x: (
            -x["score"],
            x.get(
                "latency",
                9999
            ),
            x.get(
                "port",
                65535
            )
        )
    )

    os.makedirs(
        "output",
        exist_ok=True
    )

    with open(
        BEST_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        for item in ranked:

            https_info = item.get(
                "https"
            ) or {}

            ttfb = https_info.get(
                "ttfb",
                "-"
            )

            proto = https_info.get(
                "proto",
                "-"
            )

            rel = https_info.get(
                "reliability",
                "-"
            )

            f.write(
                f'{item["ip"]}:{item["port"]} '
                f'S={item["score"]} '
                f'{item["latency"]}ms '
                f'TTFB={ttfb} '
                f'PROTO={proto} '
                f'REL={rel} '
                f'CDN={item["cdn"]} '
                f'ALPN={item["alpn"]} '
                f'{item["country"]} '
                f'{item["provider"]}\n'
            )

    print(
        f"RANKED={len(ranked)} "
        f"HTTPS={len(https_map)} "
        f"DOMAINS={len(domains)}"
    )


if __name__ == "__main__":
    rank_results()
