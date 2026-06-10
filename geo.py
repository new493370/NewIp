import requests
from cache import load_geo_cache, save_geo_cache

API_TIMEOUT = 5

def geo_lookup(ip):
    cache = load_geo_cache()

    if ip in cache:
        return cache[ip]

    try:
        r = requests.get(
            f"https://ipwho.is/{ip}",
            timeout=API_TIMEOUT
        )

        data = r.json()

        result = {
            "country": data.get("country"),
            "asn": data.get("connection", {}).get("asn"),
            "provider": data.get("connection", {}).get("isp")
        }

        cache[ip] = result
        save_geo_cache(cache)

        return result

    except:
        return {}
