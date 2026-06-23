import requests
import time
import concurrent.futures
from cache import load_geo_cache, save_geo_cache

API_TIMEOUT = 5
MAX_RETRIES = 2
BATCH_SIZE = 50

APIS = [
    {
        "name": "ipwhois",
        "url": "https://ipwho.is/{ip}",
        "parser": lambda data: {
            "country": data.get("country", "Unknown"),
            "asn": data.get("connection", {}).get("asn", "Unknown"),
            "provider": data.get("connection", {}).get("isp", data.get("org", "Unknown"))
        },
        "check": lambda data: data.get("success", False)
    },
    {
        "name": "ipapi",
        "url": "http://ip-api.com/json/{ip}",
        "parser": lambda data: {
            "country": data.get("country", "Unknown"),
            "asn": f"AS{data.get('as', '')}",
            "provider": data.get("isp", data.get("org", "Unknown"))
        },
        "check": lambda data: data.get("status") == "success"
    },
    {
        "name": "ipinfo",
        "url": "https://ipinfo.io/{ip}/json",
        "parser": lambda data: {
            "country": data.get("country", "Unknown"),
            "asn": data.get("org", "Unknown").split(" ")[0] if data.get("org") else "Unknown",
            "provider": data.get("org", "Unknown")
        },
        "check": lambda data: bool(data.get("ip"))
    },
    {
        "name": "freegeoip",
        "url": "https://freegeoip.app/json/{ip}",
        "parser": lambda data: {
            "country": data.get("country_name", "Unknown"),
            "asn": f"AS{data.get('asn', '')}" if data.get("asn") else "Unknown",
            "provider": data.get("isp", data.get("organization", "Unknown"))
        },
        "check": lambda data: bool(data.get("ip"))
    }
]

def geo_lookup_single(ip, api_index=0):
    if api_index >= len(APIS):
        return {"country": "Unknown", "asn": "Unknown", "provider": "Unknown"}
    
    api = APIS[api_index]
    
    try:
        url = api["url"].format(ip=ip)
        r = requests.get(url, timeout=API_TIMEOUT)
        
        if r.status_code == 200:
            data = r.json()
            
            if api["check"](data):
                return api["parser"](data)
        
        return geo_lookup_single(ip, api_index + 1)
        
    except:
        return geo_lookup_single(ip, api_index + 1)

def geo_lookup_batch(ips, batch_size=BATCH_SIZE):
    results = {}
    
    for i in range(0, len(ips), batch_size):
        batch = ips[i:i + batch_size]
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(10, len(batch))) as executor:
            future_to_ip = {
                executor.submit(geo_lookup_single, ip): ip 
                for ip in batch
            }
            
            for future in concurrent.futures.as_completed(future_to_ip):
                ip = future_to_ip[future]
                try:
                    results[ip] = future.result()
                except:
                    results[ip] = {"country": "Unknown", "asn": "Unknown", "provider": "Unknown"}
        
        time.sleep(0.5)
    
    return results

def geo_lookup(ip):
    cache = load_geo_cache()
    
    if ip in cache:
        return cache[ip]
    
    result = geo_lookup_single(ip)
    
    cache[ip] = result
    save_geo_cache(cache)
    
    return result

def geo_lookup_many(ips):
    cache = load_geo_cache()
    
    uncached = [ip for ip in ips if ip not in cache]
    
    if uncached:
        new_results = geo_lookup_batch(uncached)
        
        for ip, data in new_results.items():
            cache[ip] = data
        
        save_geo_cache(cache)
    
    return {ip: cache[ip] for ip in ips}

def geo_bulk_fill(ip_list):
    results = geo_lookup_many(ip_list)
    
    total = len(results)
    cached = sum(1 for v in results.values() if v.get("country") != "Unknown")
    
    print(f"GEO BULK: {total} IPs, {cached} resolved")
    
    return results

if __name__ == "__main__":
    test_ips = ["1.1.1.1", "8.8.8.8", "9.9.9.9", "1.2.3.4"]
    results = geo_lookup_many(test_ips)
    
    for ip, data in results.items():
        print(f"{ip}: {data}")
