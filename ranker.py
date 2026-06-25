import os
import json

RESULT_FILE = "output/results.txt"
BEST_FILE = "output/best_ips.txt"
DOMAINS_RAW_FILE = "output/domains_raw.txt"
TLS_FILE = "output/tls_live.txt"
GEO_FILE = "output/geo_cache.json"

KNOWN_CDN_BONUS = 2
H2_BONUS = 2
RELIABILITY_BONUS = 3

FAST_TTFB_BONUS = 4
MID_TTFB_BONUS = 2
SLOW_TTFB_BONUS = 1

STABLE_PORTS = {443, 2053, 2083, 2087, 2096, 8443}
STABLE_PORT_BONUS = 1


def parse_line(line):
    line = line.strip()

    if not line:
        return None

    parts = line.split("|")

    if len(parts) < 10:
        return None

    try:
        port = int(parts[1])
    except:
        return None

    try:
        status = int(parts[2])
    except:
        status = 0

    try:
        ttfb = int(parts[3])
    except:
        ttfb = 9999

    try:
        reliability = float(parts[5])
    except:
        reliability = 0

    return {
        "ip": parts[0],
        "port": port,
        "status": status,
        "ttfb": ttfb,
        "proto": parts[4],
        "reliability": reliability,
        "ws": parts[6],
        "cdn": parts[7],
        "country": parts[8],
        "provider": parts[9]
    }


def load_results():
    data = []
    seen = set()

    try:
        with open(RESULT_FILE, "r", encoding="utf-8") as f:
            for line in f:
                item = parse_line(line)
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


def load_tls_sni():
    sni_map = {}

    if not os.path.exists(TLS_FILE):
        return sni_map

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
                    sni = parts[4]
                    key = f"{ip}:{port}"
                    sni_map[key] = sni
    except:
        pass

    return sni_map


def load_geo_city():
    city_map = {}

    if not os.path.exists(GEO_FILE):
        return city_map

    try:
        with open(GEO_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            for ip, info in data.items():
                if isinstance(info, dict):
                    city = info.get("city", "")
                    if city and city != "Unknown":
                        city_map[ip] = city
    except:
        pass

    return city_map


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


def get_port_type(port):
    if port in {443, 8443, 2053, 2083, 2087, 2096}:
        return "HTTPS"
    elif port in {80, 8080}:
        return "HTTP"
    else:
        return "UNKNOWN"


def rank_results():
    data = load_results()
    domains_set = load_domains_raw()
    sni_map = load_tls_sni()
    city_map = load_geo_city()

    ranked = []

    for item in data:
        item["score"] = score(item)
        ranked.append(item)

    ranked.sort(
        key=lambda x: (
            -x["score"],
            x.get("ttfb", 9999),
            x.get("port", 65535)
        )
    )

    os.makedirs("output", exist_ok=True)

    with open(BEST_FILE, "w", encoding="utf-8") as f:
        for item in ranked:
            ip = item["ip"]
            port = item["port"]
            key = f"{ip}:{port}"
            
            country = item.get("country", "-")
            provider = item.get("provider", "-")
            
            sni = sni_map.get(key, "-")
            
            city = city_map.get(ip, "-")
            
            port_type = get_port_type(port)
            
            domain = "-"
            for d in sorted(domains_set):
                if d in sni or sni in d:
                    domain = d
                    break
            
            parts = [
                f'[IP: {ip}]',
                f'[PORT: {port}]',
                f'[SCORE={item["score"]}]',
                f'[TTFB={item.get("ttfb", "-")}ms]',
                f'[PROTO={item.get("proto", "-")}]',
                f'[REL={item.get("reliability", "-")}]',
                f'[CDN={item.get("cdn", "-")}]',
                f'[TYPE={port_type}]'
            ]
            
            if sni and sni != "-":
                parts.append(f'[SNI={sni}]')
            
            if domain and domain != "-":
                parts.append(f'[DOMAIN={domain}]')
            
            if city and city != "-" and city != "Unknown":
                parts.append(f'[City={city}]')
            
            if country and country != "-" and country != "Unknown":
                parts.append(f'[Country={country}]')
            
            if provider and provider != "-" and provider != "Unknown":
                parts.append(f'[Provider={provider}]')
            
            line = " ".join(parts) + "\n"
            f.write(line)

    print(f"RANKED={len(ranked)} DOMAINS={len(domains_set)}")


def ttfb_score(ttfb):
    if ttfb <= 150:
        return FAST_TTFB_BONUS
    elif ttfb <= 300:
        return MID_TTFB_BONUS
    elif ttfb <= 500:
        return SLOW_TTFB_BONUS
    else:
        return 0


def cdn_score(cdn):
    if not cdn:
        return 0
    cdn = str(cdn).strip().lower()
    if cdn == "unknown":
        return 0
    if cdn in ["cloudflare", "fastly", "akamai", "bunny", "gcore", "vercel", "cloudfront"]:
        return KNOWN_CDN_BONUS
    return 0


def port_score(port):
    if port in STABLE_PORTS:
        return STABLE_PORT_BONUS
    return 0


def score(item):
    total = 0
    
    total += ttfb_score(item.get("ttfb", 9999))
    total += cdn_score(item.get("cdn", ""))
    total += port_score(item.get("port", 0))
    
    proto = item.get("proto", "").lower()
    if "h2" in proto:
        total += H2_BONUS
    
    reliability = item.get("reliability", 0)
    if reliability >= 0.9:
        total += RELIABILITY_BONUS
    
    return total


if __name__ == "__main__":
    rank_results()
