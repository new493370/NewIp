import requests

requests.packages.urllib3.disable_warnings()

CDN_HEADERS = {
    "cloudflare": [
        "cf-ray",
        "cf-cache-status",
        "cf-worker",
        "cf-polished",
        "cf-request-id"
    ],
    "fastly": [
        "x-served-by",
        "fastly-debug",
        "x-cache",
        "x-cache-hits",
        "fastly-"
    ],
    "akamai": [
        "akamai",
        "x-akamai",
        "x-akamai-transformed",
        "x-akamai-request-id",
        "x-akamaitech"
    ],
    "azure": [
        "x-azure-ref",
        "azure-cdn",
        "x-azurecdn"
    ],
    "bunny": [
        "bunnycdn",
        "x-bunny-",
        "bunny"
    ],
    "gcore": [
        "gcdn",
        "x-gcdn-"
    ],
    "vercel": [
        "x-vercel-id",
        "x-vercel-cache",
        "vercel"
    ],
    "cloudfront": [
        "x-amz-cf-id",
        "x-amz-cf-pop"
    ]
}

TLS_PORTS = {
    443,
    8443,
    2053,
    2083,
    2087,
    2096
}


def safe_lower(v):
    try:
        return str(v).lower()
    except:
        return ""


def normalize_headers(headers):
    if not headers:
        return {}

    out = {}

    try:
        for k, v in headers.items():
            out[
                safe_lower(k)
            ] = safe_lower(v)
    except:
        return {}

    return out


def detect_cdn_from_headers(headers):
    headers = normalize_headers(headers)

    for cdn, signs in CDN_HEADERS.items():
        for sign in signs:
            sign = safe_lower(sign)
            if sign in headers:
                return cdn
            if any(
                sign in v
                for v in headers.values()
            ):
                return cdn

    server = headers.get(
        "server",
        ""
    )

    if "cloudflare" in server:
        return "cloudflare"

    if "fastly" in server:
        return "fastly"

    if "akamai" in server or "akamaitech" in server:
        return "akamai"

    if "bunny" in server:
        return "bunny"

    if "gcore" in server:
        return "gcore"

    if "vercel" in server:
        return "vercel"

    if "cloudfront" in server or "amazon" in server:
        return "cloudfront"

    if "azure" in server or "microsoft" in server:
        return "azure"

    return "unknown"


def detect_cdn_from_provider(provider):
    if not provider or provider == "?":
        return "unknown"
    
    provider_lower = str(provider).lower()
    
    if "akamai" in provider_lower:
        return "akamai"
    if "cloudflare" in provider_lower:
        return "cloudflare"
    if "fastly" in provider_lower:
        return "fastly"
    if "vercel" in provider_lower:
        return "vercel"
    if "amazon" in provider_lower or "cloudfront" in provider_lower:
        return "cloudfront"
    if "microsoft" in provider_lower or "azure" in provider_lower:
        return "azure"
    if "bunny" in provider_lower:
        return "bunny"
    if "gcore" in provider_lower:
        return "gcore"
    if "digitalocean" in provider_lower:
        return "digitalocean"
    if "hetzner" in provider_lower:
        return "hetzner"
    if "cogent" in provider_lower:
        return "cogent"
    
    return "unknown"


def detect_cdn(ip=None, port=None, headers=None, provider=None):
    result = "unknown"
    
    if headers is not None:
        result = detect_cdn_from_headers(headers)
        if result != "unknown":
            return result
    
    if provider is not None and result == "unknown":
        result = detect_cdn_from_provider(provider)
        if result != "unknown":
            return result

    if ip is None or port is None:
        return result

    scheme = (
        "https"
        if port in TLS_PORTS
        else "http"
    )

    try:
        with requests.Session() as session:
            r = session.get(
                f"{scheme}://{ip}:{port}",
                timeout=4,
                verify=False,
                allow_redirects=True,
                headers={"User-Agent": "ARISTA"}
            )

            result = detect_cdn_from_headers(r.headers)
            if result != "unknown":
                return result

    except:
        pass

    return result
