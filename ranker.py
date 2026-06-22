import os

RESULT_FILE = "output/results.txt"
HTTPS_FILE = "output/https_live.txt"
BEST_FILE = "output/best_ips.txt"
DOMAINS_RAW_FILE = "output/domains_raw.txt"
TLS_FILE = "output/tls_live.txt"
TCP_FILE = "output/tcp_live.txt"

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

MAX_OUTPUT_IPS = 4000

def load_extra_data():
    latency_map = {}
    alpn_map = {}

    try:
        with open(TLS_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                parts = line.split(":")
                if len(parts) >= 5:
                    ip = parts[0]
                    port = parts[1]
                    key = f"{ip}:{port}"
                    try:
                        latency_map[key] = int(parts[2])
                    except:
                        latency_map[key] = 9999
                    alpn_map[key] = parts[3] if len(parts) > 3 else ""
    except:
        pass

    if not latency_map:
        try:
            with open(TCP_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    parts = line.split(":")
                    if len(parts) >= 3:
                        ip = parts[0]
                        port = parts[1]
                        key = f"{ip}:{port}"
                        try:
                            latency_map[key] = int(parts[2])
                        except:
                            latency_map[key] = 9999
        except:
            pass

    return latency_map, alpn_map

def load_https():
    data = {}

    try:
        with open(HTTPS_FILE, "r", encoding="utf-8") as f:
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

                old_rel = current.get("reliability", 0)
                old_ttfb = current.get("ttfb", 9999)

                if reliability > old_rel or (reliability == old_rel and ttfb < old_ttfb):
                    data[key] = candidate

    except:
        pass

    return data

def is_complete_item(item):
    required_fields = ["ip", "port", "latency", "cdn", "country", "provider", "alpn"]
    for field in required_fields:
        if field not in item:
            return False
        if field in ["ip", "cdn", "country", "provider", "alpn"]:
            if not item[field] or item[field] == "?" or item[field] == "None":
                return False
        if field == "port":
            if item[field] is None or item[field] == 0:
                return False
        if field == "latency":
            if item[field] is None or item[field] == 9999 or item[field] == 0:
                return False

    if "https" not in item or not item["https"]:
        return False

    https = item["https"]
    if "ttfb" not in https or "proto" not in https or "reliability" not in https:
        return False

    if https["ttfb"] is None or https["ttfb"] == 9999 or https["ttfb"] == 0:
        return False

    if not https["proto"] or https["proto"] == "-" or https["proto"] == "unknown":
        return False

    if https["reliability"] is None or https["reliability"] == 0:
        return False

    return True

def parse_line(line, latency_map, alpn_map):
    line = line.strip()
    if not line:
        return None

    parts = line.split("|")
    if len(parts) < 10:
        return None

    try:
        ip = parts[0]
        port = int(parts[1])
        status = int(parts[2]) if parts[2].isdigit() else 0
        ttfb = int(parts[3]) if parts[3].isdigit() else 9999
        proto = parts[4]
        reliability = float(parts[5]) if parts[5].replace('.', '').isdigit() else 0.0
        ws = parts[6] == "1" or parts[6].lower() == "true"
        cdn = parts[7]
        country = parts[8]
        provider = parts[9]

        key = f"{ip}:{port}"
        latency = latency_map.get(key, 9999)
        alpn = alpn_map.get(key, "")

    except (ValueError, IndexError):
        return None

    item = {
        "ip": ip,
        "port": port,
        "latency": latency,
        "tls": True,
        "cdn": cdn,
        "country": country,
        "provider": provider,
        "alpn": alpn,
        "https": {
            "status": status,
            "ttfb": ttfb,
            "proto": proto,
            "reliability": reliability,
            "ws": ws
        }
    }

    if not is_complete_item(item):
        return None

    return item

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
    score += ttfb_score(info.get("ttfb", 9999))

    reliability = info.get("reliability", 0)
    if reliability >= 0.9:
        score += RELIABILITY_BONUS

    proto = str(info.get("proto", "")).lower()
    if "h2" in proto:
        score += H2_BONUS

    return score

def score(item, https_info):
    total = 0

    if item.get("tls"):
        total += TLS_BONUS

    total += latency_score(item.get("latency", 9999))
    total += cdn_score(item.get("cdn", ""))
    total += alpn_score(item.get("alpn", ""))
    total += port_score(item.get("port", 0))
    total += https_score(https_info)

    return total

def load_results():
    data = []
    seen = set()

    latency_map, alpn_map = load_extra_data()

    try:
        with open(RESULT_FILE, "r", encoding="utf-8") as f:
            for line in f:
                item = parse_line(line, latency_map, alpn_map)
                if not item:
                    continue

                key = f'{item["ip"]}:{item["port"]}'
                if key in seen:
                    continue

                seen.add(key)
                data.append(item)
    except:
        pass

    return data

def load_domains_raw():
    domains = set()

    if not os.path.exists(DOMAINS_RAW_FILE):
        return domains

    try:
        with open(DOMAINS_RAW_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    domains.add(line.lower())
    except:
        pass

    return domains

def load_previous_best_ips():
    if not os.path.exists(BEST_FILE):
        return []

    previous = []

    try:
        with open(BEST_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                parts = line.split("|")
                if len(parts) < 10:
                    continue
                ip_port = parts[0]
                try:
                    score_val = int(parts[1].replace("S=", ""))
                except:
                    score_val = 0
                if ":" in ip_port:
                    previous.append({
                        "ip": ip_port.split(":")[0],
                        "port": int(ip_port.split(":")[1]),
                        "score": score_val,
                        "is_new": False
                    })
    except:
        pass

    return previous

def merge_and_limit(new_items, previous_items):
    combined = []

    for item in new_items:
        combined.append({
            "ip": item["ip"],
            "port": item["port"],
            "score": item["score"],
            "is_new": True,
            "latency": item.get("latency", 9999),
            "cdn": item.get("cdn", "unknown"),
            "country": item.get("country", "?"),
            "provider": item.get("provider", "?"),
            "alpn": item.get("alpn", ""),
            "https": item.get("https", {})
        })

    for old in previous_items:
        combined.append(old)

    combined.sort(key=lambda x: (-x["score"], 0 if x["is_new"] else 1, x.get("latency", 9999)))

    seen_keys = set()
    limited = []

    for item in combined:
        key = f"{item['ip']}:{item['port']}"
        if key in seen_keys:
            continue
        seen_keys.add(key)
        limited.append(item)
        if len(limited) >= MAX_OUTPUT_IPS:
            break

    return limited

def rank_results():
    data = load_results()
    https_map = load_https()
    domains = load_domains_raw()
    previous_best = load_previous_best_ips()

    new_scored_items = []

    for item in data:
        key = f'{item["ip"]}:{item["port"]}'
        https_info = https_map.get(key)

        if https_info is None:
            https_info = item.get("https", {})
        item["https"] = https_info
        item["score"] = score(item, https_info)
        new_scored_items.append(item)

    merged_items = merge_and_limit(new_scored_items, previous_best)

    os.makedirs("output", exist_ok=True)

    with open(BEST_FILE, "w", encoding="utf-8") as f:
        for item in merged_items:
            https_info = item.get("https") or {}
            ttfb = https_info.get("ttfb", "-")
            proto = https_info.get("proto", "-")
            rel = https_info.get("reliability", "-")
            latency = item.get("latency", 9999)
            cdn = item.get("cdn", "unknown")
            alpn = item.get("alpn", "")
            country = item.get("country", "?")
            provider = item.get("provider", "?")

            f.write(
                f'{item["ip"]}:{item["port"]}|'
                f'S={item["score"]}|'
                f'{latency}ms|'
                f'TTFB={ttfb}|'
                f'PROTO={proto}|'
                f'REL={rel}|'
                f'CDN={cdn}|'
                f'ALPN={alpn}|'
                f'{country}|'
                f'{provider}\n'
            )

    print(
        f"RANKED={len(data)} "
        f"HTTPS={len(https_map)} "
        f"DOMAINS={len(domains)} "
        f"BEST_IPS={len(merged_items)} "
        f"MAX_LIMIT={MAX_OUTPUT_IPS}"
    )

if __name__ == "__main__":
    rank_results()
