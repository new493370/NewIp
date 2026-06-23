import os
from colorama import init, Fore, Back, Style

init(autoreset=True)

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

    if len(parts) < 10:
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
        "cdn": parts[7],
        "country": parts[8],
        "provider": parts[9],
        "alpn": parts[4]
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

                if key in seen:
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


def color_text(text, color):
    return f"{color}{text}{Style.RESET_ALL}"


def print_partition(title, items, start_idx, end_idx):
    print(f"\n{Fore.CYAN}{Style.BRIGHT}{'='*130}")
    print(f"{Fore.YELLOW}{Style.BRIGHT}{title} ({start_idx+1}-{end_idx})")
    print(f"{Fore.CYAN}{Style.BRIGHT}{'='*130}")
    print(f"{Fore.WHITE}{'IP:PORT':<20} {Fore.YELLOW}{'SCORE':<6} {Fore.WHITE}{'LATENCY':<10} {Fore.WHITE}{'TTFB':<10} {Fore.WHITE}{'PROTO':<8} {Fore.WHITE}{'REL':<6} {Fore.WHITE}{'CDN':<15} {Fore.WHITE}{'ALPN':<8} {Fore.WHITE}{'COUNTRY':<20} {Fore.WHITE}{'PROVIDER'}")
    print(f"{Fore.CYAN}{'-'*130}")

    for item in items:
        https_info = item.get("https") or {}
        ttfb = https_info.get("ttfb", "-")
        proto = https_info.get("proto", "-")
        rel = https_info.get("reliability", "-")

        ip_port = f'{item["ip"]}:{item["port"]}'

        if item["score"] >= 18:
            score_colored = f"{Fore.GREEN}{Style.BRIGHT}{item['score']}"
        elif item["score"] >= 15:
            score_colored = f"{Fore.YELLOW}{Style.BRIGHT}{item['score']}"
        elif item["score"] >= 12:
            score_colored = f"{Fore.CYAN}{item['score']}"
        else:
            score_colored = f"{Fore.RED}{item['score']}"

        if item["latency"] <= 200:
            latency_colored = f"{Fore.GREEN}{item['latency']}ms"
        elif item["latency"] <= 400:
            latency_colored = f"{Fore.YELLOW}{item['latency']}ms"
        else:
            latency_colored = f"{Fore.RED}{item['latency']}ms"

        if ttfb != "-":
            if ttfb <= 300:
                ttfb_colored = f"{Fore.GREEN}{ttfb}ms"
            elif ttfb <= 700:
                ttfb_colored = f"{Fore.YELLOW}{ttfb}ms"
            else:
                ttfb_colored = f"{Fore.RED}{ttfb}ms"
        else:
            ttfb_colored = "-"

        if proto != "-":
            if proto == "h2":
                proto_colored = f"{Fore.GREEN}{Style.BRIGHT}{proto}"
            else:
                proto_colored = f"{Fore.CYAN}{proto}"
        else:
            proto_colored = "-"

        if rel != "-":
            if float(rel) >= 0.9:
                rel_colored = f"{Fore.GREEN}{rel}"
            else:
                rel_colored = f"{Fore.YELLOW}{rel}"
        else:
            rel_colored = "-"

        if item["cdn"] and item["cdn"].lower() != "unknown":
            cdn_colored = f"{Fore.MAGENTA}{Style.BRIGHT}{item['cdn']}"
        else:
            cdn_colored = f"{Fore.WHITE}{item['cdn']}"

        if item["alpn"] == "h2":
            alpn_colored = f"{Fore.GREEN}{Style.BRIGHT}{item['alpn']}"
        else:
            alpn_colored = f"{Fore.CYAN}{item['alpn']}"

        country_colored = f"{Fore.BLUE}{Style.BRIGHT}{item['country']}"
        provider_colored = f"{Fore.WHITE}{item['provider']}"

        print(f"{Fore.WHITE}{ip_port:<20} "
              f"{score_colored:<6} "
              f"{latency_colored:<10} "
              f"{ttfb_colored:<10} "
              f"{proto_colored:<8} "
              f"{rel_colored:<6} "
              f"{cdn_colored:<15} "
              f"{alpn_colored:<8} "
              f"{country_colored:<20} "
              f"{provider_colored}")


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

    total = len(ranked)
    partitions = 4
    part_size = max(1, total // partitions)

    if total > 0:
        for i in range(partitions):
            start = i * part_size
            end = start + part_size if i < partitions - 1 else total
            if start < total:
                part_items = ranked[start:end]
                if part_items:
                    avg_score = sum(x["score"] for x in part_items) / len(part_items)
                    if avg_score >= 17:
                        quality = "PREMIUM"
                        quality_color = Fore.GREEN
                    elif avg_score >= 14:
                        quality = "HIGH"
                        quality_color = Fore.YELLOW
                    elif avg_score >= 11:
                        quality = "MEDIUM"
                        quality_color = Fore.CYAN
                    else:
                        quality = "LOW"
                        quality_color = Fore.RED

                    print_partition(
                        f"{quality_color}{quality} QUALITY IPS - PARTITION {i+1}/{partitions}",
                        part_items,
                        start,
                        end
                    )

    print(f"\n{Fore.CYAN}{Style.BRIGHT}{'='*130}")
    print(f"{Fore.GREEN}Total Ranked: {total} | HTTPS: {len(https_map)} | Domains: {len(domains)}")
    print(f"{Fore.CYAN}Output saved to: {BEST_FILE}")
    print(f"{Fore.CYAN}{Style.BRIGHT}{'='*130}\n")


if __name__ == "__main__":
    rank_results()
