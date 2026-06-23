import requests

requests.packages.urllib3.disable_warnings()

CDN_HEADERS = {
    "cloudflare": [
        "cf-ray",
        "cf-cache-status",
        "cf-worker"
    ],
    "fastly": [
        "x-served-by",
        "fastly-debug"
    ],
    "akamai": [
        "akamai",
        "x-akamai"
    ],
    "azure": [
        "x-azure-ref"
    ],
    "bunny": [
        "bunnycdn"
    ],
    "gcore": [
        "gcdn"
    ],
    "vercel": [
        "x-vercel-id"
    ],
    "cloudfront": [
        "x-amz-cf-id"
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

    if "akamai" in server:
        return "akamai"

    if "bunny" in server:
        return "bunny"

    if "gcore" in server:
        return "gcore"

    if "vercel" in server:
        return "vercel"

    if "cloudfront" in server:
        return "cloudfront"

    return "unknown"


def detect_cdn(ip=None, port=None, headers=None):
    if headers is not None:
        return detect_cdn_from_headers(headers)

    if ip is None or port is None:
        return "unknown"

    scheme = (
        "https"
        if port in TLS_PORTS
        else "http"
    )

    try:
        r = requests.get(
            f"{scheme}://{ip}",
            timeout=4,
            verify=False,
            allow_redirects=True
        )

        return detect_cdn_from_headers(r.headers)

    except:
        pass

    return "unknown"
