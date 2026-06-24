import requests
from cache import load_geo_cache, save_geo_cache

API_TIMEOUT = 8

def geo_lookup(ip):
    cache = load_geo_cache()

    if ip in cache:
        return cache[ip]

    result = None

    sources = [
        {
            "url": f"https://ipinfo.io/{ip}/json",
            "parser": lambda d: {
                "country": d.get("country"),
                "region": d.get("region"),
                "city": d.get("city"),
                "provider": d.get("org"),
                "asn": d.get("asn")
            } if d.get("country") else None
        },
        {
            "url": f"http://ip-api.com/json/{ip}?fields=status,message,country,regionName,city,isp,org,as,mobile,proxy,hosting",
            "parser": lambda d: {
                "country": d.get("country"),
                "region": d.get("regionName"),
                "city": d.get("city"),
                "provider": d.get("isp") or d.get("org"),
                "asn": d.get("as")
            } if d.get("status") == "success" else None
        },
        {
            "url": f"https://ipwho.is/{ip}",
            "parser": lambda d: {
                "country": d.get("country"),
                "region": d.get("region"),
                "city": d.get("city"),
                "provider": d.get("connection", {}).get("isp"),
                "asn": d.get("connection", {}).get("asn")
            } if d.get("success") is not False else None
        },
        {
            "url": f"https://ipapi.co/{ip}/json/",
            "parser": lambda d: {
                "country": d.get("country_name"),
                "region": d.get("region"),
                "city": d.get("city"),
                "provider": d.get("org"),
                "asn": d.get("asn")
            } if d.get("country_name") else None
        },
        {
            "url": f"https://freeipapi.com/api/json/{ip}",
            "parser": lambda d: {
                "country": d.get("countryName"),
                "region": d.get("regionName"),
                "city": d.get("cityName"),
                "provider": None,
                "asn": None
            } if d.get("countryName") else None
        },
        {
            "url": f"https://api.ipvigilante.com/{ip}",
            "parser": lambda d: {
                "country": d.get("data", {}).get("country_name"),
                "region": d.get("data", {}).get("subdivision_1_name"),
                "city": d.get("data", {}).get("city_name"),
                "provider": d.get("data", {}).get("isp"),
                "asn": d.get("data", {}).get("asn")
            } if d.get("status") == "success" else None
        }
    ]

    for source in sources:
        try:
            headers = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
            r = requests.get(source["url"], timeout=API_TIMEOUT, headers=headers)
            if r.status_code == 200:
                data = r.json()
                parsed = source["parser"](data)
                if parsed and parsed.get("country"):
                    result = parsed
                    break
        except:
            continue

    if result is None:
        result = {
            "country": "Unknown",
            "region": "Unknown",
            "city": "Unknown",
            "provider": "Unknown",
            "asn": "Unknown"
        }

    cache[ip] = result
    save_geo_cache(cache)

    return result
